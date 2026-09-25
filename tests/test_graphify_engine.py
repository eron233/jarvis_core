"""
Testes unitários cobrindo o motor Graphify de análise topológica de projetos.
"""

from pathlib import Path
import tempfile
import unittest

from runtime.graphify_engine import GraphifyEngine
from runtime.internal_agent_runtime import InternalAgentRuntime


class GraphifyEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_graphify_analysis(self) -> None:
        engine = GraphifyEngine(data_dir=self.tmp_path)
        res = engine.analyze_and_graphify(
            project_title="Sistema de Pagamentos",
            description="Módulo de checkout com alta resiliência",
            raw_components=["Gateway", "Banco SQL", "Fila RabbitMQ", "Notificador SMS"],
        )

        self.assertEqual(res["projeto"], "Sistema de Pagamentos")
        self.assertEqual(len(res["grafo"]["nos"]), 4)
        self.assertGreater(len(res["grafo"]["arestas"]), 0)
        self.assertIn("resumo_topologico_ptbr", res)

    def test_graphify_extrai_termos_reais_do_texto(self) -> None:
        engine = GraphifyEngine(data_dir=self.tmp_path)
        res = engine.analyze_and_graphify(
            project_title="Loja",
            description="Checkout chama pagamento. Pagamento grava pedido. Pedido dispara nota fiscal.",
        )
        labels = {no["label"] for no in res["grafo"]["nos"]}
        self.assertTrue({"checkout", "pagamento", "pedido"} <= labels)
        self.assertNotIn("Core Executivo", labels)
        ids = {no["label"]: no["id"] for no in res["grafo"]["nos"]}
        pares = {frozenset((a["origem"], a["destino"])) for a in res["grafo"]["arestas"]}
        self.assertIn(frozenset((ids["checkout"], ids["pagamento"])), pares)
        self.assertNotIn(frozenset((ids["checkout"], ids["pedido"])), pares)

    def test_runtime_integration_of_graphify_engine(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "graphify_engine"))


if __name__ == "__main__":
    unittest.main()
