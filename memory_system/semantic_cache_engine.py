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
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

LOGGER = logging.getLogger("jarvis.memory.semantic_cache")


class SemanticCacheEngine:
    """Motor de cache semântico local para otimização de consultas e economia de tokens."""

    def __init__(self, storage_path: Optional[Path] = None) -> None:
        self.storage_path = Path(storage_path) if storage_path else Path(__file__).resolve().parents[1] / "data" / "semantic_cache.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_entries: List[Dict[str, Any]] = []
        self._load_cache()

    def get(self, query: str, domain: str = "general") -> Optional[Dict[str, Any]]:
        """
        Busca uma resposta no cache com base na similaridade da consulta.
        """
        normalized_query = self._normalize_text(query)
        query_hash = self._compute_hash(normalized_query)

        # 1. Busca Exata por Hash
        for entry in self.cache_entries:
            if entry["domain"] == domain and entry["hash"] == query_hash:
                entry["hits"] += 1
                entry["last_accessed_at"] = datetime.now(timezone.utc).isoformat()
                self._save_cache()
                LOGGER.info("[semantic_cache_hit] Cache exato encontrado para: %s", query[:40])
                return entry["response"]

        # 2. Busca por Similaridade Semântica (Jaccard / Trigram Overlap)
        for entry in self.cache_entries:
            if entry["domain"] == domain:
                similarity = self._calculate_text_similarity(normalized_query, entry["normalized_query"])
                if similarity >= 0.82:  # Limiar de similaridade semântica
                    entry["hits"] += 1
                    entry["last_accessed_at"] = datetime.now(timezone.utc).isoformat()
                    self._save_cache()
                    LOGGER.info("[semantic_cache_hit] Cache semântico (sim=%.2f) encontrado para: %s", similarity, query[:40])
                    return entry["response"]

        return None

    def put(self, query: str, response: Dict[str, Any], domain: str = "general", tokens_saved_estimate: int = 250) -> None:
        """
        Armazena um novo par de consulta e resposta no cache semântico.
        """
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

    def _calculate_text_similarity(self, str1: str, str2: str) -> float:
        """Calcula a similaridade de Jaccard baseada em n-gramas entre duas strings."""
        words1 = set(str1.split())
        words2 = set(str2.split())
        if not words1 or not words2:
            return 0.0
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union)

    def _load_cache(self) -> None:
        """Carrega as entradas do cache do arquivo JSON."""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                self.cache_entries = data.get("entries", [])
            except Exception as e:
                LOGGER.error("Erro ao carregar cache semântico: %s", e)
                self.cache_entries = []

    def _save_cache(self) -> None:
        """
        Persiste as entradas do cache no arquivo JSON.

        A gravacao passa por um arquivo temporario trocado de nome ao final, o
        mesmo padrao do restante da persistencia do projeto. Escrever direto no
        destino deixa um JSON truncado quando o processo cai no meio da escrita.
        """

        payload = {"entries": self.cache_entries}
        temp_path = self.storage_path.with_name(f"{self.storage_path.name}.tmp")
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp_path, self.storage_path)
