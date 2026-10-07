"""Testes do ponto 7: MCP oficial, least privilege e interoperabilidade."""

from pathlib import Path
import json
import tempfile
from types import SimpleNamespace
import unittest

from runtime.mcp_stack import (
    MCPStackConfig,
    OfficialMCPClientManager,
    validate_mcp_http_url,
)
from runtime.internal_agent_runtime import InternalAgentRuntime


class _FakeClient:
    instances = []

    def __init__(self, target):
        self.target = target
        self.protocol_version = "2026-07-28"
        self.server_info = SimpleNamespace(name="fake-server", version="2.0")
        self.server_capabilities = {"tools": True, "resources": True, "prompts": True}
        self.instructions = "fake instructions"
        self.calls = []
        _FakeClient.instances.append(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def list_tools(self):
        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="safe_tool",
                    title="Safe Tool",
                    description="Ferramenta permitida",
                    input_schema={"type": "object"},
                ),
                SimpleNamespace(
                    name="dangerous_tool",
                    title="Dangerous Tool",
                    description="Ferramenta não permitida",
                    input_schema={"type": "object"},
                ),
            ]
        )

    async def list_resources(self):
        return SimpleNamespace(
            resources=[
                SimpleNamespace(uri="jarvis://allowed", name="Allowed"),
                SimpleNamespace(uri="jarvis://blocked", name="Blocked"),
            ]
        )

    async def list_prompts(self):
        return SimpleNamespace(
            prompts=[
                SimpleNamespace(name="allowed_prompt", description="Prompt permitido"),
                SimpleNamespace(name="blocked_prompt", description="Prompt bloqueado"),
            ]
        )

    async def call_tool(self, name, arguments):
        self.calls.append(("tool", name, arguments))
        return SimpleNamespace(
            structured_content={"ok": True, "name": name, "arguments": arguments},
            content=[],
            is_error=False,
        )

    async def read_resource(self, uri):
        self.calls.append(("resource", uri))
        return SimpleNamespace(contents=[{"uri": uri, "text": "conteúdo real"}])

    async def get_prompt(self, name, arguments=None):
        self.calls.append(("prompt", name, arguments or {}))
        return SimpleNamespace(
            description="prompt real",
            messages=[{"role": "user", "content": {"type": "text", "text": "Olá"}}],
        )


class MCPStackTests(unittest.TestCase):
    def setUp(self):
        _FakeClient.instances.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.registry = self.root / "mcp_servers.json"
        self.registry.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "servers": {
                        "local": {
                            "enabled": True,
                            "transport": "streamable-http",
                            "url": "http://127.0.0.1:8000/mcp",
                            "allowed_tools": ["safe_tool"],
                            "allowed_resources": ["jarvis://allowed"],
                            "allowed_prompts": ["allowed_prompt"],
                        },
                        "blocked_stdio": {
                            "enabled": True,
                            "transport": "stdio",
                            "command": "powershell.exe",
                            "args": ["-Command", "Write-Host hi"],
                            "env_allowlist": [],
                            "allowed_tools": [],
                            "allowed_resources": [],
                            "allowed_prompts": [],
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.tmp.cleanup()

    def _manager(self):
        return OfficialMCPClientManager(
            config=MCPStackConfig(
                enabled=True,
                registry_path=self.registry,
                allow_remote_http=False,
                allowed_stdio_commands=("python", "python3", "uv", "uvx"),
            ),
            client_factory=_FakeClient,
        )

    def test_defaults_are_disabled_and_local_first(self):
        config = MCPStackConfig.from_env({}, project_root=self.root)
        self.assertFalse(config.enabled)
        self.assertFalse(config.allow_remote_http)
        self.assertIn("python", config.allowed_stdio_commands)

    def test_remote_http_is_blocked_by_default(self):
        self.assertIsNone(validate_mcp_http_url("http://127.0.0.1:8000/mcp"))
        self.assertIsNotNone(validate_mcp_http_url("http://10.0.0.8:8000/mcp"))
        self.assertIsNotNone(validate_mcp_http_url("http://user:pass@127.0.0.1:8000/mcp"))

    def test_discovery_does_not_grant_execution_permission(self):
        manager = self._manager()
        result = manager.discover("local")

        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["protocol_version"], "2026-07-28")
        self.assertEqual(len(result["tools"]), 2)
        self.assertEqual(len(result["resources"]), 2)
        self.assertEqual(len(result["prompts"]), 2)
        self.assertEqual(_FakeClient.instances[-1].calls, [])

    def test_allowed_tool_executes_and_blocked_tool_does_not_connect(self):
        manager = self._manager()

        allowed = manager.call_tool("local", "safe_tool", {"x": 1})
        self.assertEqual(allowed["status"], "sucesso")
        self.assertTrue(allowed["resultado"]["structured_content"]["ok"])

        before = len(_FakeClient.instances)
        blocked = manager.call_tool("local", "dangerous_tool", {"x": 2})
        after = len(_FakeClient.instances)

        self.assertEqual(blocked["status"], "bloqueado")
        self.assertEqual(before, after)

    def test_resource_and_prompt_have_independent_allowlists(self):
        manager = self._manager()

        resource = manager.read_resource("local", "jarvis://allowed")
        self.assertEqual(resource["status"], "sucesso")

        blocked_resource = manager.read_resource("local", "jarvis://blocked")
        self.assertEqual(blocked_resource["status"], "bloqueado")

        prompt = manager.get_prompt("local", "allowed_prompt", {"name": "Eron"})
        self.assertEqual(prompt["status"], "sucesso")

        blocked_prompt = manager.get_prompt("local", "blocked_prompt")
        self.assertEqual(blocked_prompt["status"], "bloqueado")

    def test_stdio_command_outside_allowlist_is_blocked_before_launch(self):
        manager = self._manager()
        result = manager.discover("blocked_stdio")

        self.assertEqual(result["status"], "bloqueado")
        self.assertIn("allowlist", result["motivo"])
        self.assertEqual(_FakeClient.instances, [])

    def test_runtime_exposes_official_mcp_manager_without_requiring_sdk(self):
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "mcp_manager"))
        status = runtime.mcp_manager.status()
        self.assertIn("official_protocol", status)
        self.assertTrue(status["official_protocol"])
        self.assertFalse(status["fabricated_mcp"])


if __name__ == "__main__":
    unittest.main()
