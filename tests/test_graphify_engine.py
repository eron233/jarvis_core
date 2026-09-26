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

    def test_runtime_integration_of_graphify_engine(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "graphify_engine"))


if __name__ == "__main__":
    unittest.main()


class GraphifyDescriptionUsageTests(unittest.TestCase):
    """A descricao do projeto precisa influenciar o grafo produzido."""

    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.engine = GraphifyEngine(data_dir=Path(self.tmp_dir.name))

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_extrai_nos_da_descricao(self) -> None:
        """
        Sem componentes informados, o motor devolvia sempre os mesmos cinco nos
        genericos e ignorava a descricao, embora a docstring dissesse que a
        transformava em grafo.
        """

        resultado = self.engine.analyze_and_graphify(
            project_title="Pagamentos",
            description="Gateway de cartao, fila de mensagens e painel de conciliacao",
        )

        rotulos = [no["label"] for no in resultado["grafo"]["nos"]]
        self.assertEqual(resultado["origem_dos_nos"], "extraidos_da_descricao")
        self.assertTrue(resultado["descricao_utilizada"])
        self.assertIn("Gateway de cartao", rotulos)
        self.assertIn("painel de conciliacao", rotulos)

    def test_projetos_diferentes_produzem_grafos_diferentes(self) -> None:
        """Duas descricoes distintas nao podem gerar o mesmo grafo."""

        primeiro = self.engine.analyze_and_graphify("A", "Sensor de temperatura, atuador e rele")
        segundo = self.engine.analyze_and_graphify("B", "Catalogo de produtos, carrinho e checkout")

        self.assertNotEqual(
            [no["label"] for no in primeiro["grafo"]["nos"]],
            [no["label"] for no in segundo["grafo"]["nos"]],
        )

    def test_descricao_vazia_declara_o_modelo_generico(self) -> None:
        """Quando nada pode ser extraido, o relatorio precisa dizer isso."""

        resultado = self.engine.analyze_and_graphify(project_title="Vazio", description="")

        self.assertEqual(resultado["origem_dos_nos"], "modelo_generico")
        self.assertFalse(resultado["descricao_utilizada"])
        self.assertIn("modelo genérico", resultado["resumo_topologico_ptbr"])

    def test_componentes_informados_tem_prioridade(self) -> None:
        """Quem passa componentes explicitos continua mandando no grafo."""

        resultado = self.engine.analyze_and_graphify(
            project_title="Explicito",
            description="descricao que deve ser ignorada aqui",
            raw_components=["Alfa", "Beta"],
        )

        self.assertEqual(resultado["origem_dos_nos"], "componentes_informados")
        self.assertEqual([no["label"] for no in resultado["grafo"]["nos"]], ["Alfa", "Beta"])

    def test_resumo_nao_afirma_resiliencia_sem_avaliar(self) -> None:
        """O resumo terminava sempre com "Fluxo totalmente fechado e resiliente"."""

        resultado = self.engine.analyze_and_graphify("X", "Um componente qualquer")

        self.assertNotIn("resiliente", resultado["resumo_topologico_ptbr"])
