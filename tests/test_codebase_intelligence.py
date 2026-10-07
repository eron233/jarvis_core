"""Testes do ponto 8: autoconsciencia estrutural do proprio codigo."""

from pathlib import Path
import tempfile
import unittest

from learning.codebase_intelligence_engine import (
    CodebaseIntelligenceConfig,
    CodebaseIntelligenceEngine,
)
from runtime.internal_agent_runtime import InternalAgentRuntime


class _FakeMCPManager:
    def __init__(self):
        self.calls = []

    def discover(self, server_name):
        return {
            "status": "sucesso",
            "server": server_name,
            "tools": [
                {"name": "get_architecture"},
                {"name": "search_graph"},
                {"name": "trace_path"},
                {"name": "index_repository"},
            ],
        }

    def call_tool(self, server_name, tool_name, arguments=None):
        self.calls.append((server_name, tool_name, arguments or {}))
        return {
            "status": "sucesso",
            "server": server_name,
            "tool": tool_name,
            "resultado": {
                "tool": tool_name,
                "arguments": arguments or {},
            },
        }


class CodebaseLocalGraphTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "pkg").mkdir()
        (self.root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "pkg" / "core.py").write_text(
            """
def target(value):
    return value + 1

def caller():
    return target(41)
""".strip()
            + "\n",
            encoding="utf-8",
        )
        (self.root / "api.py").write_text(
            """
from pkg.core import caller

class FakeApp:
    def get(self, path):
        def deco(fn):
            return fn
        return deco

app = FakeApp()

@app.get("/health")
def health():
    return caller()
""".strip()
            + "\n",
            encoding="utf-8",
        )
        self.config = CodebaseIntelligenceConfig(
            project_root=self.root,
            db_path=self.root / "graph.sqlite3",
            local_ast_enabled=True,
            external_mcp_enabled=False,
            max_files=100,
            max_file_bytes=100000,
        )
        self.engine = CodebaseIntelligenceEngine(config=self.config)

    def tearDown(self):
        self.tmp.cleanup()

    def test_index_search_trace_and_routes_are_real(self):
        indexed = self.engine.index(prefer_external=False)

        self.assertEqual(indexed["status"], "sucesso")
        self.assertEqual(indexed["backend"], "python_ast_local")
        self.assertEqual(indexed["arquivos_indexados"], 3)
        self.assertEqual(indexed["estatisticas"]["rotas_http"], 1)

        search = self.engine.search("target", prefer_external=False)
        self.assertEqual(search["status"], "sucesso")
        self.assertEqual(search["quantidade"], 1)
        self.assertEqual(search["resultados"][0]["name"], "target")

        trace = self.engine.trace(
            "target",
            direction="inbound",
            depth=2,
            prefer_external=False,
        )
        self.assertEqual(trace["status"], "sucesso")
        self.assertTrue(
            any(edge.get("source_name", "").endswith(".caller") for edge in trace["arestas"])
        )
        self.assertTrue(
            all(edge["evidence_path"] for edge in trace["arestas"])
        )

    def test_impact_never_invents_risk_classification(self):
        self.engine.index(prefer_external=False)
        impact = self.engine.impact("target", depth=3)

        self.assertEqual(impact["status"], "sucesso")
        self.assertGreaterEqual(impact["quantidade"], 1)
        self.assertIsNone(impact["classificacao_risco"])
        self.assertIn("nao inventa", impact["observacao"])

    def test_snippet_is_bound_to_indexed_symbol_lines(self):
        self.engine.index(prefer_external=False)
        snippet = self.engine.snippet("target")

        self.assertEqual(snippet["status"], "sucesso")
        self.assertEqual(snippet["path"], "pkg/core.py")
        self.assertIn("def target", snippet["conteudo"])
        self.assertIn("return value + 1", snippet["conteudo"])

    def test_graphify_fallback_does_not_create_fake_dependencies(self):
        from runtime.graphify_engine import GraphifyEngine

        graphify = GraphifyEngine(data_dir=self.root / "graphify")
        result = graphify.analyze_and_graphify(
            project_title="Teste",
            description="API, banco e fila",
        )
        self.assertEqual(result["grafo"]["arestas"], [])
        self.assertFalse(result["arestas_inferidas_sem_evidencia"])


class CodebaseExternalMCPTests(unittest.TestCase):
    def test_external_backend_is_explicit_and_auto_index_is_blocked_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = _FakeMCPManager()
            config = CodebaseIntelligenceConfig(
                project_root=root,
                db_path=root / "graph.sqlite3",
                local_ast_enabled=True,
                external_mcp_enabled=True,
                mcp_server_name="codebase-memory",
                mcp_project_name="jarvis_core",
                external_auto_index=False,
            )
            engine = CodebaseIntelligenceEngine(
                config=config,
                mcp_manager=manager,
            )

            blocked = engine.external.index()
            self.assertEqual(blocked["status"], "bloqueado")
            self.assertEqual(manager.calls, [])

            architecture = engine.architecture(prefer_external=True)
            self.assertEqual(architecture["status"], "sucesso")
            self.assertEqual(architecture["backend"], "codebase-memory-mcp")
            self.assertEqual(manager.calls[-1][1], "get_architecture")
            self.assertEqual(
                manager.calls[-1][2]["project"],
                "jarvis_core",
            )

    def test_external_index_never_enables_persistent_repo_artifact_by_default(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manager = _FakeMCPManager()
            engine = CodebaseIntelligenceEngine(
                config=CodebaseIntelligenceConfig(
                    project_root=root,
                    db_path=root / "graph.sqlite3",
                    local_ast_enabled=True,
                    external_mcp_enabled=True,
                    mcp_server_name="codebase-memory",
                    mcp_project_name="jarvis_core",
                    external_auto_index=True,
                ),
                mcp_manager=manager,
            )

            result = engine.external.index()

            self.assertEqual(result["status"], "sucesso")
            _, tool, args = manager.calls[-1]
            self.assertEqual(tool, "index_repository")
            self.assertFalse(args["persistence"])
            self.assertEqual(args["repo_path"], str(root))


class CodebaseRuntimeIntegrationTests(unittest.TestCase):
    def test_runtime_exposes_codebase_intelligence_engine(self):
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "codebase_intelligence_engine"))
        self.assertIs(
            runtime.codebase_intelligence_engine.external.mcp_manager,
            runtime.mcp_manager,
        )


if __name__ == "__main__":
    unittest.main()
