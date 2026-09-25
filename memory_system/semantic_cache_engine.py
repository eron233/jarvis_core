"""
JARVIS - Motor de Cache Semântico Local (Semantic Cache Engine)

Responsável por:
- evitar chamadas repetitivas e redundantes a LLMs externos/processamento pesado
- armazenar pares de consulta/resposta com chaveamento por similaridade semântica
- economizar tempo, latência e tokens
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOGGER = logging.getLogger("jarvis.memory.semantic_cache")


class SemanticCacheEngine:
    """Motor de cache semântico local para otimização de consultas e economia de tokens."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else Path(__file__).resolve().parents[1] / "data" / "semantic_cache.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_entries: List[Dict[str, Any]] = []
        # Índices em memória para leitura rápida (evitam varredura e reescrita de disco):
        # - _by_hash: acesso O(1) por (domínio, hash) na busca exata;
        # - _tokens: conjunto de tokens de cada entrada, alinhado por posição, para Jaccard
        #   sem recomputar split a cada comparação.
        self._by_hash: Dict[tuple, Dict[str, Any]] = {}
        self._tokens: List[set] = []
        self._dirty = False
        self._load_cache()

    def get(self, query: str, domain: str = "general") -> Optional[Dict[str, Any]]:
        """
        Busca uma resposta no cache. Atualiza contadores APENAS em memória; a persistência
        acontece em put()/flush(), não a cada leitura (antes reescrevia o arquivo inteiro por
        leitura, custando I/O O(n) por acesso).
        """
        normalized_query = self._normalize_text(query)
        query_hash = self._compute_hash(normalized_query)

        # 1. Busca Exata por Hash — O(1) via índice
        entry = self._by_hash.get((domain, query_hash))
        if entry is not None:
            self._register_hit(entry)
            return entry["response"]

        # 2. Busca por Similaridade Semântica (Jaccard) — tokens pré-computados
        query_tokens = set(normalized_query.split())
        if query_tokens:
            for idx, cand in enumerate(self.cache_entries):
                if cand["domain"] != domain:
                    continue
                similarity = self._jaccard(query_tokens, self._tokens[idx])
                if similarity >= 0.82:
                    self._register_hit(cand)
                    LOGGER.info("[semantic_cache_hit] Similaridade %.2f para: %s", similarity, query[:40])
                    return cand["response"]

        return None

    def _register_hit(self, entry: Dict[str, Any]) -> None:
        entry["hits"] += 1
        entry["last_accessed_at"] = datetime.now(timezone.utc).isoformat()
        self._dirty = True  # persistência adiada até flush()/put()

    def put(self, query: str, response: Dict[str, Any], domain: str = "general", tokens_saved_estimate: int = 250) -> None:
        """Armazena um novo par consulta/resposta e persiste no disco."""
        now = datetime.now(timezone.utc).isoformat()
        normalized_query = self._normalize_text(query)
        query_hash = self._compute_hash(normalized_query)

        entry = {
            "query": query,
            "normalized_query": normalized_query,
            "hash": query_hash,
            "domain": domain,
            "response": response,
            "created_at": now,
            "last_accessed_at": now,
            "hits": 0,
            "tokens_saved_estimate": tokens_saved_estimate,
        }

        self.cache_entries.append(entry)
        self._tokens.append(set(normalized_query.split()))
        self._by_hash[(domain, query_hash)] = entry
        self._save_cache()

    def flush(self) -> None:
        """Persiste em disco os contadores acumulados em memória, se houver mudanças."""
        if self._dirty:
            self._save_cache()

    def get_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de uso e economia de tokens acumulada."""
        total_hits = sum(e["hits"] for e in self.cache_entries)
        estimated_tokens_saved = sum(e["hits"] * e["tokens_saved_estimate"] for e in self.cache_entries)

        return {
            "total_entradas_cache": len(self.cache_entries),
            "total_hits_acumulados": total_hits,
            "estimativa_tokens_economizados": estimated_tokens_saved,
            "taxa_eficiencia": "alta",
        }

    def _normalize_text(self, text: str) -> str:
        """Normaliza o texto para comparação."""
        return " ".join(text.lower().strip().split())

    def _compute_hash(self, text: str) -> str:
        """Gera o hash SHA-256 do texto normalizado."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _jaccard(tokens1: set, tokens2: set) -> float:
        """Similaridade de Jaccard entre dois conjuntos de tokens já computados."""
        if not tokens1 or not tokens2:
            return 0.0
        inter = len(tokens1 & tokens2)
        if inter == 0:
            return 0.0
        return inter / len(tokens1 | tokens2)

    def _calculate_text_similarity(self, str1: str, str2: str) -> float:
        """Compatibilidade: similaridade de Jaccard entre duas strings."""
        return self._jaccard(set(str1.split()), set(str2.split()))

    def _rebuild_indexes(self) -> None:
        """Reconstrói os índices em memória a partir de cache_entries."""
        self._by_hash = {}
        self._tokens = []
        for entry in self.cache_entries:
            self._tokens.append(set(str(entry.get("normalized_query", "")).split()))
            self._by_hash[(entry.get("domain"), entry.get("hash"))] = entry

    def _load_cache(self) -> None:
        """Carrega as entradas do cache do arquivo JSON e reconstrói os índices."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self.cache_entries = data.get("entries", [])
            except Exception as e:
                LOGGER.error("Erro ao carregar cache semântico: %s", e)
                self.cache_entries = []
        self._rebuild_indexes()

    def _save_cache(self) -> None:
        """Persiste as entradas do cache no arquivo JSON."""
        payload = {"entries": self.cache_entries}
        self.storage_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        self._dirty = False
