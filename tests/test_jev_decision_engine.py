import unittest
from pathlib import Path
import tempfile
import shutil

from runtime.jev_decision_engine import JEVDecisionEngine


class TestJEVDecisionEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.engine = JEVDecisionEngine(data_dir=Path(self.temp_dir))

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_evaluate_decision_vector(self):
        options = [
            {"nome": "Plano A", "utilidade_0_10": 8.5, "risco_0_10": 1.0, "custo_0_10": 2.0},
            {"nome": "Plano B (Muito Arriscado)", "utilidade_0_10": 9.0, "risco_0_10": 9.0, "custo_0_10": 5.0},
        ]
        result = self.engine.evaluate_decision_vector(
            decision_context="Escolha do pipeline de deployment",
            options=options,
        )

        self.assertEqual(result["total_opcoes_avaliadas"], 2)
        self.assertEqual(result["decisao_otima_colapsada"]["opcao"], "Plano A")
        self.assertIn("Decisão Executiva JEV", result["justificativa_jev_ptbr"])


if __name__ == "__main__":
    unittest.main()
