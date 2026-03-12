"""Primitivos de fila persistente para o planejador executivo."""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from executive_planner.audit import traduzir_estado

DEFAULT_STORAGE_PATH = Path(__file__).with_name("task_queue_store.json")


@dataclass
class TaskQueue:
    """Fila FIFO de tarefas com persistencia deterministica em disco."""

    items: Deque[Dict[str, Any]] = field(default_factory=deque)
    storage_path: Path = field(default_factory=lambda: DEFAULT_STORAGE_PATH)
    auto_persist: bool = False

    def __post_init__(self) -> None:
        self.storage_path = Path(self.storage_path)

    def enqueue(self, task: Dict[str, Any]) -> Dict[str, Any]:
        normalized_task = self._normalize_task(task, default_state="queued")
        self.items.append(normalized_task)

        if self.auto_persist:
            self.save_to_disk()

        return deepcopy(normalized_task)

    def dequeue(self) -> Optional[Dict[str, Any]]:
        if not self.items:
            return None

        task = self.items.popleft()
        task = self._normalize_task(task, default_state=task.get("state", "queued"))

        if self.auto_persist:
            self.save_to_disk()

        return deepcopy(task)

    def drain(self) -> List[Dict[str, Any]]:
        tasks = [deepcopy(task) for task in self.items]
        self.items.clear()

        if self.auto_persist:
            self.save_to_disk()

        return tasks

    def save_to_disk(self) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        return snapshot

    def load_from_disk(self) -> Dict[str, Any]:
        if not self.storage_path.exists():
            self.items = deque()
            return self._build_snapshot(saved_at=None)

        snapshot = json.loads(self.storage_path.read_text(encoding="utf-8"))
        loaded_tasks = snapshot.get("tasks", [])
        self.items = deque(self._normalize_task(task) for task in loaded_tasks)
        return self._build_snapshot(saved_at=snapshot.get("saved_at"))

    def auto_persist_on_change(self, enabled: bool = True) -> None:
        self.auto_persist = enabled

    def __len__(self) -> int:
        return len(self.items)

    def _build_snapshot(self, saved_at: Optional[str] = None) -> Dict[str, Any]:
        return {
            "version": "0.1.0",
            "task_count": len(self.items),
            "saved_at": saved_at or self._utc_now(),
            "tasks": [deepcopy(task) for task in self.items],
        }

    def _normalize_task(
        self,
        task: Dict[str, Any],
        default_state: str = "queued",
    ) -> Dict[str, Any]:
        normalized = deepcopy(task)
        now = self._utc_now()

        task_id = normalized.get("task_id", normalized.get("id"))
        if task_id is not None:
            normalized["task_id"] = str(task_id)

        description = str(normalized.get("description") or normalized.get("goal") or "")
        parent_goal = str(normalized.get("parent_goal") or normalized.get("goal") or description)
        domain = str(
            normalized.get("domain")
            or normalized.get("worker")
            or normalized.get("worker_id")
            or "general"
        )

        approval = normalized.get("approval", {})
        if not isinstance(approval, dict):
            approval = {}

        approved = bool(approval.get("approved", normalized.get("approved", True)))
        requires_supervision = bool(
            approval.get("requires_supervision", normalized.get("requires_supervision", False))
        )

        evidence = normalized.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [evidence]

        timestamps = normalized.get("timestamps", {})
        if not isinstance(timestamps, dict):
            timestamps = {}

        created_at = str(normalized.get("created_at") or timestamps.get("created_at") or now)
        updated_at = str(normalized.get("updated_at") or timestamps.get("updated_at") or created_at)
        queued_at = str(normalized.get("queued_at") or timestamps.get("queued_at") or created_at)
        state = str(normalized.get("state", default_state))

        normalized.update(
            {
                "description": description,
                "goal": str(normalized.get("goal") or description or parent_goal),
                "domain": domain,
                "urgency": int(normalized.get("urgency", 0)),
                "impact": int(normalized.get("impact", normalized.get("importance", 0))),
                "importance": int(normalized.get("importance", normalized.get("impact", 0))),
                "cost": int(normalized.get("cost", 0)),
                "reversibility": int(normalized.get("reversibility", 0)),
                "risk": int(normalized.get("risk", 0)),
                "approval": {
                    "approved": approved,
                    "requires_supervision": requires_supervision,
                },
                "approved": approved,
                "requires_supervision": requires_supervision,
                "state": state,
                "state_ptbr": traduzir_estado(state),
                "evidence": deepcopy(evidence),
                "parent_goal": parent_goal,
                "timestamps": {
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "queued_at": queued_at,
                },
                "created_at": created_at,
                "updated_at": updated_at,
                "queued_at": queued_at,
            }
        )
        return normalized

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
