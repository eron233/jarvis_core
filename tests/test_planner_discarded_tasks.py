"""Testes da declaracao de tarefas descartadas pelo ciclo do planner."""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from executive_planner.audit import AuditLogger
from executive_planner.queue import TaskQueue
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime


class PlannerDiscardedTasksTests(unittest.TestCase):
    """Uma tarefa que sai da fila sem concluir precisa aparecer no relatorio."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.runtime = InternalAgentRuntime()
        self.runtime.task_queue = TaskQueue(storage_path=self.tmp / "queue.json")
        self.runtime.audit_logger = AuditLogger(storage_path=self.tmp / "audit.json")
        self.runtime.memory = {
            "episodic": EpisodicMemory(),
            "semantic": SemanticMemory(storage_path=self.tmp / "semantic.json"),
            "procedural": ProceduralMemory(),
        }
        self.runtime.bootstrap()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tarefa_com_worker_inexistente_e_declarada_como_descartada(self) -> None:
        """
        Tarefas recusadas no despacho nao voltam para a fila, para nao gerarem
        retentativa infinita. Antes elas apenas sumiam: a fila encolhia sem que
        nada registrasse que aquela tarefa saiu sem concluir.
        """

        self.runtime.enqueue_task(
            {
                "task_id": "descartada-1",
                "goal": "Alcancar um worker que nao existe",
                "description": "Tarefa apontando para um worker inexistente",
                "domain": "runtime",
                "worker": "worker_que_nao_existe",
                "effect_scope": "internal",
                "approved": True,
            }
        )

        ciclo = self.runtime.run_planner_cycle()

        self.assertEqual(len(ciclo["discarded_tasks"]), 1)
        descartada = ciclo["discarded_tasks"][0]
        self.assertEqual(descartada["task"]["task_id"], "descartada-1")
        self.assertEqual(descartada["reason"], "unknown_worker")

    def test_descarte_aparece_na_auditoria_do_ciclo(self) -> None:
        """O operador precisa ver o descarte sem inspecionar a fila."""

        self.runtime.enqueue_task(
            {
                "task_id": "descartada-2",
                "goal": "Alcancar um worker que nao existe",
                "description": "Outra tarefa com worker inexistente",
                "domain": "runtime",
                "worker": "outro_worker_inexistente",
                "effect_scope": "internal",
                "approved": True,
            }
        )

        self.runtime.run_planner_cycle()

        revisoes = [
            entrada
            for entrada in self.runtime.audit_logger.snapshot()["entries"]
            if entrada.get("event") == "review"
        ]
        self.assertTrue(revisoes)
        self.assertEqual(revisoes[-1]["payload"]["discarded_count"], 1)
        self.assertIn("unknown_worker", revisoes[-1]["payload"]["discarded_reasons"])

    def test_ciclo_sem_descarte_reporta_lista_vazia(self) -> None:
        """Um ciclo comum nao pode inventar descartes."""

        ciclo = self.runtime.run_planner_cycle()

        self.assertEqual(ciclo["discarded_tasks"], [])


if __name__ == "__main__":
    unittest.main()
