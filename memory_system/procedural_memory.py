"""Armazenamento estruturado de memoria procedural para heuristicas reutilizaveis."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
DEFAULT_STORAGE_FILENAME = "procedural_memory_store.json"


@dataclass
class ProcedureEntry:
    """Entrada estruturada de memoria procedural."""

    id: str
    name: str
    domain: str
    task_type: str
    steps: List[str]
    heuristic: str
    context: Dict[str, Any]
    preconditions: List[str]
    observed_result: str
    success: bool
    evidence: List[str]
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProceduralMemory:
    """Armazena procedimentos estruturados com busca deterministica e persistencia opcional."""

    storage_path: Path | None = None
    auto_persist: bool = False
    procedures: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.storage_path is not None:
            self.storage_path = Path(self.storage_path)

    def register(
        self,
        name: str,
        steps: List[str],
        domain: str = "system",
        task_type: str = "general",
        heuristic: str = "",
        context: Optional[Dict[str, Any]] = None,
        preconditions: Optional[List[str]] = None,
        observed_result: str = "",
        success: bool = True,
        evidence: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        procedure_id: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Registra ou atualiza um procedimento estruturado."""

        normalized_name = str(name)
        existing = self.procedures.get(normalized_name)
        now = updated_at or self._utc_now()
        entry = ProcedureEntry(
            id=procedure_id or (existing or {}).get("id") or self._next_entry_id(),
            name=normalized_name,
            domain=str(domain),
            task_type=str(task_type),
            steps=[str(step) for step in steps],
            heuristic=str(heuristic),
            context=deepcopy(context or {}),
            preconditions=[str(item) for item in (preconditions or [])],
            observed_result=str(observed_result),
            success=bool(success),
            evidence=[str(item) for item in (evidence or [])],
            created_at=created_at or (existing or {}).get("created_at") or now,
            updated_at=now,
            metadata=deepcopy(metadata or {}),
        ).to_dict()

        self.procedures[normalized_name] = entry
        if self.auto_persist:
            self._write_storage()
        return deepcopy(entry)

    def get(self, name: str) -> List[str]:
        """Retorna apenas a lista de passos para compatibilidade com codigo existente."""

        entry = self.procedures.get(str(name))
        if entry is None:
            return []
        return list(entry.get("steps", []))

    def get_entry(self, name: str) -> Optional[Dict[str, Any]]:
        """Retorna a entrada estruturada completa de um procedimento."""

        entry = self.procedures.get(str(name))
        if entry is None:
            return None
        return deepcopy(entry)

    def search(
        self,
        query: str = "",
        domain: Optional[str] = None,
        task_type: Optional[str] = None,
        success_only: bool = False,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Busca procedimentos por texto, dominio e tipo de tarefa."""

        normalized_domain = None if domain is None else str(domain)
        normalized_task_type = None if task_type is None else str(task_type)
        query_tokens = self._tokenize(query)
        ranked_entries: List[Dict[str, Any]] = []

        for entry in self.procedures.values():
            if normalized_domain is not None and entry["domain"] != normalized_domain:
                continue
            if normalized_task_type is not None and entry["task_type"] != normalized_task_type:
                continue
            if success_only and not entry["success"]:
                continue

            score = self._score_entry(
                entry=entry,
                query_tokens=query_tokens,
                domain=normalized_domain,
                task_type=normalized_task_type,
            )
            if query_tokens and score == 0:
                continue

            ranked_entries.append({"entry": entry, "score": score})

        ranked_entries.sort(
            key=lambda item: (
                -item["score"],
                not item["entry"]["success"],
                item["entry"]["updated_at"],
                item["entry"]["name"],
            )
        )

        results: List[Dict[str, Any]] = []
        for item in ranked_entries[: max(limit, 0)]:
            entry = deepcopy(item["entry"])
            entry["score"] = item["score"]
            results.append(entry)
        return results

    def get_by_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Retorna todos os procedimentos de um dominio especifico."""

        return [
            deepcopy(entry)
            for entry in self.procedures.values()
            if entry["domain"] == str(domain)
        ]

    def recent_entries(self, limit: int = 10, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retorna os procedimentos mais recentemente atualizados."""

        entries = list(self.procedures.values())
        if domain is not None:
            entries = [entry for entry in entries if entry["domain"] == str(domain)]
        entries.sort(key=lambda entry: (entry["updated_at"], entry["name"]), reverse=True)
        return [deepcopy(entry) for entry in entries[: max(limit, 0)]]

    def snapshot(self) -> Dict[str, Any]:
        """Retorna e persiste o snapshot atual da memoria procedural."""

        snapshot = self._build_snapshot()
        self._write_storage(snapshot)
        return snapshot

    def load_snapshot(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Carrega o estado da memoria procedural de um snapshot ou do arquivo em disco."""

        if snapshot is None:
            if self.storage_path is None or not self.storage_path.exists():
                self.procedures = {}
                return self._build_snapshot()
            snapshot = json.loads(self.storage_path.read_text(encoding="utf-8"))

        loaded_entries = snapshot.get("procedures", [])
        self.procedures = {
            normalized_entry["name"]: normalized_entry
            for normalized_entry in (
                self._normalize_entry(entry)
                for entry in loaded_entries
            )
        }
        return self._build_snapshot()

    def latest_updated_at(self) -> Optional[str]:
        """Retorna a data da ultima atualizacao procedural."""

        if not self.procedures:
            return None
        return max(entry["updated_at"] for entry in self.procedures.values())

    def _score_entry(
        self,
        entry: Dict[str, Any],
        query_tokens: set[str],
        domain: Optional[str],
        task_type: Optional[str],
    ) -> int:
        searchable_tokens = (
            self._tokenize(entry["name"])
            | self._tokenize(entry["heuristic"])
            | self._tokenize(" ".join(entry["steps"]))
            | self._tokenize(json.dumps(entry["context"], sort_keys=True))
            | self._tokenize(" ".join(entry["preconditions"]))
            | self._tokenize(entry["observed_result"])
            | self._tokenize(json.dumps(entry["metadata"], sort_keys=True))
        )
        query_overlap = len(query_tokens & searchable_tokens)
        domain_bonus = 5 if domain is not None and entry["domain"] == domain else 0
        task_type_bonus = 5 if task_type is not None and entry["task_type"] == task_type else 0
        success_bonus = 2 if entry["success"] else 0
        return (query_overlap * 10) + domain_bonus + task_type_bonus + success_bonus

    def _build_snapshot(self) -> Dict[str, Any]:
        procedures = sorted(
            (deepcopy(entry) for entry in self.procedures.values()),
            key=lambda entry: entry["name"],
        )
        return {
            "version": "0.1.0",
            "procedure_count": len(procedures),
            "procedures": procedures,
        }

    def _write_storage(self, snapshot: Optional[Dict[str, Any]] = None) -> None:
        if self.storage_path is None:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = snapshot or self._build_snapshot()
        self.storage_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _next_entry_id(self) -> str:
        return f"procedure-{len(self.procedures) + 1:04d}"

    @staticmethod
    def _normalize_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(entry["id"]),
            "name": str(entry["name"]),
            "domain": str(entry.get("domain", "system")),
            "task_type": str(entry.get("task_type", "general")),
            "steps": [str(step) for step in entry.get("steps", [])],
            "heuristic": str(entry.get("heuristic", "")),
            "context": deepcopy(entry.get("context", {})),
            "preconditions": [str(item) for item in entry.get("preconditions", [])],
            "observed_result": str(entry.get("observed_result", "")),
            "success": bool(entry.get("success", True)),
            "evidence": [str(item) for item in entry.get("evidence", [])],
            "created_at": str(entry["created_at"]),
            "updated_at": str(entry.get("updated_at", entry["created_at"])),
            "metadata": deepcopy(entry.get("metadata", {})),
        }

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        return set(TOKEN_PATTERN.findall(value.lower()))

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
