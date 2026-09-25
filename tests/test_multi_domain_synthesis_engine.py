import unittest
from pathlib import Path
import tempfile
import shutil

from runtime.multi_domain_synthesis_engine import MultiDomainSynthesisEngine


class TestMultiDomainSynthesisEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.engine = MultiDomainSynthesisEngine(data_dir=Path(self.temp_dir))

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_synthesize_domain_perspectives(self):
        inputs = {
            "seguranca": {"recomendacao": "Fechar porta 8080 externa", "prioridade": "alta"},
            "engenharia": {"recomendacao": "Abrir porta 8080 para serviço API", "prioridade": "media"},
        }

        result = self.engine.synthesize_domain_perspectives(
            topic="Configuração de portas de rede",
            domain_inputs=inputs,
        )

        self.assertEqual(len(result["dominios_consultados"]), 2)
        self.assertEqual(len(result["conflitos_detectados"]), 1)
        self.assertIn("Prevalência de Segurança", result["decisao_sintetizada"])


if __name__ == "__main__":
    unittest.main()
