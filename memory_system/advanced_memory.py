"""
JARVIS - Advanced Memory Stack

Camada opcional de recuperacao semantica real e memoria de longo prazo.

Componentes suportados:
- Qwen3-Embedding via sentence-transformers
- Qwen3-Reranker via sentence-transformers CrossEncoder
- Qdrant local ou remoto
- Mem0 OSS com Qdrant + Ollama

A camada e deliberadamente opcional: se dependencias/modelos nao estiverem
instalados, o JARVIS continua usando a busca deterministica existente.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional
from uuid import NAMESPACE_URL, uuid5


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


@dataclass(frozen=True)
class AdvancedMemoryConfig:
    """Configuracao da camada avancada de memoria."""

    enabled: bool = False
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    qdrant_path: Path = PROJECT_ROOT / "data" / "qdrant"
    qdrant_collection: str = "jarvis_semantic_memory"
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    reranker_model: str = "Qwen/Qwen3-Reranker-0.6B"
    vector_top_k: int = 20
    mem0_enabled: bool = False
    mem0_user_id: str = "jarvis-owner"
    ollama_base_url: str = "http://localhost:11434"
    mem0_llm_model: str = "qwen3:4b"

    @classmethod
    def from_env(
        cls,
        environ: Optional[Mapping[str, str]] = None,
        project_root: Optional[Path] = None,
    ) -> "AdvancedMemoryConfig":
        env = dict(environ or os.environ)
        root = Path(project_root or PROJECT_ROOT)
        return cls(
            enabled=_env_bool(env.get("JARVIS_ADVANCED_MEMORY_ENABLED"), False),
            qdrant_url=(env.get("JARVIS_QDRANT_URL") or "").strip() or None,
            qdrant_api_key=(env.get("JARVIS_QDRANT_API_KEY") or "").strip() or None,
            qdrant_path=Path(env.get("JARVIS_QDRANT_PATH", root / "data" / "qdrant")),
            qdrant_collection=(env.get("JARVIS_QDRANT_COLLECTION") or "jarvis_semantic_memory").strip(),
            embedding_model=(env.get("JARVIS_EMBEDDING_MODEL") or "Qwen/Qwen3-Embedding-0.6B").strip(),
            reranker_model=(env.get("JARVIS_RERANKER_MODEL") or "Qwen/Qwen3-Reranker-0.6B").strip(),
            vector_top_k=max(1, int(env.get("JARVIS_VECTOR_TOP_K", "20"))),
            mem0_enabled=_env_bool(env.get("JARVIS_MEM0_ENABLED"), False),
            mem0_user_id=(env.get("JARVIS_MEM0_USER_ID") or "jarvis-owner").strip(),
            ollama_base_url=(env.get("JARVIS_OLLAMA_BASE_URL") or "http://localhost:11434").strip(),
            mem0_llm_model=(env.get("JARVIS_MEM0_LLM_MODEL") or "qwen3:4b").strip(),
        )


class QwenEmbeddingEngine:
    """Carrega Qwen3-Embedding de forma lazy para nao pesar no bootstrap."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: Any = None
        self._load_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self._ensure_model()

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        if self._load_error is not None:
            return False
        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            return True
        except Exception as exc:  # dependencias/modelo sao opcionais
            self._load_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def encode(self, texts: Iterable[str]) -> List[List[float]]:
        if not self._ensure_model():
            raise RuntimeError(self._load_error or "Qwen3-Embedding indisponivel.")
        values = list(texts)
        vectors = self._model.encode(values, normalize_embeddings=True)
        return [vector.tolist() if hasattr(vector, "tolist") else list(vector) for vector in vectors]


class QwenRerankerEngine:
    """Reranking local com Qwen3-Reranker, carregado somente quando usado."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._model: Any = None
        self._load_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self._ensure_model()

    def _ensure_model(self) -> bool:
        if self._model is not None:
            return True
        if self._load_error is not None:
            return False
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
            return True
        except Exception as exc:
            self._load_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def score(self, query: str, documents: List[str]) -> List[float]:
        if not documents:
            return []
        if not self._ensure_model():
            return [0.0 for _ in documents]
        raw = self._model.predict([(query, document) for document in documents])
        scores: List[float] = []
        for value in raw:
            numeric = float(value)
            scores.append(1.0 / (1.0 + math.exp(-max(-60.0, min(60.0, numeric)))))
        return scores


class QdrantSemanticIndex:
    """Indice vetorial Qdrant para entradas da memoria semantica."""

    def __init__(self, config: AdvancedMemoryConfig, embedder: QwenEmbeddingEngine) -> None:
        self.config = config
        self.embedder = embedder
        self._client: Any = None
        self._models: Any = None
        self._dimension: Optional[int] = None
        self._load_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.config.enabled and self._ensure_client() and self.embedder.available

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error or self.embedder.load_error

    def _ensure_client(self) -> bool:
        if self._client is not None:
            return True
        if self._load_error is not None:
            return False
        try:
            from qdrant_client import QdrantClient, models

            if self.config.qdrant_url:
                self._client = QdrantClient(
                    url=self.config.qdrant_url,
                    api_key=self.config.qdrant_api_key,
                )
            else:
                self.config.qdrant_path.mkdir(parents=True, exist_ok=True)
                self._client = QdrantClient(path=str(self.config.qdrant_path))
            self._models = models
            return True
        except Exception as exc:
            self._load_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def _ensure_collection(self, vector: List[float]) -> None:
        dimension = len(vector)
        self._dimension = dimension
        exists = False
        try:
            exists = bool(self._client.collection_exists(self.config.qdrant_collection))
        except AttributeError:
            try:
                self._client.get_collection(self.config.qdrant_collection)
                exists = True
            except Exception:
                exists = False
        if not exists:
            self._client.create_collection(
                collection_name=self.config.qdrant_collection,
                vectors_config=self._models.VectorParams(
                    size=dimension,
                    distance=self._models.Distance.COSINE,
                ),
            )

    @staticmethod
    def _point_id(entry_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"jarvis-memory:{entry_id}"))

    def index_entry(self, entry: Dict[str, Any]) -> bool:
        if not self.available:
            return False
        vector = self.embedder.encode([str(entry.get("content", ""))])[0]
        self._ensure_collection(vector)
        payload = {
            "entry_id": str(entry["id"]),
            "domain": str(entry.get("domain", "general")),
            "source": str(entry.get("source", "system")),
            "importance": int(entry.get("importance", 0)),
            "content": str(entry.get("content", "")),
            "tags": list(entry.get("tags", [])),
        }
        self._client.upsert(
            collection_name=self.config.qdrant_collection,
            points=[
                self._models.PointStruct(
                    id=self._point_id(str(entry["id"])),
                    vector=vector,
                    payload=payload,
                )
            ],
            wait=True,
        )
        return True

    def rebuild(self, entries: Iterable[Dict[str, Any]]) -> int:
        indexed = 0
        for entry in entries:
            try:
                indexed += int(self.index_entry(entry))
            except Exception:
                continue
        return indexed

    def search(self, query: str, domain: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        if not self.available:
            return []
        vector = self.embedder.encode([query])[0]
        self._ensure_collection(vector)
        query_filter = None
        if domain is not None:
            query_filter = self._models.Filter(
                must=[
                    self._models.FieldCondition(
                        key="domain",
                        match=self._models.MatchValue(value=str(domain)),
                    )
                ]
            )

        if hasattr(self._client, "query_points"):
            response = self._client.query_points(
                collection_name=self.config.qdrant_collection,
                query=vector,
                query_filter=query_filter,
                limit=max(1, limit),
                with_payload=True,
            )
            points = response.points
        else:
            points = self._client.search(
                collection_name=self.config.qdrant_collection,
                query_vector=vector,
                query_filter=query_filter,
                limit=max(1, limit),
                with_payload=True,
            )

        results: List[Dict[str, Any]] = []
        for point in points:
            payload = dict(point.payload or {})
            results.append(
                {
                    "entry_id": payload.get("entry_id"),
                    "content": payload.get("content", ""),
                    "vector_score": float(point.score),
                }
            )
        return results


class Mem0Bridge:
    """Ponte opcional para memoria conversacional de longo prazo via Mem0 OSS."""

    def __init__(self, config: AdvancedMemoryConfig) -> None:
        self.config = config
        self._memory: Any = None
        self._load_error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.config.enabled and self.config.mem0_enabled and self._ensure_memory()

    @property
    def load_error(self) -> Optional[str]:
        return self._load_error

    def _ensure_memory(self) -> bool:
        if self._memory is not None:
            return True
        if self._load_error is not None:
            return False
        try:
            from mem0 import Memory

            qdrant_config: Dict[str, Any] = {
                "collection_name": "jarvis_mem0",
            }
            if self.config.qdrant_url:
                qdrant_config["url"] = self.config.qdrant_url
                if self.config.qdrant_api_key:
                    qdrant_config["api_key"] = self.config.qdrant_api_key
            else:
                qdrant_config["path"] = str(self.config.qdrant_path / "mem0")

            mem0_config = {
                "vector_store": {"provider": "qdrant", "config": qdrant_config},
                "embedder": {
                    "provider": "huggingface",
                    "config": {"model": self.config.embedding_model},
                },
                "llm": {
                    "provider": "ollama",
                    "config": {
                        "model": self.config.mem0_llm_model,
                        "ollama_base_url": self.config.ollama_base_url,
                        "temperature": 0,
                    },
                },
            }
            self._memory = Memory.from_config(mem0_config)
            return True
        except Exception as exc:
            self._load_error = f"{exc.__class__.__name__}: {exc}"
            return False

    def remember(
        self,
        messages: Any,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if not self.available:
            return {"status": "indisponivel", "motivo": self._load_error}
        result = self._memory.add(
            messages,
            user_id=user_id or self.config.mem0_user_id,
            metadata=metadata or {},
        )
        return {"status": "sucesso", "resultado": result}

    def recall(self, query: str, user_id: Optional[str] = None) -> Dict[str, Any]:
        if not self.available:
            return {"status": "indisponivel", "motivo": self._load_error, "results": []}
        result = self._memory.search(
            query,
            user_id=user_id or self.config.mem0_user_id,
        )
        if isinstance(result, dict):
            results = result.get("results", [])
        else:
            results = result
        return {"status": "sucesso", "results": results}


class AdvancedMemoryRetriever:
    """Orquestra Qdrant + Qwen embedding/reranker + Mem0 sem quebrar o fallback local."""

    def __init__(self, config: Optional[AdvancedMemoryConfig] = None) -> None:
        self.config = config or AdvancedMemoryConfig.from_env()
        self.embedder = QwenEmbeddingEngine(self.config.embedding_model)
        self.reranker = QwenRerankerEngine(self.config.reranker_model)
        self.index = QdrantSemanticIndex(self.config, self.embedder)
        self.mem0 = Mem0Bridge(self.config)

    @property
    def available(self) -> bool:
        return self.index.available

    def index_entry(self, entry: Dict[str, Any]) -> bool:
        try:
            return self.index.index_entry(entry)
        except Exception:
            return False

    def rebuild(self, entries: Iterable[Dict[str, Any]]) -> int:
        try:
            return self.index.rebuild(entries)
        except Exception:
            return 0

    def search(
        self,
        query: str,
        entries_by_id: Mapping[str, Dict[str, Any]],
        domain: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        candidates = self.index.search(
            query=query,
            domain=domain,
            limit=max(limit, self.config.vector_top_k),
        )
        if not candidates:
            return []

        documents = [str(item.get("content", "")) for item in candidates]
        rerank_scores = self.reranker.score(query, documents)

        results: List[Dict[str, Any]] = []
        for candidate, rerank_score in zip(candidates, rerank_scores):
            entry_id = str(candidate.get("entry_id") or "")
            entry = entries_by_id.get(entry_id)
            if entry is None:
                continue
            vector_score = max(0.0, min(1.0, (float(candidate["vector_score"]) + 1.0) / 2.0))
            importance_bonus = max(0.0, min(0.1, int(entry.get("importance", 0)) / 100.0))
            score = (0.78 * vector_score) + (0.20 * rerank_score) + importance_bonus
            results.append(
                {
                    "entry": entry,
                    "score": score,
                    "vector_score": vector_score,
                    "rerank_score": rerank_score,
                }
            )

        results.sort(key=lambda item: (-item["score"], str(item["entry"].get("id", ""))))
        return results[: max(0, limit)]

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "vector_available": self.index.available,
            "embedding_model": self.config.embedding_model,
            "reranker_model": self.config.reranker_model,
            "qdrant_collection": self.config.qdrant_collection,
            "qdrant_mode": "remoto" if self.config.qdrant_url else "local",
            "mem0_enabled": self.config.mem0_enabled,
            "mem0_available": self.mem0.available if self.config.mem0_enabled else False,
            "fallback": "deterministic_token_search",
            "load_error": self.index.load_error,
            "mem0_error": self.mem0.load_error,
        }
