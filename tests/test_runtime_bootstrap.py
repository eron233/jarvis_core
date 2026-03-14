"""Testes unitarios para o primeiro bootstrap do runtime do JARVIS."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from executive_planner.queue import TaskQueue
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime


def make_queue_storage_path(name: str) -> Path:
    return PROJECT_ROOT / "tests" / "_queue_artifacts" / f"{name}.json"


def make_semantic_storage_path(name: str) -> Path:
    return PROJECT_ROOT / "tests" / "_semantic_memory_artifacts" / f"{name}.json"


def reset_storage_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class RuntimeBootstrapTests(unittest.TestCase):
    def test_bootstrap_initializes_core_runtime_components(self) -> None:
        queue_storage_path = make_queue_storage_path("runtime_bootstrap")
        semantic_storage_path = make_semantic_storage_path("runtime_bootstrap")
        reset_storage_path(queue_storage_path)
        reset_storage_path(semantic_storage_path)
        runtime = InternalAgentRuntime()
        runtime.task_queue = TaskQueue(storage_path=queue_storage_path)
        runtime.memory = {
            "episodic": EpisodicMemory(),
            "semantic": SemanticMemory(storage_path=semantic_storage_path),
            "procedural": ProceduralMemory(),
        }

        state = runtime.bootstrap()

        self.assertEqual(state["status"], "initialized")
        self.assertEqual(state["status_ptbr"], "inicializado")
        self.assertEqual(state["planner"], "executive_planner.planner.ExecutivePlanner")
        self.assertEqual(state["memory"], "memory_system")
        self.assertEqual(state["memory_modules"], ["episodic", "semantic", "procedural"])
        self.assertEqual(
            state["workers"],
            ["worker_runtime", "worker_finance", "worker_studio", "worker_study"],
        )
        self.assertEqual(state["queue_depth"], 0)
        self.assertEqual(state["default_locale"], "pt-BR")
        self.assertTrue(state["politica_constitucional_carregada"])
        self.assertEqual(state["modo_autonomia"], "supervisionada_por_politica_constitucional")
        self.assertIsNotNone(runtime.planner)
        self.assertIs(runtime.planner.runtime, runtime)
        self.assertEqual(runtime.memory["semantic"].get("runtime_status"), "inicializado")
        self.assertEqual(
            runtime.memory["semantic"].get("constitutional_operating_mode"),
            "autonomia_supervisionada_por_humanos",
        )
        self.assertEqual(
            runtime.memory["procedural"].get("planner_cycle"),
            ["planejar", "priorizar", "validar", "agendar", "executar", "revisar"],
        )
        self.assertEqual(runtime.memory["episodic"].recent(1)[0]["event"], "bootstrap")
        self.assertEqual(runtime.memory["episodic"].recent(1)[0]["event_ptbr"], "inicializar")

    def test_bootstrapped_runtime_runs_one_planner_cycle(self) -> None:
        queue_storage_path = make_queue_storage_path("runtime_cycle")
        semantic_storage_path = make_semantic_storage_path("runtime_cycle")
        reset_storage_path(queue_storage_path)
        reset_storage_path(semantic_storage_path)
        runtime = InternalAgentRuntime()
        runtime.task_queue = TaskQueue(storage_path=queue_storage_path)
        runtime.memory = {
            "episodic": EpisodicMemory(),
            "semantic": SemanticMemory(storage_path=semantic_storage_path),
            "procedural": ProceduralMemory(),
        }
        runtime.bootstrap()
        runtime.enqueue_task(
            {
                "task_id": "finance-1",
                "goal": "Revisar fluxo de caixa",
                "worker": "worker_finance",
                "impact": 3,
                "urgency": 2,
                "description": "Revisao financeira",
                "domain": "finance",
            }
        )

        result = runtime.run_planner_cycle()

        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["status_ptbr"], "executada")
        self.assertEqual(result["selected_task"]["task_id"], "finance-1")
        self.assertEqual(result["selected_task"]["state_ptbr"], "concluida")
        self.assertEqual(result["dispatch_result"]["worker"], "finance")
        self.assertEqual(result["dispatch_result"]["worker_response"]["worker"], "finance")
        self.assertEqual(result["dispatch_result"]["worker_response"]["status_ptbr"], "aceita")
        self.assertEqual(runtime.describe_state()["queue_depth"], 0)
        self.assertEqual(runtime.describe_state()["queue_store"], str(queue_storage_path))
        self.assertEqual(runtime.memory["episodic"].recent(1)[0]["event"], "dispatch")
        self.assertEqual(runtime.memory["episodic"].recent(1)[0]["event_ptbr"], "despachar")

        semantic_results = runtime.query_semantic_memory("fluxo de caixa concluida", domain="finance")
        self.assertEqual(len(semantic_results), 1)
        self.assertEqual(semantic_results[0]["metadata"]["task_id"], "finance-1")
        self.assertEqual(semantic_results[0]["domain"], "finance")
        system_report = runtime.build_system_report(last_cycle_result=result)
        self.assertEqual(
            system_report["politica_ativa"]["identidade"]["modo_operacao"],
            "autonomia_supervisionada_por_humanos",
        )


if __name__ == "__main__":
    unittest.main()
