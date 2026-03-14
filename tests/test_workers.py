"""Testes dos workers uteis por dominio e sua integracao com o runtime."""

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
from workers.worker_finance import FinanceWorker
from workers.worker_runtime import RuntimeWorker
from workers.worker_studio import StudioWorker
from workers.worker_study import StudyWorker


def make_storage_path(name: str, suffix: str) -> Path:
    return PROJECT_ROOT / "tests" / "_worker_artifacts" / f"{name}_{suffix}.json"


def reset_storage_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class WorkerUtilityTests(unittest.TestCase):
    def test_runtime_worker_generates_diagnostic_report(self) -> None:
        worker = RuntimeWorker()

        response = worker.handle(
            {
                "task_id": "runtime-1",
                "goal": "Diagnosticar estado do runtime",
                "domain": "runtime",
                "runtime_context": {
                    "status_ptbr": "inicializado",
                    "queue_depth": 2,
                    "active_goal_count": 1,
                    "total_cycles_executed": 3,
                    "politica_constitucional_carregada": True,
                },
            }
        )

        self.assertEqual(response["status"], "accepted")
        self.assertEqual(response["result_type"], "runtime_report")
        self.assertIn("technical_report", response["details"])
        self.assertGreaterEqual(len(response["evidence"]), 1)

    def test_study_worker_generates_topics_and_next_steps(self) -> None:
        worker = StudyWorker()

        response = worker.handle(
            {
                "task_id": "study-1",
                "goal": "Revisar algebra linear",
                "description": "Matrizes, determinantes e transformacoes lineares para prova.",
                "domain": "study",
            }
        )

        self.assertEqual(response["status"], "accepted")
        self.assertEqual(response["result_type"], "study_digest")
        self.assertGreaterEqual(len(response["details"]["topicos"]), 1)
        self.assertGreaterEqual(len(response["next_steps"]), 1)

    def test_studio_worker_generates_briefing_and_checklist(self) -> None:
        worker = StudioWorker()

        response = worker.handle(
            {
                "task_id": "studio-1",
                "goal": "Criar roteiro curto para reels",
                "description": "Video curto com foco em bastidores e mensagem principal.",
                "domain": "studio",
                "metadata": {"audience": "criadores", "format": "reels"},
            }
        )

        self.assertEqual(response["status"], "accepted")
        self.assertEqual(response["result_type"], "studio_briefing")
        self.assertEqual(response["details"]["briefing"]["formato"], "reels")
        self.assertGreaterEqual(len(response["details"]["checklist_producao"]), 1)

    def test_finance_worker_generates_analytic_summary(self) -> None:
        worker = FinanceWorker()

        response = worker.handle(
            {
                "task_id": "finance-1",
                "goal": "Organizar observacoes de caixa",
                "description": "Fluxo de caixa pressionado por despesas recorrentes.",
                "domain": "finance",
                "metadata": {
                    "observations": ["despesas recorrentes cresceram", "receita ficou estavel"],
                    "values": {"caixa": 12000, "despesas": 8000},
                },
            }
        )

        self.assertEqual(response["status"], "accepted")
        self.assertEqual(response["result_type"], "finance_analysis")
        self.assertGreaterEqual(len(response["details"]["observacoes_estruturadas"]), 1)
        self.assertGreaterEqual(len(response["details"]["indicadores"]), 1)

    def test_runtime_dispatch_routes_worker_and_records_semantic_summary(self) -> None:
        queue_path = make_storage_path("dispatch", "queue")
        semantic_path = make_storage_path("dispatch", "semantic")
        procedural_path = make_storage_path("dispatch", "procedural")
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
                "task_id": "study-dispatch-1",
                "goal": "Revisar biologia celular",
                "description": "Membrana, organelas e transporte celular.",
                "domain": "study",
                "worker": "worker_study",
                "impact": 2,
                "urgency": 2,
            }
        )

        result = runtime.run_planner_cycle()

        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["dispatch_result"]["worker"], "study")
        self.assertEqual(result["dispatch_result"]["worker_response"]["result_type"], "study_digest")
        self.assertGreaterEqual(len(result["dispatch_result"]["worker_response"]["evidence"]), 1)

        semantic_result = runtime.query_semantic_memory("biologia celular", domain="study")[0]
        self.assertEqual(semantic_result["metadata"]["worker_result_type"], "study_digest")
        self.assertTrue(semantic_result["metadata"]["worker_summary"])

    def test_worker_rejects_invalid_domain(self) -> None:
        worker = FinanceWorker()

        response = worker.handle(
            {
                "task_id": "finance-invalid-1",
                "goal": "Tema criativo",
                "description": "Briefing de video",
                "domain": "studio",
            }
        )

        self.assertEqual(response["status"], "rejected")
        self.assertEqual(response["reason"], "invalid_domain")


if __name__ == "__main__":
    unittest.main()
