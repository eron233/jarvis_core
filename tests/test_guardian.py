"""Guardian v0: nao confundir estado do Defender com varredura real do disco."""
import json
import os
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from interface.api.app import create_app
from runtime.internal_agent_runtime import InternalAgentRuntime
from security.guardian import Guardian, _STATUS_SCRIPT, _DETECTIONS_SCRIPT


def _result(obj, code=0):
    return SimpleNamespace(
        returncode=code,
        stdout=json.dumps(obj).encode("utf-8"),
        stderr=b"nao_expor_detalhes_privados",
    )


class GuardianUnitTests(unittest.TestCase):
    def setUp(self):
        self.guardian = Guardian()

    def test_linux_retorna_indisponivel_sem_alegar_protecao(self):
        with patch("security.guardian.platform.system", return_value="Linux"):
            out = self.guardian.observe()
        self.assertEqual(out["status"], "indisponivel")
        self.assertIsNone(out["protecao"])
        self.assertIsNone(out["deteccoes_historicas"])
        self.assertIsNone(out["ameacas_ativas_confirmadas"])
        self.assertFalse(out["maquina_livre_de_malware_confirmada"])
        self.assertFalse(out["verificacao_antivirus_iniciada"])

    @patch("security.guardian.subprocess.run")
    @patch("security.guardian.Path.is_file", return_value=True)
    @patch("security.guardian.platform.system", return_value="Windows")
    def test_consulta_real_mockada_e_historico_nao_significa_ameaca_ativa(self, system, exists, run):
        run.side_effect = [
            _result({
                "AMServiceEnabled": True, "AntivirusEnabled": True,
                "RealTimeProtectionEnabled": True, "AMRunningMode": "Normal",
            }),
            _result([{"ThreatID": 42, "ThreatStatusID": 3, "ActionSuccess": True,
                      "Resources": ["C:\\Users\\private\\arquivo.txt"]}]),
        ]
        out = self.guardian.observe()
        self.assertEqual(out["status"], "consultado")
        self.assertTrue(out["protecao"]["tempo_real_ativo"])
        self.assertEqual(out["total_eventos_retornados"], 1)
        self.assertNotIn("Resources", out["deteccoes_historicas"][0])
        self.assertIsNone(out["ameacas_ativas_confirmadas"])
        self.assertFalse(out["maquina_livre_de_malware_confirmada"])
        self.assertFalse(out["verificacao_antivirus_iniciada"])

    @patch("security.guardian.subprocess.run")
    @patch("security.guardian.Path.is_file", return_value=True)
    @patch("security.guardian.platform.system", return_value="Windows")
    def test_nao_recebe_segredos_e_nao_executa_comando_mutante(self, system, exists, run):
        run.side_effect = [_result({"AntivirusEnabled": False}), _result([])]
        with patch.dict(os.environ, {"JARVIS_TOKEN": "segredo_sensivel"}):
            out = self.guardian.observe()
        self.assertEqual(out["status"], "consultado")
        self.assertFalse(out["protecao"]["antivirus_ativo"])
        self.assertEqual(out["deteccoes_historicas"], [])
        self.assertFalse(out["maquina_livre_de_malware_confirmada"])
        for call in run.call_args_list:
            args, kwargs = call.args, call.kwargs
            self.assertIn("-NoProfile", args[0])
            self.assertIn("-NonInteractive", args[0])
            self.assertNotIn("JARVIS_TOKEN", kwargs["env"])
            script = args[0][-1]
            self.assertIn("Get-Mp", script)
            self.assertNotIn("Remove-Mp", script)
            self.assertNotIn("Set-Mp", script)
            self.assertNotIn("Start-MpScan", script)
            self.assertNotIn("Invoke-Expression", script)

    @patch("security.guardian.subprocess.run")
    @patch("security.guardian.Path.is_file", return_value=True)
    @patch("security.guardian.platform.system", return_value="Windows")
    def test_erro_historico_retorna_parcial_e_nao_limpo(self, system, exists, run):
        run.side_effect = [_result({"AntivirusEnabled": True}), _result([], code=1)]
        out = self.guardian.observe()
        self.assertEqual(out["status"], "parcial")
        self.assertIsNone(out["deteccoes_historicas"])
        self.assertEqual(out["consultas"]["historico"]["status"], "indisponivel")

    @patch("security.guardian.subprocess.run")
    @patch("security.guardian.Path.is_file", return_value=True)
    @patch("security.guardian.platform.system", return_value="Windows")
    def test_saida_corrompida_falha_fechado(self, system, exists, run):
        run.side_effect = [
            SimpleNamespace(returncode=0, stdout=b"{invalid", stderr=b""),
            _result({"wrong_shape": True}),
        ]
        out = self.guardian.observe()
        self.assertEqual(out["status"], "indisponivel")
        self.assertIsNone(out["protecao"])
        self.assertIsNone(out["deteccoes_historicas"])
        self.assertFalse(out["maquina_livre_de_malware_confirmada"])

    @patch("security.guardian.subprocess.run")
    @patch("security.guardian.Path.is_file", return_value=True)
    @patch("security.guardian.platform.system", return_value="Windows")
    def test_timeout_nao_declara_zero_ameacas(self, system, exists, run):
        import subprocess
        run.side_effect = subprocess.TimeoutExpired("powershell", 12)
        out = self.guardian.observe()
        self.assertEqual(out["status"], "indisponivel")
        self.assertEqual(out["consultas"]["estado"]["status"], "timeout")
        self.assertIsNone(out["total_eventos_retornados"])


class GuardianAPITests(unittest.TestCase):
    def setUp(self):
        self.runtime = InternalAgentRuntime()
        self.runtime.bootstrap()
        self.app = create_app(
            runtime=self.runtime, api_token="guardian-test-token",
            trusted_device_id="guardian-test-device",
        )
        self.client = TestClient(self.app)

    def _headers(self):
        return {
            "X-Jarvis-Token": "guardian-test-token",
            "X-Jarvis-Device-Id": "guardian-test-device",
            "X-Jarvis-Nonce": str(uuid.uuid4()),
            "X-Jarvis-Timestamp": str(int(time.time())),
        }

    def test_guardian_usa_gate_de_dispositivo(self):
        res = self.client.get("/api/seguranca/guardian/estado")
        self.assertNotEqual(res.status_code, 200)

    def test_guardian_report_em_endpoint_autorizado(self):
        expected = {
            "status": "indisponivel",
            "leitura_apenas": True,
            "maquina_livre_de_malware_confirmada": False,
        }
        with patch.object(self.runtime.guardian, "observe", return_value=expected):
            res = self.client.get("/api/seguranca/guardian/estado", headers=self._headers())
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["guardian"], expected)

    def test_hunter_api_nao_alega_campanha_executada(self):
        res = self.client.post(
            "/api/seguranca/caca-vulnerabilidades/campanha?nome_alvo=Core&caminho_alvo=src",
            headers=self._headers(),
        )
        self.assertEqual(res.status_code, 200)
        report = res.json()["relatorio_campanha"]
        self.assertEqual(report["status"], "nao_executado")
        self.assertEqual(report["total_achados"], 0)
        self.assertNotIn("sucesso", res.json()["mensagem"].lower())


if __name__ == "__main__":
    unittest.main()
