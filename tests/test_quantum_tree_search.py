"""
Testes unitários cobrindo o motor de busca em árvore paralela estilo quântico e questionamento socrático dos 11 pilares.
"""

from pathlib import Path
import tempfile
import unittest

from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.quantum_tree_search_engine import QuantumTreeSearchEngine


class QuantumTreeSearchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp_dir.name)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_quantum_tree_search_and_pruning(self) -> None:
        engine = QuantumTreeSearchEngine(data_dir=self.tmp_path)

        hypotheses = [
            {"nome": "Hipótese 1 - Open Source", "open_source": True, "custo_estimado_brl": 0.0, "diferencial_inovacao_0_10": 9.0},
            {"nome": "Hipótese 2 - Cripto Baixo Custo", "open_source": True, "custo_estimado_brl": 30.0, "diferencial_inovacao_0_10": 9.5},
            {"nome": "Hipótese 3 - Proprietária Cara", "open_source": False, "custo_estimado_brl": 1000.0, "diferencial_inovacao_0_10": 5.0},
        ]

        res = engine.explore_hypotheses_tree(
            domain_goal="Criar produto inovador",
            initial_hypotheses=hypotheses,
            available_crypto_budget_brl=100.0,
        )

        self.assertEqual(res["total_hipoteses_avaliadas"], 3)
        self.assertEqual(res["total_hipoteses_mantidas_pos_poda"], 2)  # A hipótese 3 deve ser podada
        self.assertTrue(res["aprovado_para_execucao"])

        # Checa as 11 perguntas socráticas
        socratic_answers = res["validacao_socratica_11_pilares"]["perguntas_e_respostas_11_pilares"]
        self.assertEqual(len(socratic_answers), 11)

    def test_runtime_integration_of_quantum_tree_engine(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()

        self.assertTrue(hasattr(runtime, "quantum_tree_search_engine"))


if __name__ == "__main__":
    unittest.main()
