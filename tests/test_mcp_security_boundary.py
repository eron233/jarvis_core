"""Regressoes do limite de confianca MCP, sem subprocessos ou rede."""
from pathlib import Path
import tempfile
import unittest

from runtime.mcp_stack import MCPStackConfig, OfficialMCPClientManager, validate_mcp_http_url


class MCPSecurityBoundaryTests(unittest.TestCase):
    def test_invalid_ports_are_rejected_even_with_remote_enabled(self):
        for host in ("127.0.0.1", "localhost", "example.invalid"):
            for port in ("abc", "65536", "0"):
                for remote in (True, False):
                    with self.subTest(host=host, port=port, remote=remote):
                        self.assertIsNotNone(validate_mcp_http_url(
                            f"http://{host}:{port}/mcp", allow_remote=remote
                        ))

    def test_valid_loopback_remains_allowed(self):
        self.assertIsNone(validate_mcp_http_url("http://127.0.0.1:8000/mcp"))
        self.assertIsNone(validate_mcp_http_url("http://[::1]:8000/mcp"))

    def test_executable_paths_require_explicit_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "python")
            def target_factory(payload):
                return payload
            for command in (path, "./python", "../python"):
                manager = OfficialMCPClientManager(
                    config=MCPStackConfig(allowed_stdio_commands=("python",)),
                    stdio_target_factory=target_factory,
                )
                self.assertEqual(manager._build_target({
                    "transport": "stdio", "command": command
                })["status"], "bloqueado")
            manager = OfficialMCPClientManager(
                config=MCPStackConfig(allowed_stdio_commands=(path,)),
                stdio_target_factory=target_factory,
            )
            self.assertEqual(manager._build_target({
                "transport": "stdio", "command": path
            })["status"], "sucesso")
            self.assertEqual(manager._build_target({
                "transport": "stdio", "command": "python"
            })["status"], "bloqueado")
