"""Armazenamento deterministico de memoria semantica para fatos e entradas pesquisaveis."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
DEFAULT_STORAGE_PATH = Path(__file__).with_name("semantic_memory_store.json")


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
        return asdict(self)


@dataclass
class SemanticMemory:
    """Armazena entradas semanticas com pontuacao deterministica por palavras-chave."""

    storage_path: Path = field(default_factory=lambda: DEFAULT_STORAGE_PATH)
    auto_persist: bool = False
    entries: List[Dict[str, Any]] = field(default_factory=list)
    facts: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
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
        return {
            "version": "0.1.0",
            "entry_count": len(self.entries),
            "entries": deepcopy(self.entries),
            "facts": deepcopy(self.facts),
        }

    def _write_storage(self, snapshot: Optional[Dict[str, Any]] = None) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = snapshot or self._build_snapshot()
        self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _next_entry_id(self) -> str:
        return f"memory-{len(self.entries) + 1:04d}"

    @staticmethod
    def _normalize_tags(tags: List[str]) -> List[str]:
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
        return set(TOKEN_PATTERN.findall(value.lower()))

    @staticmethod
    def _value_as_text(value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, sort_keys=True)
        return str(value)
