"""Gerenciamento persistente de metas estrategicas e objetivos ativos."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_GOALS_PATH = Path(__file__).with_name("goals.json")

GOAL_STATE_PTBR = {
    "draft": "rascunho",
    "active": "ativa",
    "blocked": "bloqueada",
    "completed": "concluida",
    "archived": "arquivada",
}

GOAL_KIND_PTBR = {
    "strategic": "meta_estrategica",
    "active": "objetivo_ativo",
}


@dataclass
class GoalManager:
    """Mantem metas estrategicas e objetivos ativos com persistencia local."""

    storage_path: Path = field(default_factory=lambda: DEFAULT_GOALS_PATH)
    auto_persist: bool = True
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.storage_path = Path(self.storage_path)
        self.load()

    def load(self) -> Dict[str, Any]:
        """Carrega o arquivo de metas do disco."""

        if not self.storage_path.exists():
            self.data = self._default_snapshot()
            return self.snapshot()

        snapshot = json.loads(self.storage_path.read_text(encoding="utf-8"))
        self.data = self._normalize_snapshot(snapshot)
        return self.snapshot()

    def save(self) -> Dict[str, Any]:
        """Persiste o estado atual do gerenciador."""

        snapshot = self._normalize_snapshot(self.data)
        snapshot["updated_at"] = self._utc_now()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        self.data = snapshot
        return self.snapshot()

    def snapshot(self) -> Dict[str, Any]:
        """Retorna um snapshot seguro do estado atual."""

        return deepcopy(self._normalize_snapshot(self.data or self._default_snapshot()))

    def add_strategic_goal(
        self,
        title: str,
        description: str = "",
        priority: int = 0,
        deadline: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Adiciona uma meta estrategica persistida."""

        goal = self._build_goal(
            kind="strategic",
            title=title,
            description=description,
            priority=priority,
            deadline=deadline,
            state="draft",
            metadata=metadata,
        )
        self.data["strategic_goals"].append(goal)
        self._persist_if_needed()
        return deepcopy(goal)

    def add_active_goal(
        self,
        title: str,
        description: str = "",
        priority: int = 0,
        deadline: Optional[str] = None,
        state: str = "active",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Adiciona um objetivo ativo persistido."""

        goal = self._build_goal(
            kind="active",
            title=title,
            description=description,
            priority=priority,
            deadline=deadline,
            state=state,
            metadata=metadata,
        )
        self.data["active_goals"].append(goal)
        self._persist_if_needed()
        return deepcopy(goal)

    def list_strategic_goals(self) -> List[Dict[str, Any]]:
        """Retorna as metas estrategicas cadastradas."""

        return deepcopy(self.data["strategic_goals"])

    def list_active_goals(self) -> List[Dict[str, Any]]:
        """Retorna os objetivos ativos cadastrados."""

        return deepcopy(self.data["active_goals"])

    def get_goal(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """Recupera uma meta ou objetivo por identificador."""

        goal_ref = self._find_goal_ref(goal_id)
        if goal_ref is None:
            return None
        return deepcopy(goal_ref["goal"])

    def link_task_to_goal(self, task: Dict[str, Any], goal_id: str) -> Dict[str, Any]:
        """Vincula uma tarefa a um objetivo ativo e propaga seu contexto."""

        goal_ref = self._find_goal_ref(goal_id)
        if goal_ref is None:
            raise ValueError(f"Objetivo nao encontrado: {goal_id}")

        goal = goal_ref["goal"]
        if goal["kind"] != "active":
            raise ValueError("Apenas objetivos ativos podem receber tarefas vinculadas.")

        linked_task = deepcopy(task)
        task_id = linked_task.get("task_id")
        if task_id is not None and str(task_id) not in goal["task_ids"]:
            goal["task_ids"].append(str(task_id))

        linked_task["parent_goal_id"] = goal["goal_id"]
        linked_task["parent_goal"] = goal["title"]
        linked_task["goal_priority"] = goal["priority"]
        linked_task["goal_state"] = goal["state"]
        goal["updated_at"] = self._utc_now()
        goal["progress"] = self._calculate_progress(goal)
        self._persist_if_needed()
        return linked_task

    def record_task_result(self, task: Dict[str, Any], result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Atualiza o progresso do objetivo associado apos uma execucao."""

        goal_id = task.get("parent_goal_id")
        if goal_id is None:
            return None

        goal_ref = self._find_goal_ref(str(goal_id))
        if goal_ref is None:
            return None

        goal = goal_ref["goal"]
        task_id = task.get("task_id")
        if task_id is not None and str(task_id) not in goal["task_ids"]:
            goal["task_ids"].append(str(task_id))

        status = str(result.get("status", ""))
        if status == "executed" and task_id is not None and str(task_id) not in goal["completed_task_ids"]:
            goal["completed_task_ids"].append(str(task_id))

        goal["progress"] = self._calculate_progress(goal)
        goal["last_result"] = status
        goal["updated_at"] = self._utc_now()

        if status == "blocked":
            goal["state"] = "blocked"
        elif goal["progress"] >= 100 and goal["task_ids"]:
            goal["state"] = "completed"
        elif goal["kind"] == "active":
            goal["state"] = "active"

        self._persist_if_needed()
        return self.goal_report(str(goal_id))

    def goal_report(self, goal_id: Optional[str] = None) -> Dict[str, Any]:
        """Retorna um relatorio em pt-BR de um objetivo ou do conjunto de metas."""

        if goal_id is not None:
            goal = self.get_goal(goal_id)
            if goal is None:
                raise ValueError(f"Objetivo nao encontrado: {goal_id}")
            return self._build_goal_report(goal)

        strategic_goals = [self._build_goal_report(goal) for goal in self.data["strategic_goals"]]
        active_goals = [self._build_goal_report(goal) for goal in self.data["active_goals"]]

        return {
            "metas_estrategicas": strategic_goals,
            "objetivos_ativos": active_goals,
            "resumo": {
                "total_metas_estrategicas": len(strategic_goals),
                "total_objetivos_ativos": len(active_goals),
                "objetivos_concluidos": len([goal for goal in active_goals if goal["estado"] == "completed"]),
            },
        }

    def _persist_if_needed(self) -> None:
        if self.auto_persist:
            self.save()

    def _build_goal(
        self,
        kind: str,
        title: str,
        description: str,
        priority: int,
        deadline: Optional[str],
        state: str,
        metadata: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        now = self._utc_now()
        return {
            "goal_id": self._next_goal_id(),
            "kind": kind,
            "title": str(title),
            "description": str(description),
            "state": state,
            "priority": int(priority),
            "deadline": deadline,
            "progress": 0,
            "task_ids": [],
            "completed_task_ids": [],
            "created_at": now,
            "updated_at": now,
            "metadata": deepcopy(metadata or {}),
            "last_result": None,
        }

    def _build_goal_report(self, goal: Dict[str, Any]) -> Dict[str, Any]:
        state = goal["state"]
        kind = goal["kind"]
        task_count = len(goal["task_ids"])
        completed_count = len(goal["completed_task_ids"])

        return {
            "goal_id": goal["goal_id"],
            "titulo": goal["title"],
            "descricao": goal["description"],
            "tipo": GOAL_KIND_PTBR.get(kind, kind),
            "estado": state,
            "estado_ptbr": GOAL_STATE_PTBR.get(state, state),
            "prioridade": goal["priority"],
            "prazo": goal["deadline"],
            "progresso": goal["progress"],
            "tarefas_vinculadas": task_count,
            "tarefas_concluidas": completed_count,
            "ultimo_resultado": goal.get("last_result"),
            "resumo": f"{goal['title']} com {goal['progress']}% de progresso.",
        }

    def _find_goal_ref(self, goal_id: str) -> Optional[Dict[str, Any]]:
        for collection_name in ("strategic_goals", "active_goals"):
            for index, goal in enumerate(self.data[collection_name]):
                if goal["goal_id"] == goal_id:
                    return {
                        "collection": collection_name,
                        "index": index,
                        "goal": goal,
                    }
        return None

    def _normalize_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._default_snapshot()
        normalized["constraints"] = list(snapshot.get("constraints", []))
        normalized["preferences"] = deepcopy(snapshot.get("preferences", {}))
        normalized["preferences"].setdefault("default_locale", "pt-BR")
        normalized["updated_at"] = str(snapshot.get("updated_at") or self._utc_now())
        normalized["strategic_goals"] = [
            self._normalize_goal(goal, kind="strategic") for goal in snapshot.get("strategic_goals", [])
        ]
        normalized["active_goals"] = [
            self._normalize_goal(goal, kind="active") for goal in snapshot.get("active_goals", [])
        ]
        return normalized

    def _normalize_goal(self, goal: Dict[str, Any], kind: str) -> Dict[str, Any]:
        task_ids = self._normalize_string_list(goal.get("task_ids", []))
        completed_task_ids = self._normalize_string_list(goal.get("completed_task_ids", []))
        created_at = str(goal.get("created_at") or self._utc_now())
        updated_at = str(goal.get("updated_at") or created_at)
        progress = int(goal.get("progress", self._calculate_progress({"task_ids": task_ids, "completed_task_ids": completed_task_ids})))

        return {
            "goal_id": str(goal.get("goal_id") or goal.get("id") or self._next_goal_id()),
            "kind": kind,
            "title": str(goal.get("title") or goal.get("goal") or ""),
            "description": str(goal.get("description") or ""),
            "state": str(goal.get("state") or ("active" if kind == "active" else "draft")),
            "priority": int(goal.get("priority", 0)),
            "deadline": goal.get("deadline"),
            "progress": progress,
            "task_ids": task_ids,
            "completed_task_ids": completed_task_ids,
            "created_at": created_at,
            "updated_at": updated_at,
            "metadata": deepcopy(goal.get("metadata", {})),
            "last_result": goal.get("last_result"),
        }

    def _next_goal_id(self) -> str:
        current_total = len(self.data.get("strategic_goals", [])) + len(self.data.get("active_goals", []))
        return f"goal-{current_total + 1:04d}"

    @staticmethod
    def _normalize_string_list(values: List[Any]) -> List[str]:
        normalized: List[str] = []
        seen: set[str] = set()

        for value in values:
            normalized_value = str(value)
            if normalized_value in seen:
                continue
            normalized.append(normalized_value)
            seen.add(normalized_value)

        return normalized

    @staticmethod
    def _calculate_progress(goal: Dict[str, Any]) -> int:
        task_ids = goal.get("task_ids", [])
        completed_task_ids = goal.get("completed_task_ids", [])
        if not task_ids:
            return int(goal.get("progress", 0))
        return int((len(completed_task_ids) / len(task_ids)) * 100)

    @staticmethod
    def _default_snapshot() -> Dict[str, Any]:
        return {
            "strategic_goals": [],
            "active_goals": [],
            "constraints": [],
            "preferences": {
                "default_locale": "pt-BR",
                "autonomy_level": "supervisionado",
                "response_style": "direto",
                "tone": "tecnico",
            },
            "updated_at": GoalManager._utc_now(),
        }

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
