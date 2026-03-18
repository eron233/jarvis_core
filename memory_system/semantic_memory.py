"""
JARVIS - Memoria Semantica

Responsavel por:
- armazenar fatos e entradas textuais persistentes
- recuperar informacao por pontuacao deterministica de tokens
- expor snapshots auditaveis para runtime e API

Integracoes principais:
- runtime.internal_agent_runtime
- interface.api.app
- memory_system.procedural_memory
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

#
# JARVIS_MEMORY_SYSTEM
# ==================================================
# BLOCO: Entradas semanticas e persistencia local
# ==================================================

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORAGE_PATH = PROJECT_ROOT / "data" / "semantic_memory_store.json"


@dataclass
class MemoryEntry:
    """Entrada estruturada de memoria semantica."""

    id: str
    content: str
    domain: str
    tags: List[str]
    source: str
    created_at: str
    importance: int
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """
        Converte a entrada dataclass para dicionario serializavel.

        Parametros:
        - nenhum.

        Retorno:
        - dicionario completo da entrada.

        Efeitos no sistema:
        - nenhum; apenas facilita persistencia e resposta da API.
        """

        return asdict(self)


@dataclass
class SemanticMemory:
    """Armazena entradas semanticas com pontuacao deterministica por palavras-chave."""

    storage_path: Path = field(default_factory=lambda: DEFAULT_STORAGE_PATH)
    auto_persist: bool = False
    entries: List[Dict[str, Any]] = field(default_factory=list)
    facts: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """
        Normaliza o caminho de armazenamento da memoria semantica.

        Parametros:
        - nenhum.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - garante que `storage_path` seja sempre um `Path`.
        """

        self.storage_path = Path(self.storage_path)

    def add_entry(
        self,
        content: str,
        domain: str,
        tags: Optional[List[str]] = None,
        source: str = "system",
        importance: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
        entry_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Adiciona uma entrada estruturada de memoria semantica."""

        entry = MemoryEntry(
            id=entry_id or self._next_entry_id(),
            content=str(content),
            domain=str(domain),
            tags=self._normalize_tags(tags or []),
            source=str(source),
            created_at=created_at or datetime.now(timezone.utc).isoformat(),
            importance=int(importance),
            metadata=deepcopy(metadata or {}),
        ).to_dict()

        self.entries.append(entry)

        if self.auto_persist:
            self._write_storage()

        return deepcopy(entry)

    def search(self, query: str, domain: Optional[str] = None, limit: int = 5) -> List[Dict[str, Any]]:
        """Recupera as entradas mais relevantes usando pontuacao deterministica."""

        query_tokens = self._tokenize(query)
        normalized_domain = None if domain is None else str(domain)
        ranked_entries: List[Dict[str, Any]] = []

        for entry in self.entries:
            if normalized_domain is not None and entry["domain"] != normalized_domain:
                continue

            score = self._score_entry(entry, query_tokens, normalized_domain)
            if query_tokens and score == 0:
                continue

            ranked_entries.append(
                {
                    "entry": entry,
                    "score": score,
                }
            )

        ranked_entries.sort(
            key=lambda item: (
                -item["score"],
                -int(item["entry"]["importance"]),
                item["entry"]["created_at"],
                item["entry"]["id"],
            )
        )

        results: List[Dict[str, Any]] = []
        for item in ranked_entries[: max(limit, 0)]:
            result = deepcopy(item["entry"])
            result["score"] = item["score"]
            results.append(result)
        return results

    def get_by_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Retorna todas as entradas de um dominio especifico na ordem de insercao."""

        return [deepcopy(entry) for entry in self.entries if entry["domain"] == domain]

    def recent_entries(self, limit: int = 10, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna as entradas mais recentes, opcionalmente filtradas por dominio."""

        entries = self.entries
        if domain is not None:
            entries = [entry for entry in entries if entry["domain"] == domain]

        recent_entries = entries[-max(limit, 0) :]
        return [deepcopy(entry) for entry in reversed(recent_entries)]

    def snapshot(self) -> Dict[str, Any]:
        """Retorna e persiste o snapshot atual da memoria semantica."""

        snapshot = self._build_snapshot()
        self._write_storage(snapshot)
        return snapshot

    def load_snapshot(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Carrega o estado da memoria semantica de um snapshot ou do arquivo em disco."""

        if snapshot is None:
            if not self.storage_path.exists():
                self.entries = []
                self.facts = {}
                return self._build_snapshot()

            snapshot = json.loads(self.storage_path.read_text(encoding="utf-8"))

        loaded_entries = snapshot.get("entries", [])
        self.entries = [self._normalize_entry(entry) for entry in loaded_entries]
        self.facts = deepcopy(snapshot.get("facts", {}))
        return self._build_snapshot()

    def upsert(
        self,
        concept: str,
        value: Any,
        domain: str = "system",
        tags: Optional[List[str]] = None,
        source: str = "system",
        importance: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Helper de compatibilidade para armazenar fatos semanticos nomeados."""

        self.facts[str(concept)] = deepcopy(value)
        merged_metadata = deepcopy(metadata or {})
        merged_metadata.update({"concept": concept, "value": deepcopy(value)})
        return self.add_entry(
            content=f"{concept}: {self._value_as_text(value)}",
            domain=domain,
            tags=[*(tags or []), str(concept)],
            source=source,
            importance=importance,
            metadata=merged_metadata,
        )

    def get(self, concept: str) -> Optional[Any]:
        """Retorna o fato mais recente armazenado para um conceito."""

        value = self.facts.get(concept)
        return deepcopy(value)

    def _score_entry(
        self,
        entry: Dict[str, Any],
        query_tokens: set[str],
        domain: Optional[str],
    ) -> int:
        """
        Calcula a relevancia de uma entrada para uma consulta.

        Parametros:
        - entry: entrada candidata da memoria.
        - query_tokens: tokens derivados da consulta.
        - domain: dominio opcional usado como bonus de correspondencia.

        Retorno:
        - score inteiro usado no ranking final.

        Efeitos no sistema:
        - nenhum; apenas ordena resultados de busca.
        """

        searchable_tokens = (
            self._tokenize(entry["content"])
            | self._tokenize(entry["source"])
            | self._tokenize(json.dumps(entry["metadata"], sort_keys=True))
        )
        tag_tokens = set(entry["tags"])

        content_overlap = len(query_tokens & searchable_tokens)
        tag_overlap = len(query_tokens & tag_tokens)
        domain_bonus = 3 if domain is not None and entry["domain"] == domain else 0

        if not query_tokens and domain is None:
            return 0

        return (content_overlap * 10) + (tag_overlap * 5) + domain_bonus

    def _build_snapshot(self) -> Dict[str, Any]:
        """
        Monta o snapshot completo da memoria semantica.

        Parametros:
        - nenhum.

        Retorno:
        - payload serializavel contendo entradas e fatos.

        Efeitos no sistema:
        - nenhum; base para persistencia e recuperacao.
        """

        return {
            "version": "0.1.0",
            "entry_count": len(self.entries),
            "entries": deepcopy(self.entries),
            "facts": deepcopy(self.facts),
        }

    def _write_storage(self, snapshot: Optional[Dict[str, Any]] = None) -> None:
        """
        Grava em disco o snapshot atual ou fornecido.

        Parametros:
        - snapshot: estado opcional ja montado para persistencia.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - escreve o arquivo JSON da memoria semantica.
        """

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = snapshot or self._build_snapshot()
        temp_path = self.storage_path.with_name(f"{self.storage_path.name}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp_path, self.storage_path)

    def _next_entry_id(self) -> str:
        """
        Gera o proximo identificador sequencial de entrada.

        Parametros:
        - nenhum.

        Retorno:
        - identificador textual da nova entrada.

        Efeitos no sistema:
        - nenhum; apenas padroniza ids locais.
        """

        return f"memory-{len(self.entries) + 1:04d}"

    @staticmethod
    def _normalize_tags(tags: List[str]) -> List[str]:
        """
        Normaliza tags para formato textual unico e em minusculas.

        Parametros:
        - tags: lista original de tags.

        Retorno:
        - lista sem vazios nem duplicacoes.

        Efeitos no sistema:
        - nenhum; melhora consistencia da recuperacao semantica.
        """

        normalized: List[str] = []
        seen: set[str] = set()

        for tag in tags:
            normalized_tag = str(tag).strip().lower()
            if not normalized_tag or normalized_tag in seen:
                continue
            normalized.append(normalized_tag)
            seen.add(normalized_tag)

        return normalized

    @staticmethod
    def _normalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Padroniza uma entrada carregada do disco.

        Parametros:
        - entry: payload bruto do snapshot persistido.

        Retorno:
        - entrada pronta para uso interno.

        Efeitos no sistema:
        - nenhum; saneia dados antigos ou incompletos.
        """

        return {
            "id": str(entry["id"]),
            "content": str(entry["content"]),
            "domain": str(entry["domain"]),
            "tags": SemanticMemory._normalize_tags(list(entry.get("tags", []))),
            "source": str(entry.get("source", "system")),
            "created_at": str(entry["created_at"]),
            "importance": int(entry.get("importance", 0)),
            "metadata": deepcopy(entry.get("metadata", {})),
        }

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        """
        Tokeniza texto simples para busca deterministica.

        Parametros:
        - value: texto de origem.

        Retorno:
        - conjunto de tokens normalizados.

        Efeitos no sistema:
        - nenhum; utilitario da estrategia de busca.
        """

        return set(TOKEN_PATTERN.findall(value.lower()))

    @staticmethod
    def _value_as_text(value: Any) -> str:
        """
        Converte um valor arbitrario em texto para armazenamento semantico.

        Parametros:
        - value: valor estruturado ou simples.

        Retorno:
        - representacao textual deterministica.

        Efeitos no sistema:
        - nenhum; usado por `upsert` e snapshots.
        """

        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True)
        return str(value)
