"""Testes de portabilidade dos entrypoints oficiais do JARVIS."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from startup_bootstrap import ensure_project_root_on_path


def make_startup_artifact_dir(name: str) -> Path:
    return PROJECT_ROOT / "tests" / "_startup_artifacts" / name


def reset_directory(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


class StartupPortabilityTests(unittest.TestCase):
    def test_bootstrap_helper_discovers_project_root(self) -> None:
        nested_path = PROJECT_ROOT / "runtime" / "server.py"
        project_root = ensure_project_root_on_path(nested_path)

        self.assertEqual(project_root, PROJECT_ROOT)
        self.assertEqual(str(PROJECT_ROOT), sys.path[0])

    def test_main_entrypoint_runs_with_current_interpreter(self) -> None:
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
            "--goal-storage-path",
            str(artifact_dir / "goals.json"),
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
        self.assertTrue((artifact_dir / "goals.json").exists())

    def test_server_check_config_runs_with_current_interpreter(self) -> None:
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
        payload = json.loads(completed.stdout)
        self.assertIn("mensagem", payload)
        self.assertIn("ambiente", payload)

    @unittest.skipUnless(sys.platform.startswith("win"), "Launcher .cmd valido apenas em Windows.")
    def test_windows_launcher_runs_loop_with_explicit_interpreter(self) -> None:
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
                "--goal-storage-path",
                str(artifact_dir / "goals.json"),
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


if __name__ == "__main__":
    unittest.main()
