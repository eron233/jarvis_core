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

    def test_components_extracted_from_description_become_nodes(self) -> None:
        """Sem raw_components, os nós devem vir de tokens reais extraídos da descrição."""
        engine = GraphifyEngine(data_dir=self.tmp_path)
        res = engine.analyze_and_graphify(
            project_title="Assistente Pessoal",
            description="Reconhecimento de voz, motor de decisão e memória semântica",
        )

        labels = [n["label"] for n in res["grafo"]["nos"]]
        self.assertEqual(len(labels), 3)
        # Cada fragmento separado por vírgula/"e" vira um nó, sem lista fixa hardcoded
        joined = " ".join(labels).lower()
        self.assertIn("reconhecimento", joined)
        self.assertIn("decis", joined)  # "decisão" sem stopwords
        self.assertIn("mem", joined)  # "memória"

    def test_density_matches_formula_and_hub_is_max_degree_node(self) -> None:
        engine = GraphifyEngine(data_dir=self.tmp_path)
        res = engine.analyze_and_graphify(
            project_title="Grafo Teste",
            description="ignorado",
            raw_components=["A", "B", "C", "D"],
        )

        n = len(res["grafo"]["nos"])
        m = len(res["grafo"]["arestas"])
        densidade_esperada = round(m / (n * (n - 1)), 4)
        self.assertEqual(res["estatisticas"]["densidade_topologica"], densidade_esperada)

        graus = res["estatisticas"]["graus"]
        hub_id = res["estatisticas"]["hub_id"]
        self.assertEqual(graus[hub_id], max(graus.values()))
        self.assertEqual(res["estatisticas"]["grau_maximo"], max(graus.values()))

        # É um grafo em anel fechado por retroalimentação -> deve ser detectado como cíclico
        self.assertTrue(res["estatisticas"]["tem_ciclo"])

        # importancia_score de cada nó deve refletir o grau real (não fórmula arbitrária antiga)
        for node in res["grafo"]["nos"]:
            self.assertEqual(node["importancia_score"], graus[node["id"]] * 1.0)

    def test_single_node_has_zero_density_and_no_cycle(self) -> None:
        engine = GraphifyEngine(data_dir=self.tmp_path)
        res = engine.analyze_and_graphify(
            project_title="Projeto Único",
            description="ignorado",
            raw_components=["Único Componente"],
        )
        self.assertEqual(res["estatisticas"]["total_arestas"], 0)
        self.assertEqual(res["estatisticas"]["densidade_topologica"], 0.0)
        self.assertFalse(res["estatisticas"]["tem_ciclo"])

    def test_runtime_integration_of_graphify_engine(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "graphify_engine"))


if __name__ == "__main__":
    unittest.main()
