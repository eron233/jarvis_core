"""Interop real com flyingrobots/graft v0.14.0.

O workflow dedicado baixa o tarball oficial pinado, verifica SHA-256, instala
em diretório isolado e informa GRAFT_CONTEXT_BINARY. A suite core pula este
teste quando o binário externo não está provisionado.
"""

from pathlib import Path
import json
import os
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
        self.fixture_dir = self.project_root / "tests" / "fixtures" / "graft_context_sample"
        self.large_file = self.fixture_dir / "large_runtime.py"
        self.secret_file = self.fixture_dir / ".env.graft-runtime"
        self.large_file.write_text(
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
        self.secret_file.write_text(
            "SUPER_SECRET_VALUE=never-return-this\n",
            encoding="utf-8",
        )

        registry = self.fixture_dir / "graft_registry_runtime.json"
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
                            "cwd": ".",
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
        for path in (self.large_file, self.secret_file, self.registry):
            try:
                path.unlink()
            except FileNotFoundError:
                pass

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
                "path": "tests/fixtures/graft_context_sample/small.py",
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
            {
                "path": "tests/fixtures/graft_context_sample/large_runtime.py",
            },
        )
        self.assertEqual(large["status"], "sucesso", large)
        large_text = self._text(large["resultado"])
        self.assertIn('"projection": "outline"', large_text)
        self.assertIn("giant", large_text)
        self.assertIn("_receipt", large_text)

        outline = self.manager.call_tool(
            "graft-context",
            "file_outline",
            {
                "path": "tests/fixtures/graft_context_sample/large_runtime.py",
            },
        )
        self.assertEqual(outline["status"], "sucesso", outline)
        outline_text = self._text(outline["resultado"])
        self.assertIn("giant", outline_text)

        ranged = self.manager.call_tool(
            "graft-context",
            "read_range",
            {
                "path": "tests/fixtures/graft_context_sample/large_runtime.py",
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
            {
                "path": "tests/fixtures/graft_context_sample/.env.graft-runtime",
            },
        )
        self.assertEqual(secret["status"], "sucesso", secret)
        secret_text = self._text(secret["resultado"])
        self.assertIn('"projection": "refused"', secret_text)
        self.assertIn("SECRET", secret_text)
        self.assertNotIn("never-return-this", secret_text)


if __name__ == "__main__":
    unittest.main()
