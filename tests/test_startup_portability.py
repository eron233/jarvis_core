"""Testes de portabilidade dos entrypoints oficiais do JARVIS."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from startup_bootstrap import ensure_project_root_on_path


def make_startup_artifact_dir(name: str) -> Path:
    """Retorna o diretorio de artefatos usado nos testes de startup."""

    return Path(tempfile.gettempdir()) / f"jarvis_startup_{name}"


def reset_directory(path: Path) -> None:
    """Recria o diretorio de artefato em estado limpo."""

    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def extract_json_payload_from_output(stdout: str) -> dict:
    """Extrai o payload JSON final de uma saida que pode conter avisos antes do bloco estruturado."""

    start = stdout.find("{")
    if start == -1:
        raise ValueError("Nenhum payload JSON encontrado na saida.")
    return json.loads(stdout[start:])


class StartupPortabilityTests(unittest.TestCase):
    """Valida portabilidade dos entrypoints oficiais do sistema."""

    def test_bootstrap_helper_discovers_project_root(self) -> None:
        """Confirma que o helper encontra a raiz correta do projeto."""

        nested_path = PROJECT_ROOT / "runtime" / "server.py"
        project_root = ensure_project_root_on_path(nested_path)

        self.assertEqual(project_root, PROJECT_ROOT)
        self.assertEqual(str(PROJECT_ROOT), sys.path[0])

    def test_main_entrypoint_runs_with_current_interpreter(self) -> None:
        """Verifica execucao do entrypoint principal com o interpretador atual."""

        artifact_dir = make_startup_artifact_dir("main_entrypoint")
        reset_directory(artifact_dir)

        command = [
            sys.executable,
            str(PROJECT_ROOT / "main.py"),
            "--max-cycles",
            "1",
            "--stop-when-idle",
            "--queue-storage-path",
            str(artifact_dir / "task_queue_store.json"),
            "--semantic-storage-path",
            str(artifact_dir / "semantic_memory_store.json"),
            "--procedural-storage-path",
            str(artifact_dir / "procedural_memory_store.json"),
            "--goal-storage-path",
            str(artifact_dir / "goals.json"),
            "--cognitive-evolution-storage-path",
            str(artifact_dir / "cognitive_evolution_history.json"),
            "--audit-storage-path",
            str(artifact_dir / "runtime_audit_store.json"),
            "--device-registry-path",
            str(artifact_dir / "device_registry.json"),
            "--self-defense-report-path",
            str(artifact_dir / "self_defense_latest.json"),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("[encerramento]", completed.stdout)
        self.assertTrue((artifact_dir / "task_queue_store.json").exists())
        self.assertTrue((artifact_dir / "semantic_memory_store.json").exists())
        self.assertTrue((artifact_dir / "procedural_memory_store.json").exists())
        self.assertTrue((artifact_dir / "goals.json").exists())

    def test_server_check_config_runs_with_current_interpreter(self) -> None:
        """Confirma validacao de configuracao do servidor pelo entrypoint oficial."""

        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "runtime" / "server.py"),
                "--check-config",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        payload = extract_json_payload_from_output(completed.stdout)
        self.assertIn("mensagem", payload)
        self.assertIn("ambiente", payload)

    @unittest.skipUnless(sys.platform.startswith("win"), "Launcher .cmd valido apenas em Windows.")
    def test_windows_launcher_runs_loop_with_explicit_interpreter(self) -> None:
        """Valida o launcher Windows com interpretador explicitamente configurado."""

        artifact_dir = make_startup_artifact_dir("windows_launcher")
        reset_directory(artifact_dir)

        env = dict(os.environ)
        env["PYTHON_BIN"] = sys.executable

        completed = subprocess.run(
            [
                "cmd.exe",
                "/c",
                "jarvis.cmd",
                "loop",
                "--max-cycles",
                "1",
                "--stop-when-idle",
                "--queue-storage-path",
                str(artifact_dir / "task_queue_store.json"),
                "--semantic-storage-path",
                str(artifact_dir / "semantic_memory_store.json"),
                "--procedural-storage-path",
                str(artifact_dir / "procedural_memory_store.json"),
                "--goal-storage-path",
                str(artifact_dir / "goals.json"),
                "--cognitive-evolution-storage-path",
                str(artifact_dir / "cognitive_evolution_history.json"),
                "--audit-storage-path",
                str(artifact_dir / "runtime_audit_store.json"),
                "--device-registry-path",
                str(artifact_dir / "device_registry.json"),
                "--self-defense-report-path",
                str(artifact_dir / "self_defense_latest.json"),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            env=env,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("[encerramento]", completed.stdout)
        self.assertTrue((artifact_dir / "procedural_memory_store.json").exists())

    @unittest.skipUnless(sys.platform.startswith("win"), "Launcher .cmd valido apenas em Windows.")
    def test_windows_launcher_api_direct_is_legacy_shim_to_server(self) -> None:
        """Confirma que o modo legado api-direct redireciona para o servidor oficial."""

        env = dict(os.environ)
        env["PYTHON_BIN"] = sys.executable

        completed = subprocess.run(
            [
                "cmd.exe",
                "/c",
                "jarvis.cmd",
                "api-direct",
                "--check-config",
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            env=env,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("modo api-direct foi aposentado", completed.stdout)
        self.assertIn("Redirecionando para o servidor oficial", completed.stdout)
        payload = extract_json_payload_from_output(completed.stdout)
        self.assertIn("mensagem", payload)
        self.assertIn("ambiente", payload)


if __name__ == "__main__":
    unittest.main()
