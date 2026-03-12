"""Bootstrap interno do runtime do Sistema Cognitivo JARVIS."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from executive_planner.audit import traduzir_estado, traduzir_motivo, traduzir_status
from runtime.autonomy import AutonomyController


class InternalAgentRuntime:
    """Inicializa o runtime funcional do sistema e coordena a execucao basica."""

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
        """Compartilha com o runtime os componentes controlados pelo planner."""

        self.planner = planner
        self.task_queue = task_queue
        self.prioritizer = prioritizer
        self.validator = validator
        self.audit_logger = audit_logger

    def bootstrap(self) -> Dict[str, Any]:
        """Inicializa o primeiro runtime funcional do sistema."""

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

        self.task_queue = self.task_queue if self.task_queue is not None else TaskQueue()
        if len(self.task_queue) == 0:
            self.task_queue.load_from_disk()
        self.task_queue.auto_persist_on_change(True)
        self.prioritizer = self.prioritizer if self.prioritizer is not None else Prioritizer()
        self.validator = self.validator if self.validator is not None else PlanValidator()
        self.audit_logger = self.audit_logger if self.audit_logger is not None else AuditLogger()

        if not self.memory:
            self.memory = {}

        self.memory.setdefault("episodic", EpisodicMemory())
        self.memory.setdefault("semantic", SemanticMemory())
        self.memory.setdefault("procedural", ProceduralMemory())

        semantic_memory = self.memory["semantic"]
        if not semantic_memory.entries and not semantic_memory.facts:
            semantic_memory.load_snapshot()
        semantic_memory.auto_persist = True

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
            "inicializado",
            domain="system",
            tags=["runtime", "estado"],
            source="runtime.bootstrap",
            importance=5,
            metadata={"status": "initialized", "status_ptbr": "inicializado"},
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
            ["planejar", "priorizar", "validar", "agendar", "executar", "revisar"],
        )
        self.memory["episodic"].remember(
            {
                "event": "bootstrap",
                "event_ptbr": "inicializar",
                "status": "initialized",
                "status_ptbr": "inicializado",
                "planner": self._planner_path(),
                "worker_count": len(self.workers),
            }
        )

        self.status = "initialized"
        return self.describe_state()

    def can_execute(self, task: Dict[str, Any]) -> bool:
        """Retorna se a tarefa pode ser executada de forma deterministica agora."""

        return self.autonomy_controller.should_execute(task)

    def dispatch_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Executa uma tarefa por meio do gate de autonomia do runtime."""

        self.bootstrap()

        if not self.can_execute(task):
            self._apply_state(task, "blocked")
            result = {
                "status": "blocked",
                "status_ptbr": traduzir_status("blocked"),
                "task": task,
                "reason": "autonomy_gate",
                "reason_ptbr": traduzir_motivo("autonomy_gate"),
            }
            self.memory["episodic"].remember(
                {
                    "event": "dispatch",
                    "event_ptbr": "despachar",
                    "status": result["status"],
                    "status_ptbr": result["status_ptbr"],
                    "task_id": task.get("task_id"),
                    "worker": task.get("worker", "runtime"),
                }
            )
            return result

        worker_id = self._normalize_worker_id(task.get("worker") or task.get("worker_id") or "runtime")
        worker = self.workers.get(worker_id)

        if worker is None:
            self._apply_state(task, "rejected")
            result = {
                "status": "rejected",
                "status_ptbr": traduzir_status("rejected"),
                "task": task,
                "reason": "unknown_worker",
                "reason_ptbr": traduzir_motivo("unknown_worker"),
                "worker": worker_id,
            }
            self.memory["episodic"].remember(
                {
                    "event": "dispatch",
                    "event_ptbr": "despachar",
                    "status": result["status"],
                    "status_ptbr": result["status_ptbr"],
                    "task_id": task.get("task_id"),
                    "worker": worker_id,
                }
            )
            return result

        worker_response = worker.handle(task)
        self._apply_state(task, "completed")
        result = {
            "status": "executed",
            "status_ptbr": traduzir_status("executed"),
            "task": task,
            "worker": worker_id,
            "worker_response": worker_response,
            "result": {
                "runtime_status": "completed",
                "runtime_status_ptbr": traduzir_status("completed"),
            },
        }
        self.memory["episodic"].remember(
            {
                "event": "dispatch",
                "event_ptbr": "despachar",
                "status": result["status"],
                "status_ptbr": result["status_ptbr"],
                "task_id": task.get("task_id"),
                "worker": worker_id,
            }
        )
        self.memory["semantic"].add_entry(
            content=self._build_completed_task_content(task, worker_id, result),
            domain=worker_id,
            tags=[worker_id, "resultado_tarefa", "concluida"],
            source="runtime.dispatch_task",
            importance=int(task.get("importance", 0)),
            metadata={
                "task_id": task.get("task_id"),
                "goal": task.get("goal"),
                "worker": worker_id,
                "dispatch_status": result["status"],
                "dispatch_status_ptbr": result["status_ptbr"],
                "runtime_status": result["result"]["runtime_status"],
                "runtime_status_ptbr": result["result"]["runtime_status_ptbr"],
            },
        )
        return result

    def enqueue_task(self, task: Dict[str, Any]) -> None:
        """Adiciona uma tarefa na fila controlada pelo runtime."""

        self.bootstrap()
        self.task_queue.enqueue(task)

    def run_planner_cycle(self) -> Dict[str, Any]:
        """Executa um ciclo do planner a partir de um runtime inicializado."""

        self.bootstrap()
        return self.planner.run_cycle()

    def query_semantic_memory(
        self, query: str, domain: str | None = None, limit: int = 5
    ) -> list[Dict[str, Any]]:
        """Consulta a memoria semantica em busca de entradas relevantes."""

        self.bootstrap()
        return self.memory["semantic"].search(query=query, domain=domain, limit=limit)

    def persist_runtime_state(self) -> Dict[str, Any]:
        """Persiste os artefatos de runtime necessarios para reinicio seguro."""

        self.bootstrap()

        queue_snapshot = None
        if self.task_queue is not None:
            queue_snapshot = self.task_queue.save_to_disk()

        semantic_snapshot = None
        semantic_memory = self.memory.get("semantic")
        if semantic_memory is not None:
            semantic_snapshot = semantic_memory.snapshot()

        return {
            "queue": deepcopy(queue_snapshot),
            "semantic_memory": deepcopy(semantic_snapshot),
        }

    def describe_state(self) -> Dict[str, Any]:
        """Retorna um snapshot leve do estado atual do runtime inicializado."""

        queue_depth = 0
        if self.task_queue is not None:
            queue_depth = len(self.task_queue.items)

        return {
            "status": self.status,
            "status_ptbr": traduzir_status(self.status),
            "default_locale": "pt-BR",
            "planner": self._planner_path(),
            "memory": "memory_system",
            "memory_modules": list(self.memory),
            "workers": [f"worker_{worker_id}" for worker_id in self.workers],
            "queue_depth": queue_depth,
            "queue_store": str(self.task_queue.storage_path) if self.task_queue is not None else None,
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
    def _apply_state(task: Dict[str, Any], state: str) -> None:
        task["state"] = state
        task["state_ptbr"] = traduzir_estado(state)

    @staticmethod
    def _build_completed_task_content(task: Dict[str, Any], worker_id: str, result: Dict[str, Any]) -> str:
        goal = task.get("goal", "Tarefa concluida")
        runtime_status = result["result"]["runtime_status_ptbr"]
        return f"{goal} concluida por {worker_id} com status de runtime {runtime_status}"
