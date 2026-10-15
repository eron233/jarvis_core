"""Regressoes do hunter: simulacoes nao provam vulnerabilidades."""
import tempfile
import unittest
from pathlib import Path

from security.vulnerability_hunter import AgenticVulnerabilityHunter


class HunterEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.hunter = AgenticVulnerabilityHunter(data_dir=self.root / "reports")

    def tearDown(self):
        self.tmp.cleanup()

    def test_sem_scanner_nao_declara_zero_day_ou_correcao(self):
        out = self.hunter.execute_hunting_campaign("Alvo", "src/")
        self.assertEqual(out["status"], "nao_executado")
        self.assertFalse(out["executado"])
        self.assertFalse(out["scanner_real_disponivel"])
        self.assertEqual(out["achados_vulnerabilidades"], [])
        self.assertEqual(out["evidencias"], [])
        self.assertEqual(out["ferramentas_evoluidas_autonomamente"], [])
        self.assertEqual(out["total_achados"], 0)
        self.assertFalse(out["ausencia_de_achados_significa_sistema_seguro"])
        self.assertNotIn("detectada", out["resumo_campanha_ptbr"].lower())

    def test_ferramentas_simuladas_nao_geram_achados(self):
        out = self.hunter.execute_hunting_campaign(
            "Alvo", "src/", simulated_tools=[
                {"nome": "Fuzzer", "codigo": "raise Exception('X')", "simular_falha": True},
            ]
        )
        self.assertTrue(out["simulation"])
        self.assertFalse(out["executado"])
        self.assertEqual(out["total_achados"], 0)
        self.assertEqual(out["achados_vulnerabilidades"], [])
        self.assertEqual(list((self.root / "reports").glob("*.json")).__len__(), 1)

    def test_nome_de_alvo_nao_permita_gravar_fora(self):
        self.hunter.execute_hunting_campaign("../../fora", ".")
        paths = list((self.root / "reports").glob("*.json"))
        self.assertEqual(len(paths), 1)
        self.assertEqual(paths[0].parent, self.root / "reports")
        self.assertFalse((self.root / "fora.json").exists())

    def test_nenhum_alvo_vazio(self):
        out = self.hunter.execute_hunting_campaign("", "src/")
        self.assertEqual(out["status"], "entrada_invalida")
        self.assertEqual(list((self.root / "reports").glob("*.json")), [])


if __name__ == "__main__":
    unittest.main()
