"""Interop real com codebase-memory-mcp v0.11.0.

O workflow dedicado baixa um release pinado e informa CBM_BINARY. A suite core
ignora este teste quando o binario nao foi provisionado.
"""

from pathlib import Path
import json
import os
import tempfile
import unittest

from runtime.mcp_stack import MCPStackConfig, OfficialMCPClientManager


CBM_BINARY = os.environ.get("CBM_BINARY")


@unittest.skipUnless(CBM_BINARY and Path(CBM_BINARY).exists(), "codebase-memory-mcp externo nao provisionado")
class CodebaseMemoryExternalTests(unittest.TestCase):
    def test_real_index_search_trace_and_architecture_over_official_mcp(self):
        project_root = Path(__file__).resolve().parents[1]
        fixture = (project_root / "tests" / "fixtures" / "codebase_sample").resolve()
        binary = Path(CBM_BINARY).resolve()

        with tempfile.TemporaryDirectory() as temp_dir:
            registry = Path(temp_dir) / "mcp_servers.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema_version": "1.0",
                        "servers": {
                            "codebase-memory": {
                                "enabled": True,
                                "transport": "stdio",
                                "command": str(binary),
                                "args": [],
                                "cwd": ".",
                                "env_allowlist": [
                                    "HOME",
                                    "PATH",
                                    "XDG_CONFIG_HOME",
                                    "XDG_DATA_HOME",
                                ],
                                "allowed_tools": [
                                    "index_repository",
                                    "list_projects",
                                    "search_graph",
                                    "trace_path",
                                    "get_architecture",
                                ],
                                "allowed_resources": [],
                                "allowed_prompts": [],
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
                    allowed_stdio_commands=(binary.name,),
                    max_result_chars=500000,
                )
            )

            discovered = manager.discover("codebase-memory")
            self.assertEqual(discovered["status"], "sucesso")
            tool_names = {item.get("name") for item in discovered.get("tools", [])}
            for required in {
                "index_repository",
                "search_graph",
                "trace_path",
                "get_architecture",
            }:
                self.assertIn(required, tool_names)

            indexed = manager.call_tool(
                "codebase-memory",
                "index_repository",
                {
                    "repo_path": str(fixture),
                    "name": "jarvis-cbm-fixture",
                    "persistence": False,
                },
            )
            self.assertEqual(indexed["status"], "sucesso", indexed)

            projects = manager.call_tool("codebase-memory", "list_projects", {})
            self.assertEqual(projects["status"], "sucesso", projects)
            self.assertIn(
                "jarvis-cbm-fixture",
                json.dumps(projects["resultado"], ensure_ascii=False),
            )

            searched = manager.call_tool(
                "codebase-memory",
                "search_graph",
                {
                    "project": "jarvis-cbm-fixture",
                    "name_pattern": ".*target.*",
                    "label": "Function",
                    "limit": 20,
                },
            )
            self.assertEqual(searched["status"], "sucesso", searched)
            self.assertIn(
                "target",
                json.dumps(searched["resultado"], ensure_ascii=False).lower(),
            )

            traced = manager.call_tool(
                "codebase-memory",
                "trace_path",
                {
                    "project": "jarvis-cbm-fixture",
                    "function_name": "target",
                    "direction": "inbound",
                    "depth": 3,
                },
            )
            self.assertEqual(traced["status"], "sucesso", traced)
            trace_text = json.dumps(traced["resultado"], ensure_ascii=False).lower()
            self.assertIn("caller", trace_text)

            architecture = manager.call_tool(
                "codebase-memory",
                "get_architecture",
                {"project": "jarvis-cbm-fixture"},
            )
            self.assertEqual(architecture["status"], "sucesso", architecture)
            architecture_text = json.dumps(
                architecture["resultado"],
                ensure_ascii=False,
            ).lower()
            self.assertIn("python", architecture_text)


if __name__ == "__main__":
    unittest.main()
