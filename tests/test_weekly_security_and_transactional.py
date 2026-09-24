"""
Testes unitários para o motor de relatório semanal de segurança (Bloco 12.6) e armazenamento transacional.
"""

from pathlib import Path
import tempfile
import unittest

from executive_planner.audit import AuditLogger
from executive_planner.queue import TaskQueue
from executive_planner.transactional_store import TransactionalStore
from security.security_report_engine import WeeklySecurityReportEngine


class SecurityReportEngineAndTransactionalStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_weekly_security_report_generation_and_loading(self) -> None:
        report_path = self.tmp_path / "weekly_report.json"
        engine = WeeklySecurityReportEngine(report_path=report_path)

        sd_report = {
            "nivel_risco_geral": "medio",
            "fraquezas_detectadas": [
                {
                    "id": "W1",
                    "titulo": "Senha de Teste",
                    "severidade": "medio",
                    "descricao": "Aviso de teste",
                    "recorrente": False,
                }
            ],
            "acoes_automaticas_aplicadas": ["Auto Fix 1"],
        }

        report = engine.generate_report(self_defense_report=sd_report)
        self.assertEqual(report["nivel_risco_geral"], "medio")
        self.assertEqual(report["estatisticas"]["total_fraquezas"], 1)
        self.assertTrue(report_path.exists())

        loaded = engine.load_latest_report()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["nivel_risco_geral"], "medio")

    def test_transactional_store_queue_and_audit(self) -> None:
        db_path = self.tmp_path / "test_transactional.db"
        tx_store = TransactionalStore(db_path=db_path)

        tasks = [
            {"task_id": "T1", "domain": "runtime", "state": "queued", "urgency": 1},
            {"task_id": "T2", "domain": "finance", "state": "completed", "urgency": 2},
        ]
        tx_store.save_queue_tasks(tasks)
        loaded_tasks = tx_store.load_queue_tasks()
        self.assertEqual(len(loaded_tasks), 2)
        self.assertEqual(loaded_tasks[0]["task_id"], "T1")

        event = {"event_id": "E1", "event": "auth_success", "actor": "test_device"}
        tx_store.append_audit_event(event)
        loaded_events = tx_store.load_audit_events()
        self.assertEqual(len(loaded_events), 1)
        self.assertEqual(loaded_events[0]["event_id"], "E1")

        stats = tx_store.get_stats()
        self.assertEqual(stats["total_tarefas_transacionais"], 2)
        self.assertEqual(stats["total_eventos_auditoria_transacionais"], 1)

    def test_queue_and_audit_mirroring_to_transactional_store(self) -> None:
        json_queue_path = self.tmp_path / "task_queue_store.json"
        json_audit_path = self.tmp_path / "runtime_audit_store.json"
        db_path = self.tmp_path / "jarvis_transactional.db"

        queue = TaskQueue(storage_path=json_queue_path, auto_persist=True)
        queue.enqueue({"task_id": "TX_TASK", "goal": "Test Mirroring"})

        audit = AuditLogger(storage_path=json_audit_path, auto_persist=True)
        audit.record("bootstrap", {"status": "success"})

        tx_store = TransactionalStore(db_path=db_path)
        self.assertEqual(len(tx_store.load_queue_tasks()), 1)
        self.assertEqual(len(tx_store.load_audit_events()), 1)


if __name__ == "__main__":
    unittest.main()
