"""Testes unitarios para o planejador executivo minimo."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from executive_planner.audit import AuditLogger
from executive_planner.planner import run_planner_cycle
from executive_planner.queue import TaskQueue
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime


def make_queue_storage_path(name: str) -> Path:
    """Retorna o path de fila usado nos testes do planner."""

    return PROJECT_ROOT / "tests" / "_queue_artifacts" / f"{name}.json"


def reset_storage_path(path: Path) -> None:
    """Limpa um arquivo persistente antes da execucao do cenario."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


def build_runtime(name: str, task_queue: TaskQueue) -> InternalAgentRuntime:
    """Monta um runtime isolado para os testes do planner."""

    semantic_storage_path = PROJECT_ROOT / "tests" / "_semantic_memory_artifacts" / f"{name}.json"
    reset_storage_path(semantic_storage_path)

    runtime = InternalAgentRuntime()
    runtime.task_queue = task_queue
    runtime.memory = {
        "episodic": EpisodicMemory(),
        "semantic": SemanticMemory(storage_path=semantic_storage_path),
        "procedural": ProceduralMemory(),
    }
    return runtime


def queue_snapshot(task_queue: TaskQueue) -> list[str]:
    """Retorna uma copia leve da fila para comparacoes nas assercoes."""

    return [str(task.get("task_id")) for task in task_queue.items]


class ExecutivePlannerCycleTests(unittest.TestCase):
    """Valida selecao, rejeicao e ociosidade do ciclo do planner."""

    def test_run_planner_cycle_executes_highest_priority_task(self) -> None:
        """Confirma execucao da tarefa de maior prioridade no ciclo."""

        storage_path = make_queue_storage_path("planner_priority")
        reset_storage_path(storage_path)
        task_queue = TaskQueue(storage_path=storage_path)
        audit_logger = AuditLogger()
        runtime = build_runtime("planner_priority", task_queue)

        task_queue.enqueue({"task_id": "task-low", "goal": "Tarefa de baixa prioridade", "impact": 1, "urgency": 1})
        task_queue.enqueue({"task_id": "task-high", "goal": "Tarefa de alta prioridade", "impact": 3, "urgency": 5})

        result = run_planner_cycle(task_queue=task_queue, audit_logger=audit_logger, runtime=runtime)

        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["status_ptbr"], "executada")
        self.assertEqual(result["selected_task"]["task_id"], "task-high")
        self.assertEqual(result["selected_task"]["state_ptbr"], "concluida")
        self.assertEqual(queue_snapshot(task_queue), ["task-low"])

        phases = [entry["event"] for entry in audit_logger.entries]
        fases_ptbr = [entry["event_ptbr"] for entry in audit_logger.entries]
        self.assertEqual(phases, ["plan", "prioritize", "prioritize", "validate", "validate", "schedule", "schedule", "execute", "review"])
        self.assertEqual(fases_ptbr, ["planejar", "priorizar", "priorizar", "validar", "validar", "agendar", "agendar", "executar", "revisar"])

    def test_run_planner_cycle_skips_invalid_and_blocked_tasks(self) -> None:
        """Verifica rejeicao de invalidas e reenvio das bloqueadas."""

        storage_path = make_queue_storage_path("planner_blocked")
        reset_storage_path(storage_path)
        task_queue = TaskQueue(storage_path=storage_path)
        audit_logger = AuditLogger()
        runtime = build_runtime("planner_blocked", task_queue)

        task_queue.enqueue({"task_id": "task-invalid", "impact": 5, "urgency": 5})
        task_queue.enqueue(
            {
                "task_id": "task-blocked",
                "goal": "Precisa de supervisao",
                "impact": 4,
                "urgency": 0,
                "requires_supervision": True,
                "approved": False,
            }
        )
        task_queue.enqueue({"task_id": "task-ready", "goal": "Tarefa pronta", "impact": 1, "urgency": 1})

        result = run_planner_cycle(task_queue=task_queue, audit_logger=audit_logger, runtime=runtime)

        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["status_ptbr"], "executada")
        self.assertEqual(result["selected_task"]["task_id"], "task-ready")
        self.assertEqual(len(result["rejected_tasks"]), 1)
        self.assertEqual(result["rejected_tasks"][0]["task"]["task_id"], "task-invalid")
        self.assertEqual(result["rejected_tasks"][0]["task"]["state_ptbr"], "rejeitada")
        self.assertEqual(queue_snapshot(task_queue), ["task-blocked"])

        schedule_entries = [entry for entry in audit_logger.entries if entry["event"] == "schedule"]
        self.assertEqual(schedule_entries[0]["payload"]["decision"], "blocked")
        self.assertEqual(schedule_entries[0]["payload"]["decision_ptbr"], "bloqueada")
        self.assertEqual(schedule_entries[0]["payload"]["task_id"], "task-blocked")

    def test_run_planner_cycle_is_idle_when_queue_is_empty(self) -> None:
        """Confirma ociosidade correta quando a fila nao contem tarefas."""

        storage_path = make_queue_storage_path("planner_idle")
        reset_storage_path(storage_path)
        task_queue = TaskQueue(storage_path=storage_path)
        audit_logger = AuditLogger()
        runtime = build_runtime("planner_idle", task_queue)

        result = run_planner_cycle(task_queue=task_queue, audit_logger=audit_logger, runtime=runtime)

        self.assertEqual(result["status"], "idle")
        self.assertEqual(result["status_ptbr"], "ociosa")
        self.assertEqual(result["reason"], "no_tasks")
        self.assertEqual(result["reason_ptbr"], "sem_tarefas")
        self.assertIsNone(result["selected_task"])
        self.assertEqual(queue_snapshot(task_queue), [])
        self.assertEqual([entry["event"] for entry in audit_logger.entries], ["plan", "review"])
        self.assertEqual([entry["event_ptbr"] for entry in audit_logger.entries], ["planejar", "revisar"])


if __name__ == "__main__":
    unittest.main()
