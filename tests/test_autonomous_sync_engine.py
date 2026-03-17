"""Testes do motor interno de sincronizacao autonoma de desenvolvimento."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.vital_organs.autonomous_sync_engine import (
    AutonomousSyncConfig,
    AutonomousSyncEngine,
    CommandResult,
)


class AutonomousSyncEngineTests(unittest.TestCase):
    """Valida a sincronizacao autonoma sem tocar no Git real do workspace."""

    def build_engine(self, root: Path, runner) -> AutonomousSyncEngine:
        """Monta um motor em modo de teste com runner falso."""

        config = AutonomousSyncConfig(
            enabled=True,
            write_enabled=True,
            device_name="pc_esposa(voce)",
            sync_area="runtime",
            sync_interval_seconds=180,
            remote_name="origin",
            branch_name="master",
            tests_command=("python", "-m", "unittest", "discover", "-s", "tests", "-v"),
        )
        return AutonomousSyncEngine(project_root=root, config=config, command_runner=runner)

    def test_engine_observa_sem_escrever_quando_write_mode_esta_desligado(self) -> None:
        """Confirma modo somente-observacao por padrao seguro."""

        commands: list[list[str]] = []

        def runner(command):
            commands.append(list(command))
            if command[:3] == ["git", "fetch", "origin"]:
                return CommandResult(list(command), 0, "", "")
            if command[:3] == ["git", "rev-list", "--left-right"]:
                return CommandResult(list(command), 0, "0 0\n", "")
            raise AssertionError(f"Comando inesperado: {command}")

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = self.build_engine(Path(temp_dir), runner)
            engine.config.write_enabled = False

            report = engine.run(runtime=None)

            self.assertEqual(report["status"], "observacao")
            self.assertEqual(report["acao"], "observe_only")
            self.assertEqual(commands[0][:3], ["git", "fetch", "origin"])
            self.assertTrue(engine.log_path.exists())

    def test_engine_respeita_lock_ativo_de_outro_dispositivo(self) -> None:
        """Impede sincronizacao concorrente quando a area ja esta reservada."""

        now = datetime.now(timezone.utc).isoformat()
        commands: list[list[str]] = []

        def runner(command):
            commands.append(list(command))
            if command[:3] == ["git", "fetch", "origin"]:
                return CommandResult(list(command), 0, "", "")
            if command[:3] == ["git", "rev-list", "--left-right"]:
                return CommandResult(list(command), 0, "0 0\n", "")
            raise AssertionError(f"Comando inesperado: {command}")

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            engine = self.build_engine(root, runner)
            engine.lock_path.parent.mkdir(parents=True, exist_ok=True)
            engine.lock_path.write_text(
                json.dumps(
                    {
                        "updated_at": now,
                        "locks": [
                            {
                                "area": "runtime",
                                "device": "pc_melhor_amigo",
                                "timestamp": now,
                                "status": "working",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = engine.run(runtime=None)

            self.assertEqual(report["status"], "atencao")
            self.assertEqual(report["acao"], "lock_denied")
            self.assertIn("pc_melhor_amigo", report["mensagem"])

    def test_engine_cancela_commit_quando_testes_falham(self) -> None:
        """Garante bloqueio de commit/push se a suite falhar."""

        commands: list[list[str]] = []

        def runner(command):
            commands.append(list(command))
            if command[:3] == ["git", "fetch", "origin"]:
                return CommandResult(list(command), 0, "", "")
            if command[:3] == ["git", "rev-list", "--left-right"]:
                return CommandResult(list(command), 0, "1 0\n", "")
            if command[:4] == ["git", "pull", "--rebase", "origin"]:
                return CommandResult(list(command), 0, "Already up to date.\n", "")
            if command[:3] == ["python", "-m", "unittest"]:
                return CommandResult(list(command), 1, "", "falha em teste")
            raise AssertionError(f"Comando inesperado: {command}")

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = self.build_engine(Path(temp_dir), runner)

            report = engine.run(runtime=None)

            self.assertEqual(report["status"], "critico")
            self.assertEqual(report["acao"], "tests_failed")
            self.assertFalse(any(cmd[:2] == ["git", "commit"] for cmd in commands))
            lock_snapshot = json.loads(engine.lock_path.read_text(encoding="utf-8"))
            self.assertEqual(lock_snapshot["locks"], [])

    def test_engine_commit_e_push_quando_workspace_esta_dentro_da_area(self) -> None:
        """Confirma o fluxo completo quando a area reservada contem mudancas validas."""

        commands: list[list[str]] = []

        def runner(command):
            commands.append(list(command))
            if command[:3] == ["git", "fetch", "origin"]:
                return CommandResult(list(command), 0, "", "")
            if command[:3] == ["git", "rev-list", "--left-right"]:
                return CommandResult(list(command), 0, "1 0\n", "")
            if command[:4] == ["git", "pull", "--rebase", "origin"]:
                return CommandResult(list(command), 0, "Atualizado.\n", "")
            if command[:3] == ["python", "-m", "unittest"]:
                return CommandResult(list(command), 0, "OK", "")
            if command[:3] == ["git", "status", "--porcelain"]:
                return CommandResult(
                    list(command),
                    0,
                    " M runtime/internal_agent_runtime.py\n M tests/test_runtime_bootstrap.py\n",
                    "",
                )
            if command[:2] == ["git", "add"]:
                return CommandResult(list(command), 0, "", "")
            if command[:2] == ["git", "commit"]:
                return CommandResult(list(command), 0, "[master abc123] checkpoint\n", "")
            if command[:3] == ["git", "rev-parse", "HEAD"]:
                return CommandResult(list(command), 0, "abc123def456\n", "")
            if command[:2] == ["git", "push"]:
                return CommandResult(list(command), 0, "push ok\n", "")
            raise AssertionError(f"Comando inesperado: {command}")

        with tempfile.TemporaryDirectory() as temp_dir:
            engine = self.build_engine(Path(temp_dir), runner)

            report = engine.run(runtime=None)

            self.assertEqual(report["status"], "saudavel")
            self.assertEqual(report["acao"], "sync_completed")
            self.assertTrue(any(cmd[:4] == ["git", "pull", "--rebase", "origin"] for cmd in commands))
            self.assertTrue(any(cmd[:2] == ["git", "commit"] for cmd in commands))
            self.assertTrue(any(cmd[:2] == ["git", "push"] for cmd in commands))
            self.assertIn("abc123def456", engine.checkpoint_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
