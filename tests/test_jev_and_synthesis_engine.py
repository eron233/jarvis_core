import unittest
import tempfile
import shutil
import time
import uuid
from pathlib import Path
from fastapi.testclient import TestClient

from interface.api.app import create_app
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.jev_decision_engine import JEVDecisionEngine
from runtime.multi_domain_synthesis_engine import MultiDomainSynthesisEngine


class TestJEVAndSynthesisIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.runtime = InternalAgentRuntime()
        self.runtime.bootstrap()

        # Sobrescrever diretorios dos motores para pasta temporaria
        self.runtime.jev_decision_engine = JEVDecisionEngine(data_dir=Path(self.temp_dir) / "jev")
        self.runtime.multi_domain_synthesis_engine = MultiDomainSynthesisEngine(data_dir=Path(self.temp_dir) / "synthesis")

        self.app = create_app(
            runtime=self.runtime,
            api_token="test-token",
            trusted_device_id="test-device-id",
        )
        self.client = TestClient(self.app)

    def _get_headers(self):
        return {
            "X-Jarvis-Token": "test-token",
            "X-Jarvis-Device-Id": "test-device-id",
            "X-Jarvis-Nonce": str(uuid.uuid4()),
            "X-Jarvis-Timestamp": str(int(time.time())),
        }

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_jev_endpoint(self):
        payload = [
            {"nome": "Estratégia 1", "utilidade_0_10": 9.0, "risco_0_10": 2.0, "custo_0_10": 1.0},
            {"nome": "Estratégia 2", "utilidade_0_10": 9.5, "risco_0_10": 9.0, "custo_0_10": 8.0},
        ]
        response = self.client.post(
            "/api/decisao/jev/avaliar?contexto=Expansao_de_Infraestrutura",
            json=payload,
            headers=self._get_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("relatorio_jev", data)
        self.assertEqual(data["relatorio_jev"]["decisao_otima_colapsada"]["opcao"], "Estratégia 1")

    def test_multi_domain_synthesis_endpoint(self):
        payload = {
            "seguranca": {"recomendacao": "Ativar MFA obrigatório", "prioridade": "alta"},
            "produto": {"recomendacao": "Simplificar login sem MFA", "prioridade": "media"},
        }
        response = self.client.post(
            "/api/sintese/multi-dominio/sintetizar?topico=Politica_de_Autenticacao",
            json=payload,
            headers=self._get_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("relatorio_sintese", data)
        self.assertEqual(len(data["relatorio_sintese"]["conflitos_detectados"]), 1)
        self.assertIn("Prevalência de Segurança", data["relatorio_sintese"]["decisao_sintetizada"])


if __name__ == "__main__":
    unittest.main()
