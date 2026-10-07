"""Interop real com flyingrobots/graft v0.14.0.

O workflow dedicado baixa o tarball oficial pinado, verifica SHA-256, instala
em diretório isolado e informa GRAFT_CONTEXT_BINARY. A suite core pula este
teste quando o binário externo não está provisionado.

A prova usa um repositório Git temporário próprio dentro da árvore de testes,
evitando depender de particularidades do checkout do GitHub Actions.
"""

from pathlib import Path
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from runtime.mcp_stack import MCPStackConfig, OfficialMCPClientManager


GRAFT_BINARY = os.environ.get("GRAFT_CONTEXT_BINARY")


@unittest.skipUnless(
    GRAFT_BINARY and Path(GRAFT_BINARY).exists(),
    "flyingrobots/graft externo nao provisionado",
)
class FlyingRobotsGraftIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(__file__).resolve().parents[1]
        fixtures_root = self.project_root / "tests" / "fixtures"
        fixtures_root.mkdir(parents=True, exist_ok=True)
        self.temp_repo = Path(
            tempfile.mkdtemp(prefix="graft-runtime-", dir=str(fixtures_root))
        )

        (self.temp_repo / "small.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n",
            encoding="utf-8",
        )
        (self.temp_repo / "large.py").write_text(
            "\n".join(
                [
                    "def giant(value: int) -> int:",
                    "    total = value",
                    *[f"    total += {i}" for i in range(1, 190)],
                    "    return total",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (self.temp_repo / ".env.graft-runtime").write_text(
            "SUPER_SECRET_VALUE=never-return-this\n",
            encoding="utf-8",
        )

        git_env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Jarvis CI",
            "GIT_AUTHOR_EMAIL": "jarvis-ci@example.invalid",
            "GIT_COMMITTER_NAME": "Jarvis CI",
            "GIT_COMMITTER_EMAIL": "jarvis-ci@example.invalid",
        }
        subprocess.run(
            ["git", "init", "-q"],
            cwd=self.temp_repo,
            env=git_env,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "add", "."],
            cwd=self.temp_repo,
            env=git_env,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-qm", "fixture"],
            cwd=self.temp_repo,
            env=git_env,
            check=True,
            capture_output=True,
            text=True,
        )
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.temp_repo,
            env=git_env,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.assertEqual(len(head), 40)

        direct = subprocess.run(
            [
                str(Path(GRAFT_BINARY).resolve()),
                "--cwd",
                str(self.temp_repo),
                "read",
                "safe",
                "small.py",
                "--json",
            ],
            cwd=self.temp_repo,
            env=os.environ.copy(),
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            direct.returncode,
            0,
            f"Graft CLI preflight failed. stdout={direct.stdout!r} stderr={direct.stderr!r}",
        )
        self.assertIn("content", direct.stdout)

        registry = self.temp_repo / "graft_registry_runtime.json"
        relative_repo = self.temp_repo.relative_to(self.project_root).as_posix()
        registry.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "servers": {
                        "graft-context": {
                            "enabled": True,
                            "transport": "stdio",
                            "command": str(Path(GRAFT_BINARY).resolve()),
                            "args": ["serve"],
                            "cwd": relative_repo,
                            "env_allowlist": [
                                "PATH",
                                "HOME",
                                "USERPROFILE",
                                "LOCALAPPDATA",
                                "APPDATA",
                            ],
                            "allowed_tools": [
                                "safe_read",
                                "file_outline",
                                "read_range",
                                "changed_since",
                            ],
                            "allowed_resources": [],
                            "allowed_prompts": [],
                        }
                    },
                }
            ),
            encoding="utf-8",
        )
        self.registry = registry
        self.manager = OfficialMCPClientManager(
            config=MCPStackConfig(
                enabled=True,
                registry_path=registry,
                allowed_stdio_commands=(Path(GRAFT_BINARY).resolve().name,),
                max_result_chars=500000,
            )
        )

    def tearDown(self):
        shutil.rmtree(self.temp_repo, ignore_errors=True)

    @staticmethod
    def _text(result):
        return json.dumps(result, ensure_ascii=False)

    def test_real_graft_governs_reads_over_official_mcp(self):
        discovered = self.manager.discover("graft-context")
        self.assertEqual(discovered["status"], "sucesso", discovered)
        names = {item.get("name") for item in discovered.get("tools", [])}
        for required in {"safe_read", "file_outline", "read_range", "changed_since"}:
            self.assertIn(required, names)

        small = self.manager.call_tool(
            "graft-context",
            "safe_read",
            {
                "path": "small.py",
                "intent": "understand fixture",
            },
        )
        self.assertEqual(small["status"], "sucesso", small)
        small_text = self._text(small["resultado"])
        self.assertIn('"projection": "content"', small_text)
        self.assertIn("def add", small_text)
        self.assertIn("_receipt", small_text)

        large = self.manager.call_tool(
            "graft-context",
            "safe_read",
            {"path": "large.py"},
        )
        self.assertEqual(large["status"], "sucesso", large)
        large_text = self._text(large["resultado"])
        self.assertIn('"projection": "outline"', large_text)
        self.assertIn("giant", large_text)
        self.assertIn("_receipt", large_text)

        outline = self.manager.call_tool(
            "graft-context",
            "file_outline",
            {"path": "large.py"},
        )
        self.assertEqual(outline["status"], "sucesso", outline)
        outline_text = self._text(outline["resultado"])
        self.assertIn("giant", outline_text)

        ranged = self.manager.call_tool(
            "graft-context",
            "read_range",
            {
                "path": "large.py",
                "start": 1,
                "end": 10,
            },
        )
        self.assertEqual(ranged["status"], "sucesso", ranged)
        range_text = self._text(ranged["resultado"])
        self.assertIn("def giant", range_text)
        self.assertIn("total += 1", range_text)

        secret = self.manager.call_tool(
            "graft-context",
            "safe_read",
            {"path": ".env.graft-runtime"},
        )
        self.assertEqual(secret["status"], "sucesso", secret)
        secret_text = self._text(secret["resultado"])
        self.assertIn('"projection": "refused"', secret_text)
        self.assertIn("SECRET", secret_text)
        self.assertNotIn("never-return-this", secret_text)


if __name__ == "__main__":
    unittest.main()
