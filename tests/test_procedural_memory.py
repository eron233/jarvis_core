"""Testes da memoria procedural persistente e integrada ao runtime."""

from __future__ import annotations

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


def make_storage_path(name: str, suffix: str) -> Path:
    return PROJECT_ROOT / "tests" / "_procedural_artifacts" / f"{name}_{suffix}.json"


def reset_storage_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class ProceduralMemoryTests(unittest.TestCase):
    def test_register_stores_structured_procedure(self) -> None:
        storage_path = make_storage_path("register", "procedural")
        reset_storage_path(storage_path)
        memory = ProceduralMemory(storage_path=storage_path)

        entry = memory.register(
            name="finance_execution_pattern",
            steps=["coletar contexto", "executar analise", "registrar evidencias"],
            domain="finance",
            task_type="finance",
            heuristic="Registrar o contexto antes de resumir a analise.",
            context={"goal": "Revisar fluxo de caixa"},
            preconditions=["tarefa validada"],
            observed_result="executed",
            success=True,
            evidence=["saldo_atual", "fluxo_caixa"],
            metadata={"task_id": "finance-1"},
        )

        self.assertEqual(entry["id"], "procedure-0001")
        self.assertEqual(memory.get("finance_execution_pattern")[0], "coletar contexto")
        self.assertEqual(memory.get_entry("finance_execution_pattern")["domain"], "finance")
        self.assertEqual(memory.get_entry("finance_execution_pattern")["metadata"]["task_id"], "finance-1")

    def test_search_filters_by_domain_and_task_type(self) -> None:
        storage_path = make_storage_path("search", "procedural")
        reset_storage_path(storage_path)
        memory = ProceduralMemory(storage_path=storage_path)

        memory.register(
            name="finance_execution_pattern",
            steps=["coletar dados", "resumir variacoes"],
            domain="finance",
            task_type="finance",
            heuristic="Focar em fluxo de caixa e variacoes.",
            observed_result="executed",
        )
        memory.register(
            name="study_execution_pattern",
            steps=["ler material", "organizar topicos"],
            domain="study",
            task_type="study",
            heuristic="Converter conteudo em topicos de estudo.",
            observed_result="executed",
        )

        results = memory.search(
            query="fluxo de caixa",
            domain="finance",
            task_type="finance",
            success_only=True,
            limit=5,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "finance_execution_pattern")
        self.assertEqual(memory.get_by_domain("study")[0]["task_type"], "study")

    def test_persistence_roundtrip_restores_procedures(self) -> None:
        storage_path = make_storage_path("roundtrip", "procedural")
        reset_storage_path(storage_path)
        memory = ProceduralMemory(storage_path=storage_path)

        memory.register(
            name="runtime_execution_pattern",
            steps=["diagnosticar", "registrar", "persistir"],
            domain="runtime",
            task_type="runtime",
            heuristic="Fechar sempre com persistencia explicita.",
            observed_result="executed",
            metadata={"task_id": "runtime-1"},
        )
        snapshot = memory.snapshot()

        restored = ProceduralMemory(storage_path=storage_path)
        restored_snapshot = restored.load_snapshot()

        self.assertEqual(snapshot["procedure_count"], 1)
        self.assertEqual(restored_snapshot["procedure_count"], 1)
        self.assertEqual(restored.get("runtime_execution_pattern")[-1], "persistir")

    def test_runtime_records_and_reuses_procedural_guidance(self) -> None:
        queue_path = make_storage_path("runtime", "queue")
        semantic_path = make_storage_path("runtime", "semantic")
        procedural_path = make_storage_path("runtime", "procedural")
        for path in (queue_path, semantic_path, procedural_path):
            reset_storage_path(path)

        runtime = InternalAgentRuntime()
        runtime.task_queue = TaskQueue(storage_path=queue_path)
        runtime.memory = {
            "episodic": EpisodicMemory(),
            "semantic": SemanticMemory(storage_path=semantic_path),
            "procedural": ProceduralMemory(storage_path=procedural_path),
        }
        runtime.bootstrap()

        runtime.enqueue_task(
            {
                "task_id": "finance-1",
                "goal": "Revisar fluxo de caixa semanal",
                "description": "Consolidar variacoes de caixa",
                "domain": "finance",
                "worker": "worker_finance",
                "impact": 3,
                "urgency": 2,
            }
        )
        first_result = runtime.run_planner_cycle()

        stored_guidance = runtime.query_procedural_memory(
            query="fluxo de caixa",
            domain="finance",
            task_type="finance",
            success_only=True,
            limit=5,
        )
        self.assertEqual(first_result["status"], "executed")
        self.assertGreaterEqual(len(stored_guidance), 1)
        self.assertEqual(stored_guidance[0]["name"], "finance_execution_pattern")

        runtime.enqueue_task(
            {
                "task_id": "finance-2",
                "goal": "Revisar fluxo de caixa mensal",
                "description": "Consolidar variacoes recorrentes",
                "domain": "finance",
                "worker": "worker_finance",
                "impact": 2,
                "urgency": 2,
            }
        )
        second_result = runtime.run_planner_cycle()

        self.assertEqual(second_result["status"], "executed")
        procedural_context = second_result["dispatch_result"]["procedural_context"]
        self.assertGreaterEqual(procedural_context["guidance_candidates"], 1)
        self.assertEqual(procedural_context["guidance_used"]["name"], "finance_execution_pattern")


if __name__ == "__main__":
    unittest.main()
