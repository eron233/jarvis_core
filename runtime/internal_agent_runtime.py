"""Internal runtime bootstrap for the JARVIS cognitive system."""

from __future__ import annotations

from typing import Any, Dict

from runtime.autonomy import AutonomyController


class InternalAgentRuntime:
    """Bootstraps the initial runtime state for orchestration."""

    def __init__(self, autonomy_controller: AutonomyController | None = None) -> None:
        self.autonomy_controller = autonomy_controller or AutonomyController()
        self.status = "cold"
        self.task_queue: Any = None
        self.prioritizer: Any = None
        self.validator: Any = None
        self.audit_logger: Any = None
        self.planner: Any = None
        self.memory: Dict[str, Any] = {}
        self.workers: Dict[str, Any] = {}

    def attach_planner(
        self,
        planner: Any,
        task_queue: Any,
        prioritizer: Any,
        validator: Any,
        audit_logger: Any,
    ) -> None:
        """Shares planner-owned components with the runtime."""

        self.planner = planner
        self.task_queue = task_queue
        self.prioritizer = prioritizer
        self.validator = validator
        self.audit_logger = audit_logger

    def bootstrap(self) -> Dict[str, Any]:
        """Initializes the first functional system runtime."""

        if self.status == "initialized":
            return self.describe_state()

        from executive_planner.audit import AuditLogger
        from executive_planner.planner import ExecutivePlanner
        from executive_planner.prioritizer import Prioritizer
        from executive_planner.queue import TaskQueue
        from executive_planner.validator import PlanValidator
        from memory_system.episodic_memory import EpisodicMemory
        from memory_system.procedural_memory import ProceduralMemory
        from memory_system.semantic_memory import SemanticMemory
        from workers.worker_finance import FinanceWorker
        from workers.worker_runtime import RuntimeWorker
        from workers.worker_studio import StudioWorker
        from workers.worker_study import StudyWorker

        self.task_queue = self.task_queue or TaskQueue()
        self.prioritizer = self.prioritizer or Prioritizer()
        self.validator = self.validator or PlanValidator()
        self.audit_logger = self.audit_logger or AuditLogger()

        if not self.memory:
            self.memory = {
                "episodic": EpisodicMemory(),
                "semantic": SemanticMemory(),
                "procedural": ProceduralMemory(),
            }

        if not self.workers:
            self.workers = {
                "runtime": RuntimeWorker(),
                "finance": FinanceWorker(),
                "studio": StudioWorker(),
                "study": StudyWorker(),
            }

        if self.planner is None:
            self.planner = ExecutivePlanner(
                task_queue=self.task_queue,
                prioritizer=self.prioritizer,
                validator=self.validator,
                audit_logger=self.audit_logger,
                runtime=self,
            )

        self.memory["semantic"].upsert(
            "runtime_status",
            "initialized",
            domain="system",
            tags=["runtime", "status"],
            source="runtime.bootstrap",
            importance=5,
            metadata={"status": "initialized"},
        )
        self.memory["semantic"].upsert(
            "registered_workers",
            list(self.workers),
            domain="system",
            tags=["runtime", "workers"],
            source="runtime.bootstrap",
            importance=4,
            metadata={"worker_ids": list(self.workers)},
        )
        self.memory["procedural"].register(
            "planner_cycle",
            ["plan", "prioritize", "validate", "schedule", "execute", "review"],
        )
        self.memory["episodic"].remember(
            {
                "event": "bootstrap",
                "status": "initialized",
                "planner": self._planner_path(),
                "worker_count": len(self.workers),
            }
        )

        self.status = "initialized"
        return self.describe_state()

    def can_execute(self, task: Dict[str, Any]) -> bool:
        """Returns whether the runtime can deterministically execute the task now."""

        return self.autonomy_controller.should_execute(task)

    def dispatch_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a task through the runtime's autonomy gate."""

        self.bootstrap()

        if not self.can_execute(task):
            result = {
                "status": "blocked",
                "task": task,
                "reason": "autonomy_gate",
            }
            self.memory["episodic"].remember(
                {
                    "event": "dispatch",
                    "status": result["status"],
                    "task_id": task.get("task_id"),
                    "worker": task.get("worker", "runtime"),
                }
            )
            return result

        worker_id = self._normalize_worker_id(task.get("worker") or task.get("worker_id") or "runtime")
        worker = self.workers.get(worker_id)

        if worker is None:
            result = {
                "status": "rejected",
                "task": task,
                "reason": "unknown_worker",
                "worker": worker_id,
            }
            self.memory["episodic"].remember(
                {
                    "event": "dispatch",
                    "status": result["status"],
                    "task_id": task.get("task_id"),
                    "worker": worker_id,
                }
            )
            return result

        worker_response = worker.handle(task)
        result = {
            "status": "executed",
            "task": task,
            "worker": worker_id,
            "worker_response": worker_response,
            "result": {
                "runtime_status": "completed",
            },
        }
        self.memory["episodic"].remember(
            {
                "event": "dispatch",
                "status": result["status"],
                "task_id": task.get("task_id"),
                "worker": worker_id,
            }
        )
        self.memory["semantic"].add_entry(
            content=self._build_completed_task_content(task, worker_id, result),
            domain=worker_id,
            tags=[worker_id, "task_result", "completed"],
            source="runtime.dispatch_task",
            importance=int(task.get("importance", 0)),
            metadata={
                "task_id": task.get("task_id"),
                "goal": task.get("goal"),
                "worker": worker_id,
                "dispatch_status": result["status"],
                "runtime_status": result["result"]["runtime_status"],
            },
        )
        return result

    def enqueue_task(self, task: Dict[str, Any]) -> None:
        """Adds a task to the runtime-owned planner queue."""

        self.bootstrap()
        self.task_queue.enqueue(task)

    def run_planner_cycle(self) -> Dict[str, Any]:
        """Runs one planner cycle from a fully bootstrapped runtime."""

        self.bootstrap()
        return self.planner.run_cycle()

    def query_semantic_memory(
        self, query: str, domain: str | None = None, limit: int = 5
    ) -> list[Dict[str, Any]]:
        """Queries semantic memory for relevant entries."""

        self.bootstrap()
        return self.memory["semantic"].search(query=query, domain=domain, limit=limit)

    def describe_state(self) -> Dict[str, Any]:
        """Returns a lightweight snapshot of the bootstrapped runtime."""

        queue_depth = 0
        if self.task_queue is not None:
            queue_depth = len(self.task_queue.items)

        return {
            "status": self.status,
            "planner": self._planner_path(),
            "memory": "memory_system",
            "memory_modules": list(self.memory),
            "workers": [f"worker_{worker_id}" for worker_id in self.workers],
            "queue_depth": queue_depth,
        }

    def _planner_path(self) -> str:
        if self.planner is None:
            return "executive_planner.planner.ExecutivePlanner"
        return f"{self.planner.__class__.__module__}.{self.planner.__class__.__name__}"

    @staticmethod
    def _normalize_worker_id(worker_id: str) -> str:
        if worker_id.startswith("worker_"):
            return worker_id[len("worker_") :]
        return worker_id

    @staticmethod
    def _build_completed_task_content(task: Dict[str, Any], worker_id: str, result: Dict[str, Any]) -> str:
        goal = task.get("goal", "Task completed")
        runtime_status = result["result"]["runtime_status"]
        return f"{goal} completed by {worker_id} with runtime status {runtime_status}"
