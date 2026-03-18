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
    """Retorna o path de fila usado nos cenarios do loop continuo."""

    return PROJECT_ROOT / "tests" / "_main_loop_artifacts" / f"{name}_queue.json"


def make_semantic_storage_path(name: str) -> Path:
    """Retorna o path de memoria semantica usado nos testes do loop."""

    return PROJECT_ROOT / "tests" / "_main_loop_artifacts" / f"{name}_semantic.json"


def make_audit_storage_path(name: str) -> Path:
    """Retorna o path de auditoria usado nos testes do loop."""

    return PROJECT_ROOT / "tests" / "_main_loop_artifacts" / f"{name}_audit.json"


def reset_storage_path(path: Path) -> None:
    """Remove artefatos antigos antes da execucao do teste."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class MainLoopTests(unittest.TestCase):
    """Valida bootstrap, idle seguro e recuperacao do loop principal."""

    def test_bootstrap_runtime_loads_queue_and_semantic_memory(self) -> None:
        """Confirma recarga de fila e memoria semantica no bootstrap do loop."""

        queue_storage_path = make_queue_storage_path("bootstrap")
        semantic_storage_path = make_semantic_storage_path("bootstrap")
        audit_storage_path = make_audit_storage_path("bootstrap")
        reset_storage_path(queue_storage_path)
        reset_storage_path(semantic_storage_path)
        reset_storage_path(audit_storage_path)

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
                audit_storage_path=audit_storage_path,
                install_signal_handlers=False,
            ),
        )

        self.assertEqual(state["status"], "initialized")
        self.assertEqual(state["queue_depth"], 1)
        self.assertEqual(runtime.task_queue.items[0]["task_id"], "bootstrap-1")
        self.assertEqual(runtime.query_semantic_memory("memoria persistida", domain="system")[0]["domain"], "system")

    def test_loop_minimo_para_em_fila_vazia_sem_erro(self) -> None:
        """Verifica parada limpa quando o loop encontra fila vazia."""

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
                audit_storage_path=make_audit_storage_path("idle"),
            ),
            logger=logs.append,
        )
        reset_storage_path(loop.config.queue_storage_path)
        reset_storage_path(loop.config.semantic_storage_path)
        reset_storage_path(loop.config.audit_storage_path)

        summary = loop.run()

        self.assertEqual(summary["completed_cycles"], 1)
        self.assertEqual(summary["shutdown_reason"], "idle_queue")
        self.assertEqual(summary["shutdown_reason_ptbr"], "fila_vazia")
        self.assertEqual(summary["runtime_state"]["queue_depth"], 0)
        self.assertEqual(summary["cycle_logs"][0]["status"], "idle")
        self.assertTrue(any("[ciclo 1]" in line for line in logs))

    def test_restart_recovers_blocked_queue_state(self) -> None:
        """Garante recuperacao do estado bloqueado da fila apos reinicio."""

        queue_storage_path = make_queue_storage_path("restart")
        semantic_storage_path = make_semantic_storage_path("restart")
        audit_storage_path = make_audit_storage_path("restart")
        reset_storage_path(queue_storage_path)
        reset_storage_path(semantic_storage_path)
        reset_storage_path(audit_storage_path)

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
                audit_storage_path=audit_storage_path,
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
                audit_storage_path=audit_storage_path,
                install_signal_handlers=False,
            ),
        )

        self.assertEqual(restarted_state["queue_depth"], 1)
        self.assertEqual(restarted_runtime.task_queue.items[0]["task_id"], "blocked-1")
        self.assertEqual(restarted_runtime.task_queue.items[0]["state"], "blocked")
        self.assertEqual(restarted_runtime.task_queue.items[0]["state_ptbr"], "bloqueada")

    def test_watchdog_mantem_loop_vivo_apos_excecao_controlada(self) -> None:
        """Garante que o loop continue rodando mesmo apos uma excecao em um ciclo."""

        class FlakyRuntime(InternalAgentRuntime):
            """Runtime de teste que falha de forma controlada para exercitar o watchdog."""
            def __init__(self) -> None:
                """Inicializa a instancia e prepara o estado interno do componente."""
                super().__init__()
                self.calls = 0

            def run_planner_cycle(self) -> dict[str, str]:
                """Executa a rotina interna de run planner cycle."""
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("falha_controlada")
                return {
                    "status": "idle",
                    "status_ptbr": "ociosa",
                    "reason": "no_tasks",
                    "reason_ptbr": "sem_tarefas",
                }

        logs: list[str] = []
        queue_path = make_queue_storage_path("watchdog")
        semantic_path = make_semantic_storage_path("watchdog")
        audit_path = make_audit_storage_path("watchdog")
        reset_storage_path(queue_path)
        reset_storage_path(semantic_path)
        reset_storage_path(audit_path)

        loop = JarvisSystemLoop(
            runtime=FlakyRuntime(),
            config=SystemLoopConfig(
                cycle_sleep_seconds=0,
                idle_sleep_seconds=0,
                max_cycles=2,
                stop_when_idle=True,
                install_signal_handlers=False,
                queue_storage_path=queue_path,
                semantic_storage_path=semantic_path,
                audit_storage_path=audit_path,
            ),
            logger=logs.append,
        )

        summary = loop.run()

        self.assertEqual(summary["completed_cycles"], 2)
        self.assertEqual(summary["cycle_logs"][0]["status"], "failed")
        self.assertEqual(summary["cycle_logs"][1]["status"], "idle")
        self.assertTrue(any("[ciclo 1]" in line for line in logs))


if __name__ == "__main__":
    unittest.main()
