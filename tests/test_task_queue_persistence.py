"""Testes unitarios para a fila persistente de tarefas."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from executive_planner.audit import AuditLogger
from executive_planner.queue import TaskQueue
from executive_planner.planner import ExecutivePlanner
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime


def make_storage_path(name: str) -> Path:
    """Retorna o path persistente usado nos testes da fila."""

    return PROJECT_ROOT / "tests" / "_queue_artifacts" / f"{name}.json"


def make_semantic_storage_path(name: str) -> Path:
    """Retorna o path de memoria semantica usado nos cenarios da fila."""

    return PROJECT_ROOT / "tests" / "_semantic_memory_artifacts" / f"{name}.json"


def make_audit_storage_path(name: str) -> Path:
    """Retorna o path de auditoria usado nos cenarios da fila."""

    return PROJECT_ROOT / "tests" / "_audit_artifacts" / f"{name}.json"


def reset_storage_path(path: Path) -> None:
    """Limpa o arquivo persistente antes da execucao do cenario."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class TaskQueuePersistenceTests(unittest.TestCase):
    """Valida roundtrip, recuperacao e consistencia da fila persistente."""

    def test_queue_persistence_roundtrip(self) -> None:
        """Confirma serializacao e restauracao completa de uma fila em disco."""

        storage_path = make_storage_path("queue_roundtrip")
        reset_storage_path(storage_path)

        queue = TaskQueue(storage_path=storage_path)
        queue.enqueue(
            {
                "task_id": "queue-1",
                "description": "Preparar briefing financeiro",
                "domain": "finance",
                "urgency": 3,
                "impact": 5,
                "cost": 2,
                "reversibility": 4,
                "risk": 1,
                "approval": {"approved": True, "requires_supervision": False},
                "state": "queued",
                "evidence": ["snapshot_orcamento"],
                "parent_goal": "Melhorar visibilidade financeira",
                "timestamps": {
                    "created_at": "2026-03-12T00:00:00+00:00",
                    "updated_at": "2026-03-12T00:00:00+00:00",
                    "queued_at": "2026-03-12T00:00:00+00:00",
                },
            }
        )

        snapshot = queue.save_to_disk()
        restored_queue = TaskQueue(storage_path=storage_path)
        restored_snapshot = restored_queue.load_from_disk()
        restored_task = restored_queue.dequeue()

        self.assertEqual(snapshot["task_count"], 1)
        self.assertEqual(restored_snapshot["task_count"], 1)
        self.assertEqual(restored_task["task_id"], "queue-1")
        self.assertEqual(restored_task["description"], "Preparar briefing financeiro")
        self.assertEqual(restored_task["domain"], "finance")
        self.assertEqual(restored_task["impact"], 5)
        self.assertEqual(restored_task["approval"]["approved"], True)
        self.assertEqual(restored_task["state_ptbr"], "na_fila")
        self.assertEqual(restored_task["evidence"], ["snapshot_orcamento"])
        self.assertEqual(restored_task["parent_goal"], "Melhorar visibilidade financeira")
        self.assertEqual(restored_task["timestamps"]["queued_at"], "2026-03-12T00:00:00+00:00")

    def test_runtime_bootstrap_recovers_persisted_queue(self) -> None:
        """Verifica que o runtime recarrega a fila persistida no bootstrap."""

        storage_path = make_storage_path("runtime_recovery")
        semantic_storage_path = make_semantic_storage_path("runtime_recovery")
        audit_storage_path = make_audit_storage_path("runtime_recovery")
        reset_storage_path(storage_path)
        reset_storage_path(semantic_storage_path)
        reset_storage_path(audit_storage_path)

        persisted_queue = TaskQueue(storage_path=storage_path)
        persisted_queue.enqueue(
            {
                "task_id": "recover-1",
                "goal": "Recuperar tarefa enfileirada",
                "description": "Recuperar tarefa enfileirada",
                "domain": "runtime",
                "urgency": 2,
                "impact": 4,
                "approval": {"approved": True, "requires_supervision": False},
                "state": "queued",
                "evidence": [],
                "parent_goal": "Recuperacao do sistema",
            }
        )
        persisted_queue.save_to_disk()

        runtime = InternalAgentRuntime()
        runtime.task_queue = TaskQueue(storage_path=storage_path)
        runtime.audit_logger = AuditLogger(storage_path=audit_storage_path)
        runtime.memory = {
            "episodic": EpisodicMemory(),
            "semantic": SemanticMemory(storage_path=semantic_storage_path),
            "procedural": ProceduralMemory(),
        }

        state = runtime.bootstrap()

        self.assertEqual(state["status"], "initialized")
        self.assertEqual(state["status_ptbr"], "inicializado")
        self.assertEqual(state["queue_depth"], 1)
        self.assertEqual(runtime.task_queue.items[0]["task_id"], "recover-1")
        self.assertEqual(runtime.task_queue.items[0]["state"], "queued")
        self.assertEqual(runtime.task_queue.items[0]["state_ptbr"], "na_fila")

    def test_state_consistency_after_reload(self) -> None:
        """Garante preservacao de estado e aprovacao apos recarga da fila."""

        storage_path = make_storage_path("state_consistency")
        reset_storage_path(storage_path)

        queue = TaskQueue(storage_path=storage_path)
        queue.enqueue(
            {
                "task_id": "state-1",
                "goal": "Validar estado da fila",
                "description": "Validar estado da fila",
                "domain": "study",
                "urgency": 1,
                "impact": 2,
                "cost": 1,
                "reversibility": 3,
                "risk": 1,
                "approval": {"approved": False, "requires_supervision": True},
                "state": "blocked",
                "evidence": ["revisao_de_politica"],
                "parent_goal": "Estudar com seguranca",
                "timestamps": {
                    "created_at": "2026-03-12T01:00:00+00:00",
                    "updated_at": "2026-03-12T01:15:00+00:00",
                    "queued_at": "2026-03-12T01:00:00+00:00",
                },
            }
        )
        queue.auto_persist_on_change(True)
        queue.save_to_disk()

        reloaded_queue = TaskQueue(storage_path=storage_path)
        reloaded_queue.load_from_disk()

        self.assertEqual(len(reloaded_queue), 1)
        self.assertEqual(reloaded_queue.items[0]["state"], "blocked")
        self.assertEqual(reloaded_queue.items[0]["state_ptbr"], "bloqueada")
        self.assertEqual(reloaded_queue.items[0]["approval"]["requires_supervision"], True)
        self.assertEqual(reloaded_queue.items[0]["cost"], 1)
        self.assertEqual(reloaded_queue.items[0]["risk"], 1)
        self.assertEqual(reloaded_queue.items[0]["timestamps"]["updated_at"], "2026-03-12T01:15:00+00:00")

    def test_task_is_not_lost_when_cycle_fails_before_commit(self) -> None:
        """Garante que a fila preserve a tarefa se o ciclo falhar antes do commit final."""

        class CrashingRuntime(InternalAgentRuntime):
            def can_execute(self, task: dict[str, object]) -> bool:
                return True

            def dispatch_task(self, task: dict[str, object]) -> dict[str, object]:
                raise RuntimeError("falha_antes_do_commit")

        storage_path = make_storage_path("no_loss_on_failure")
        reset_storage_path(storage_path)

        queue = TaskQueue(storage_path=storage_path)
        queue.auto_persist_on_change(True)
        queue.enqueue(
            {
                "task_id": "safe-1",
                "goal": "Preservar tarefa em falha",
                "description": "Preservar tarefa em falha",
                "domain": "runtime",
                "worker": "worker_runtime",
                "impact": 2,
                "urgency": 2,
            }
        )

        planner = ExecutivePlanner(task_queue=queue, runtime=CrashingRuntime())

        with self.assertRaises(RuntimeError):
            planner.run_cycle()

        reloaded_queue = TaskQueue(storage_path=storage_path)
        reloaded_queue.load_from_disk()

        self.assertEqual(len(reloaded_queue), 1)
        self.assertEqual(reloaded_queue.items[0]["task_id"], "safe-1")


if __name__ == "__main__":
    unittest.main()
