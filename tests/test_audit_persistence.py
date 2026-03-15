"""Testes da auditoria persistente do JARVIS."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from executive_planner.audit import AuditLogger
from runtime.internal_agent_runtime import InternalAgentRuntime


def make_audit_storage_path(name: str) -> Path:
    """Retorna o path isolado da auditoria persistente para testes."""

    return PROJECT_ROOT / "tests" / "_audit_artifacts" / f"{name}.json"


def reset_storage_path(path: Path) -> None:
    """Limpa o arquivo de auditoria antes do cenario."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class AuditPersistenceTests(unittest.TestCase):
    """Valida persistencia e recarga da trilha de auditoria."""

    def test_audit_logger_roundtrip_persists_entries(self) -> None:
        """Confirma que eventos persistidos voltam apos recarga do logger."""

        storage_path = make_audit_storage_path("roundtrip")
        reset_storage_path(storage_path)

        logger = AuditLogger(storage_path=storage_path)
        logger.auto_persist_on_change(True)
        logger.record("execute", {"status": "completed", "reason": "no_tasks"})

        restored_logger = AuditLogger(storage_path=storage_path)
        snapshot = restored_logger.load_snapshot()

        self.assertEqual(snapshot["entry_count"], 1)
        self.assertEqual(restored_logger.entries[0]["event"], "execute")
        self.assertEqual(restored_logger.entries[0]["payload"]["status_ptbr"], "concluida")

    def test_runtime_access_attempt_is_persisted(self) -> None:
        """Garante que eventos criticos de acesso fiquem gravados em disco."""

        storage_path = make_audit_storage_path("runtime_access")
        reset_storage_path(storage_path)

        runtime = InternalAgentRuntime()
        runtime.audit_logger = AuditLogger(storage_path=storage_path)
        runtime.bootstrap()
        runtime.record_access_attempt(
            endpoint="/api/status",
            method="GET",
            device_id="eron-celular-principal",
            allowed=False,
            reason="invalid_token",
            client_host="127.0.0.1",
        )

        restored_logger = AuditLogger(storage_path=storage_path)
        restored_logger.load_snapshot()

        self.assertEqual(restored_logger.entries[-1]["event"], "access")
        self.assertEqual(restored_logger.entries[-1]["payload"]["reason"], "invalid_token")


if __name__ == "__main__":
    unittest.main()
