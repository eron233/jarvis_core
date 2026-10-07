"""Interop real com o SDK MCP oficial v2.

Este arquivo e ignorado pela suite core quando o pacote opcional mcp nao esta
instalado. O workflow MCP dedicado instala requirements-mcp.txt e executa este
teste de ponta a ponta.
"""

from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest

from runtime.mcp_stack import MCPStackConfig, OfficialMCPClientManager


@unittest.skipUnless(importlib.util.find_spec("mcp") is not None, "SDK MCP opcional nao instalado")
class OfficialMCPSDKIntegrationTests(unittest.TestCase):
    def test_stdio_discover_call_resource_and_prompt_roundtrip(self):
        project_root = Path(__file__).resolve().parents[1]
        fixture = project_root / "tests" / "fixtures" / "mcp_echo_server.py"

        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "mcp_servers.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "servers": {
                            "real_stdio": {
                                "enabled": True,
                                "transport": "stdio",
                                "command": sys.executable,
                                "args": [str(fixture)],
                                "cwd": ".",
                                "env_allowlist": [],
                                "allowed_tools": ["echo"],
                                "allowed_resources": ["echo://hello"],
                                "allowed_prompts": ["greet"],
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            manager = OfficialMCPClientManager(
                config=MCPStackConfig(
                    enabled=True,
                    registry_path=registry,
                    allowed_stdio_commands=(Path(sys.executable).name,),
                )
            )

            discovered = manager.discover("real_stdio")
            self.assertEqual(discovered["status"], "sucesso")
            self.assertIn(discovered["protocol_version"], {"2026-07-28", "2025-11-25"})
            self.assertIn("echo", {item["name"] for item in discovered["tools"]})
            self.assertIn(
                "echo://hello",
                {str(item["uri"]) for item in discovered["resources"]},
            )
            self.assertIn("greet", {item["name"] for item in discovered["prompts"]})

            called = manager.call_tool("real_stdio", "echo", {"text": "Jarvis"})
            self.assertEqual(called["status"], "sucesso")
            serialized_call = json.dumps(called["resultado"], ensure_ascii=False)
            self.assertIn("Jarvis", serialized_call)

            resource = manager.read_resource("real_stdio", "echo://hello")
            self.assertEqual(resource["status"], "sucesso")
            self.assertIn(
                "hello-from-real-mcp-resource",
                json.dumps(resource["resultado"], ensure_ascii=False),
            )

            prompt = manager.get_prompt("real_stdio", "greet", {"name": "Eron"})
            self.assertEqual(prompt["status"], "sucesso")
            self.assertIn(
                "Eron",
                json.dumps(prompt["resultado"], ensure_ascii=False),
            )


if __name__ == "__main__":
    unittest.main()
