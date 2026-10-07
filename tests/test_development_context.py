"""Testes do ponto 9: governanca de contexto de desenvolvimento."""

from pathlib import Path
import os
import tempfile
import unittest

from learning.development_context_engine import (
    DevelopmentContextConfig,
    DevelopmentContextEngine,
)
from runtime.internal_agent_runtime import InternalAgentRuntime


class _FakeMCPManager:
    def __init__(self, status="sucesso"):
        self.status = status
        self.calls = []

    def discover(self, server_name):
        return {
            "status": self.status,
            "server": server_name,
            "tools": [
                {"name": "safe_read"},
                {"name": "file_outline"},
                {"name": "read_range"},
                {"name": "changed_since"},
            ],
        }

    def call_tool(self, server_name, tool_name, arguments=None):
        self.calls.append((server_name, tool_name, arguments or {}))
        if self.status != "sucesso":
            return {"status": "erro", "motivo": "backend indisponivel"}
        return {
            "status": "sucesso",
            "server": server_name,
            "tool": tool_name,
            "resultado": {
                "structured_content": {
                    "projection": "content",
                    "path": (arguments or {}).get("path"),
                    "_receipt": {"decision": "CONTENT"},
                }
            },
        }


class DevelopmentContextLocalTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

        (self.root / "small.py").write_text(
            "def add(a, b):\n    return a + b\n",
            encoding="utf-8",
        )

        large_lines = ["def large_function(value):", "    total = value"]
        large_lines += [f"    total += {i}" for i in range(1, 190)]
        large_lines += ["    return total", ""]
        (self.root / "large.py").write_text(
            "\n".join(large_lines),
            encoding="utf-8",
        )

        (self.root / ".env.runtime").write_text(
            "SECRET=should-never-be-returned\n",
            encoding="utf-8",
        )
        (self.root / "package-lock.json").write_text(
            '{"lockfileVersion": 3}\n',
            encoding="utf-8",
        )
        (self.root / "binary.bin").write_bytes(b"abc\x00def")
        (self.root / "ignored.txt").write_text("hidden", encoding="utf-8")
        (self.root / ".graftignore").write_text("ignored.txt\n", encoding="utf-8")

        self.config = DevelopmentContextConfig(
            project_root=self.root,
            max_full_lines=150,
            max_full_bytes=12288,
            early_session_byte_cap=20480,
            mid_session_byte_cap=10240,
            late_session_byte_cap=4096,
            max_range_lines=250,
            local_enabled=True,
            external_graft_enabled=False,
            prefer_external=True,
        )
        self.engine = DevelopmentContextEngine(config=self.config)

    def tearDown(self):
        self.tmp.cleanup()

    def test_small_file_returns_content_with_receipt(self):
        result = self.engine.safe_read(
            "small.py",
            session_id="s1",
            prefer_external=False,
        )

        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["projection"], "content")
        self.assertIn("def add", result["content"])
        self.assertEqual(result["_receipt"]["decision"], "CONTENT")
        self.assertGreater(result["_receipt"]["bytes_returned"], 0)

    def test_large_python_returns_structural_outline_not_full_body(self):
        result = self.engine.safe_read(
            "large.py",
            session_id="s2",
            prefer_external=False,
        )

        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["projection"], "outline")
        self.assertNotIn("content", result)
        names = {item["name"] for item in result["outline"]}
        self.assertIn("large_function", names)
        self.assertGreater(result["_receipt"]["bytes_avoided"], 0)

    def test_secret_binary_lockfile_and_graftignore_are_refused(self):
        expected = {
            ".env.runtime": "SECRET",
            "binary.bin": "BINARY",
            "package-lock.json": "LOCKFILE",
            "ignored.txt": "GRAFTIGNORE",
        }
        for path, reason in expected.items():
            with self.subTest(path=path):
                result = self.engine.safe_read(
                    path,
                    session_id="refusals",
                    prefer_external=False,
                )
                self.assertEqual(result["status"], "bloqueado")
                self.assertEqual(result["projection"], "refused")
                self.assertEqual(result["reason"], reason)
                self.assertNotIn("content", result)

    def test_outside_project_is_refused(self):
        result = self.engine.safe_read(
            "../outside.txt",
            prefer_external=False,
        )
        self.assertEqual(result["status"], "bloqueado")
        self.assertEqual(result["reason"], "OUTSIDE_PROJECT")

    def test_range_is_bounded_and_secret_policy_still_applies(self):
        ok = self.engine.read_range(
            "large.py",
            1,
            20,
            session_id="range",
            prefer_external=False,
        )
        self.assertEqual(ok["status"], "sucesso")
        self.assertEqual(ok["projection"], "range")
        self.assertEqual(ok["start"], 1)
        self.assertEqual(ok["end"], 20)

        too_large = self.engine.read_range(
            "large.py",
            1,
            300,
            session_id="range",
            prefer_external=False,
        )
        self.assertEqual(too_large["status"], "bloqueado")
        self.assertEqual(too_large["reason"], "RANGE_TOO_LARGE")

        secret = self.engine.read_range(
            ".env.runtime",
            1,
            1,
            session_id="range",
            prefer_external=False,
        )
        self.assertEqual(secret["status"], "bloqueado")
        self.assertEqual(secret["reason"], "SECRET")

    def test_budget_cap_forces_outline_even_for_small_file(self):
        result = self.engine.safe_read(
            "small.py",
            session_id="budget",
            budget_remaining=20,
            prefer_external=False,
        )
        self.assertEqual(result["projection"], "outline")
        self.assertEqual(result["reason"], "BUDGET_CAP")

    def test_repeated_reads_trip_session_warning(self):
        for _ in range(4):
            self.engine.safe_read(
                "small.py",
                session_id="repeat",
                prefer_external=False,
            )
        status = self.engine.session_status("repeat")
        self.assertIn("REPEATED_PATH_READ", status["tripwires"])
        self.assertEqual(status["paths"]["small.py"], 4)

    def test_symlink_is_refused_when_supported(self):
        target = self.root / "target.txt"
        target.write_text("safe", encoding="utf-8")
        link = self.root / "link.txt"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symlink indisponivel neste host")

        result = self.engine.safe_read(
            "link.txt",
            prefer_external=False,
        )
        self.assertEqual(result["status"], "bloqueado")
        self.assertEqual(result["reason"], "SYMLINK_REFUSED")


class DevelopmentContextExternalTests(unittest.TestCase):
    def test_external_graft_is_used_only_when_explicitly_enabled(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            manager = _FakeMCPManager()
            engine = DevelopmentContextEngine(
                config=DevelopmentContextConfig(
                    project_root=root,
                    external_graft_enabled=True,
                    graft_server_name="graft-context",
                    prefer_external=True,
                ),
                mcp_manager=manager,
            )

            result = engine.safe_read("a.py", intent="understand file")

            self.assertEqual(result["status"], "sucesso")
            self.assertEqual(result["backend"], "flyingrobots-graft")
            server, tool, args = manager.calls[-1]
            self.assertEqual(server, "graft-context")
            self.assertEqual(tool, "safe_read")
            self.assertEqual(args["path"], "a.py")
            self.assertEqual(args["intent"], "understand file")
            self.assertNotIn("cwd", args)

    def test_external_failure_falls_back_to_local_governor(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            manager = _FakeMCPManager(status="erro")
            engine = DevelopmentContextEngine(
                config=DevelopmentContextConfig(
                    project_root=root,
                    external_graft_enabled=True,
                    prefer_external=True,
                ),
                mcp_manager=manager,
            )

            result = engine.safe_read("a.py")

            self.assertEqual(result["status"], "sucesso")
            self.assertEqual(result["backend"], "local_context_governor")
            self.assertEqual(result["projection"], "content")


class DevelopmentContextRuntimeTests(unittest.TestCase):
    def test_runtime_exposes_context_governor_sharing_mcp_manager(self):
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "development_context_engine"))
        self.assertIs(
            runtime.development_context_engine.external.mcp_manager,
            runtime.mcp_manager,
        )


if __name__ == "__main__":
    unittest.main()
