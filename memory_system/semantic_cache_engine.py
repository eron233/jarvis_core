"""
JARVIS - Motor de Cache Semantico

Ponto 10.

Regras:
- cache exato funciona sem modelo;
- cache vetorial e opcional;
- nenhum modelo de embedding e escolhido por padrao;
- Qdrant e apenas infraestrutura de indice;
- sem modelo configurado, nao existe falsa "similaridade semantica";
- estatisticas reportam hits/misses observados, sem inventar economia de tokens.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from uuid import NAMESPACE_URL, uuid5

LOGGER = logging.getLogger("jarvis.memory.semantic_cache")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


@dataclass(frozen=True)
class SemanticCacheConfig:
    """Configuracao do cache semantico sem selecionar modelo por default."""

    vector_enabled: bool = False
    embedding_model: Optional[str] = None
    similarity_threshold: float = 0.90
    vector_top_k: int = 3
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    qdrant_path: Path = PROJECT_ROOT / "data" / "qdrant_semantic_cache"
    qdrant_collection: str = "jarvis_semantic_cache"

    @classmethod
    def from_env(
        cls,
        environ: Optional[Mapping[str, str]] = None,
        project_root: Optional[Path] = None,
    ) -> "SemanticCacheConfig":
        env = dict(environ or os.environ)
        root = Path(project_root or PROJECT_ROOT)
        threshold = float(env.get("JARVIS_SEMANTIC_CACHE_SIMILARITY_THRESHOLD", "0.90"))
        return cls(
            vector_enabled=_env_bool(
                env.get("JARVIS_SEMANTIC_CACHE_VECTOR_ENABLED"),
                False,
            ),
            embedding_model=(env.get("JARVIS_SEMANTIC_CACHE_EMBEDDING_MODEL") or "").strip() or None,
            similarity_threshold=max(-1.0, min(1.0, threshold)),
            vector_top_k=max(1, int(env.get("JARVIS_SEMANTIC_CACHE_VECTOR_TOP_K", "3"))),
            qdrant_url=(env.get("JARVIS_SEMANTIC_CACHE_QDRANT_URL") or "").strip() or None,
            qdrant_api_key=(env.get("JARVIS_SEMANTIC_CACHE_QDRANT_API_KEY") or "").strip() or None,
            qdrant_path=Path(
                env.get(
                    "JARVIS_SEMANTIC_CACHE_QDRANT_PATH",
                    root / "data" / "qdrant_semantic_cache",
                )
            ),
            qdrant_collection=(
                env.get("JARVIS_SEMANTIC_CACHE_QDRANT_COLLECTION")
                or "jarvis_semantic_cache"
            ).strip(),
        )


class QdrantSemanticCacheBackend:
    """Backend vetorial opcional. Carrega modelo e Qdrant somente quando usado."""

    def __init__(self, config: SemanticCacheConfig) -> None:
        self.config = config
        self._embedder: Any = None
        self._client: Any = None
        self._models: Any = None
        self._load_error: Optional[str] = None

    @property
    def configured(self) -> bool:
        return bool(self.config.vector_enabled and self.config.embedding_model)

    @property
    def available(self) -> bool:
        return self.configured and self._ensure_ready()

    def status(self) -> Dict[str, Any]:
        return {
            "configured": self.configured,
            "vector_enabled": self.config.vector_enabled,
            "embedding_model_configured": bool(self.config.embedding_model),
            "active": self._embedder is not None and self._client is not None,
            "backend": "qdrant",
            "collection": self.config.qdrant_collection,
            "load_error": self._load_error,
        }

    def _ensure_ready(self) -> bool:
        if not self.configured:
            return False
        if self._embedder is not None and self._client is not None:
            return True
        if self._load_error is not None:
            return False

        try:
            from qdrant_client import QdrantClient, models
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(str(self.config.embedding_model))
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
            LOGGER.warning("Cache vetorial indisponivel: %s", self._load_error)
            return False

    def _encode(self, text: str) -> List[float]:
        vector = self._embedder.encode([text], normalize_embeddings=True)[0]
        return vector.tolist() if hasattr(vector, "tolist") else list(vector)

    def _ensure_collection(self, dimension: int) -> None:
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
        return str(uuid5(NAMESPACE_URL, f"jarvis-semantic-cache:{entry_id}"))

    def upsert(self, entry: Dict[str, Any]) -> bool:
        if not self.available:
            return False

        vector = self._encode(str(entry["normalized_query"]))
        self._ensure_collection(len(vector))
        self._client.upsert(
            collection_name=self.config.qdrant_collection,
            points=[
                self._models.PointStruct(
                    id=self._point_id(str(entry["id"])),
                    vector=vector,
                    payload={
                        "entry_id": str(entry["id"]),
                        "domain": str(entry["domain"]),
                        "hash": str(entry["hash"]),
                    },
                )
            ],
            wait=True,
        )
        return True

    def search(self, query: str, domain: str, limit: int = 3) -> List[Tuple[str, float]]:
        if not self.available:
            return []

        vector = self._encode(query)
        self._ensure_collection(len(vector))
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

        results: List[Tuple[str, float]] = []
        for point in points:
            payload = dict(point.payload or {})
            entry_id = str(payload.get("entry_id") or "")
            if entry_id:
                results.append((entry_id, float(point.score)))
        return results


class SemanticCacheEngine:
    """Cache exato sempre disponivel e cache vetorial opcional por configuracao."""

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        config: Optional[SemanticCacheConfig] = None,
        vector_backend: Optional[Any] = None,
    ) -> None:
        self.storage_path = (
            Path(storage_path)
            if storage_path
            else PROJECT_ROOT / "data" / "semantic_cache.json"
        )
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.config = config or SemanticCacheConfig.from_env()
        self.vector_backend = vector_backend or QdrantSemanticCacheBackend(self.config)
        self.cache_entries: List[Dict[str, Any]] = []
        self._stats: Dict[str, int] = {
            "exact_hits": 0,
            "vector_hits": 0,
            "misses": 0,
        }
        self._load_cache()

    def get(self, query: str, domain: str = "general") -> Optional[Dict[str, Any]]:
        """Busca primeiro por chave exata e depois, se configurado, por vetor real."""

        normalized_query = self._normalize_text(query)
        query_hash = self._compute_hash(normalized_query)

        for entry in self.cache_entries:
            if entry["domain"] == domain and entry["hash"] == query_hash:
                entry["exact_hits"] += 1
                entry["last_accessed_at"] = datetime.now(timezone.utc).isoformat()
                self._stats["exact_hits"] += 1
                self._save_cache()
                return deepcopy(entry["response"])

        try:
            if self.vector_backend.available:
                matches = self.vector_backend.search(
                    normalized_query,
                    domain,
                    limit=self.config.vector_top_k,
                )
                entries_by_id = {
                    str(entry["id"]): entry
                    for entry in self.cache_entries
                    if entry["domain"] == domain
                }
                for entry_id, similarity in matches:
                    if similarity < self.config.similarity_threshold:
                        continue
                    entry = entries_by_id.get(str(entry_id))
                    if entry is None:
                        continue
                    entry["vector_hits"] += 1
                    entry["last_accessed_at"] = datetime.now(timezone.utc).isoformat()
                    entry["last_vector_similarity"] = round(float(similarity), 6)
                    self._stats["vector_hits"] += 1
                    self._save_cache()
                    return deepcopy(entry["response"])
        except Exception as exc:
            LOGGER.warning("Falha no backend vetorial do cache: %s", exc)

        self._stats["misses"] += 1
        self._save_cache()
        return None

    def put(
        self,
        query: str,
        response: Dict[str, Any],
        domain: str = "general",
        tokens_saved_estimate: Optional[int] = None,
    ) -> None:
        """
        Armazena um par consulta/resposta.

        tokens_saved_estimate e aceito apenas por compatibilidade com chamadas antigas;
        ele nao e usado nem reportado, porque nao existe medicao real de tokens aqui.
        """

        del tokens_saved_estimate
        now = datetime.now(timezone.utc).isoformat()
        normalized_query = self._normalize_text(query)
        query_hash = self._compute_hash(normalized_query)

        existing = next(
            (
                entry
                for entry in self.cache_entries
                if entry["domain"] == domain and entry["hash"] == query_hash
            ),
            None,
        )

        if existing is None:
            entry_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"jarvis-semantic-cache:{domain}:{query_hash}",
                )
            )
            entry = {
                "id": entry_id,
                "query": query,
                "normalized_query": normalized_query,
                "hash": query_hash,
                "domain": domain,
                "response": deepcopy(response),
                "created_at": now,
                "last_accessed_at": now,
                "exact_hits": 0,
                "vector_hits": 0,
                "last_vector_similarity": None,
            }
            self.cache_entries.append(entry)
        else:
            entry = existing
            entry["query"] = query
            entry["normalized_query"] = normalized_query
            entry["response"] = deepcopy(response)
            entry["last_accessed_at"] = now

        try:
            if self.vector_backend.available:
                self.vector_backend.upsert(entry)
        except Exception as exc:
            LOGGER.warning("Entrada salva sem indexacao vetorial: %s", exc)

        self._save_cache()

    def get_stats(self) -> Dict[str, Any]:
        """Retorna somente metricas observadas e o estado configurado do backend."""

        exact_hits = int(self._stats.get("exact_hits", 0))
        vector_hits = int(self._stats.get("vector_hits", 0))
        misses = int(self._stats.get("misses", 0))
        total_queries = exact_hits + vector_hits + misses
        hits = exact_hits + vector_hits

        backend_status: Dict[str, Any]
        try:
            backend_status = dict(self.vector_backend.status())
        except Exception:
            backend_status = {
                "configured": False,
                "active": False,
                "backend": "unknown",
            }

        return {
            "total_entradas_cache": len(self.cache_entries),
            "consultas_observadas": total_queries,
            "hits_exatos": exact_hits,
            "hits_vetoriais": vector_hits,
            "misses": misses,
            "taxa_hit_observada": round(hits / total_queries, 6) if total_queries else 0.0,
            "similaridade_minima_vetorial": self.config.similarity_threshold,
            "cache_vetorial": backend_status,
            "modelo_selecionado_pelo_sistema": False,
        }

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(str(text).lower().strip().split())

    @staticmethod
    def _compute_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _load_cache(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            raw_entries = data.get("entries", [])
            self.cache_entries = [
                self._normalize_loaded_entry(entry)
                for entry in raw_entries
                if isinstance(entry, dict)
            ]
            raw_stats = data.get("stats", {})
            for key in self._stats:
                self._stats[key] = max(0, int(raw_stats.get(key, 0)))
        except Exception as exc:
            LOGGER.error("Erro ao carregar cache semantico: %s", exc)
            self.cache_entries = []
            self._stats = {"exact_hits": 0, "vector_hits": 0, "misses": 0}

    def _normalize_loaded_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        normalized_query = self._normalize_text(
            str(entry.get("normalized_query") or entry.get("query") or "")
        )
        domain = str(entry.get("domain", "general"))
        query_hash = str(entry.get("hash") or self._compute_hash(normalized_query))
        entry_id = str(
            entry.get("id")
            or uuid5(
                NAMESPACE_URL,
                f"jarvis-semantic-cache:{domain}:{query_hash}",
            )
        )

        return {
            "id": entry_id,
            "query": str(entry.get("query", "")),
            "normalized_query": normalized_query,
            "hash": query_hash,
            "domain": domain,
            "response": deepcopy(entry.get("response", {})),
            "created_at": str(
                entry.get("created_at") or datetime.now(timezone.utc).isoformat()
            ),
            "last_accessed_at": str(
                entry.get("last_accessed_at")
                or entry.get("created_at")
                or datetime.now(timezone.utc).isoformat()
            ),
            "exact_hits": max(0, int(entry.get("exact_hits", 0))),
            "vector_hits": max(0, int(entry.get("vector_hits", 0))),
            "last_vector_similarity": entry.get("last_vector_similarity"),
            "legacy_hits_unclassified": max(0, int(entry.get("hits", 0))),
        }

    def _save_cache(self) -> None:
        payload = {
            "schema_version": 2,
            "entries": self.cache_entries,
            "stats": self._stats,
        }
        temp_path = self.storage_path.with_name(f"{self.storage_path.name}.tmp")
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temp_path, self.storage_path)
