"""Testes unitarios para o loop continuo inicial do JARVIS."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from executive_planner.queue import TaskQueue
from main import JarvisSystemLoop, SystemLoopConfig, bootstrap_runtime
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime


def make_queue_storage_path(name: str) -> Path:
    return PROJECT_ROOT / "tests" / "_main_loop_artifacts" / f"{name}_queue.json"


def make_semantic_storage_path(name: str) -> Path:
    return PROJECT_ROOT / "tests" / "_main_loop_artifacts" / f"{name}_semantic.json"


def reset_storage_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class MainLoopTests(unittest.TestCase):
    def test_bootstrap_runtime_loads_queue_and_semantic_memory(self) -> None:
        queue_storage_path = make_queue_storage_path("bootstrap")
        semantic_storage_path = make_semantic_storage_path("bootstrap")
        reset_storage_path(queue_storage_path)
        reset_storage_path(semantic_storage_path)

        queue = TaskQueue(storage_path=queue_storage_path)
        queue.enqueue(
            {
                "task_id": "bootstrap-1",
                "goal": "Recarregar tarefa persistida",
                "domain": "runtime",
                "worker": "worker_runtime",
                "impact": 1,
                "urgency": 1,
            }
        )
        queue.save_to_disk()

        semantic_memory = SemanticMemory(storage_path=semantic_storage_path)
        semantic_memory.add_entry(
            content="Memoria persistida de bootstrap",
            domain="system",
            tags=["bootstrap", "memoria"],
            source="unit-test",
            importance=3,
            metadata={"kind": "bootstrap"},
        )
        semantic_memory.snapshot()

        runtime, state = bootstrap_runtime(
            runtime=InternalAgentRuntime(),
            config=SystemLoopConfig(
                queue_storage_path=queue_storage_path,
                semantic_storage_path=semantic_storage_path,
                install_signal_handlers=False,
            ),
        )

        self.assertEqual(state["status"], "initialized")
        self.assertEqual(state["queue_depth"], 1)
        self.assertEqual(runtime.task_queue.items[0]["task_id"], "bootstrap-1")
        self.assertEqual(runtime.query_semantic_memory("memoria persistida", domain="system")[0]["domain"], "system")

    def test_loop_minimo_para_em_fila_vazia_sem_erro(self) -> None:
        logs: list[str] = []
        loop = JarvisSystemLoop(
            config=SystemLoopConfig(
                cycle_sleep_seconds=0,
                idle_sleep_seconds=0,
                max_cycles=1,
                stop_when_idle=True,
                install_signal_handlers=False,
                queue_storage_path=make_queue_storage_path("idle"),
                semantic_storage_path=make_semantic_storage_path("idle"),
            ),
            logger=logs.append,
        )
        reset_storage_path(loop.config.queue_storage_path)
        reset_storage_path(loop.config.semantic_storage_path)

        summary = loop.run()

        self.assertEqual(summary["completed_cycles"], 1)
        self.assertEqual(summary["shutdown_reason"], "idle_queue")
        self.assertEqual(summary["shutdown_reason_ptbr"], "fila_vazia")
        self.assertEqual(summary["runtime_state"]["queue_depth"], 0)
        self.assertEqual(summary["cycle_logs"][0]["status"], "idle")
        self.assertTrue(any("[ciclo 1]" in line for line in logs))

    def test_restart_recovers_blocked_queue_state(self) -> None:
        queue_storage_path = make_queue_storage_path("restart")
        semantic_storage_path = make_semantic_storage_path("restart")
        reset_storage_path(queue_storage_path)
        reset_storage_path(semantic_storage_path)

        queue = TaskQueue(storage_path=queue_storage_path)
        queue.enqueue(
            {
                "task_id": "blocked-1",
                "goal": "Aguardar aprovacao humana",
                "description": "Aguardar aprovacao humana",
                "domain": "runtime",
                "worker": "worker_runtime",
                "impact": 2,
                "urgency": 2,
                "approval": {"approved": False, "requires_supervision": True},
            }
        )
        queue.save_to_disk()

        first_loop = JarvisSystemLoop(
            config=SystemLoopConfig(
                cycle_sleep_seconds=0,
                idle_sleep_seconds=0,
                max_cycles=1,
                install_signal_handlers=False,
                queue_storage_path=queue_storage_path,
                semantic_storage_path=semantic_storage_path,
            ),
            logger=lambda _: None,
        )

        first_summary = first_loop.run()

        self.assertEqual(first_summary["completed_cycles"], 1)
        self.assertEqual(first_summary["cycle_logs"][0]["status"], "idle")

        restarted_runtime, restarted_state = bootstrap_runtime(
            runtime=InternalAgentRuntime(),
            config=SystemLoopConfig(
                queue_storage_path=queue_storage_path,
                semantic_storage_path=semantic_storage_path,
                install_signal_handlers=False,
            ),
        )

        self.assertEqual(restarted_state["queue_depth"], 1)
        self.assertEqual(restarted_runtime.task_queue.items[0]["task_id"], "blocked-1")
        self.assertEqual(restarted_runtime.task_queue.items[0]["state"], "blocked")
        self.assertEqual(restarted_runtime.task_queue.items[0]["state_ptbr"], "bloqueada")


if __name__ == "__main__":
    unittest.main()
