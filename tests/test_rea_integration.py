"""REA: gateway desativado por padrao, analise estatica escopada."""
import json
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import time
import unittest
import uuid

from fastapi.testclient import TestClient
from interface.api.app import create_app
from runtime.internal_agent_runtime import InternalAgentRuntime
from runtime.rea_integration import REAInvestigator
from runtime.mcp_stack import MCPStackConfig, OfficialMCPClientManager

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class REAAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.mcp = Mock()
        self.mcp.call_tool.return_value = {
            "status": "sucesso",
            "truncado": False,
            "resultado": {"structured_content": {"normalized_result": {"file": "observed"}}},
        }
        self.adapter = REAInvestigator(mcp_manager=self.mcp, allowed_root=self.root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_managed_chama_apenas_ferramenta_estatica(self):
        test_file = self.root / "untrusted.dll"
        test_file.write_bytes(b"fake")
        result = self.adapter.inspect_static("untrusted.dll", "managed", approved=True)
        self.assertEqual(result["status"], "resultado_recebido")
        self.assertFalse(result["execucao_do_alvo"])
        self.assertFalse(result["evidencia_validada"])
        self.assertTrue(result["conteudo_de_alvo_nao_confiavel"])
        self.mcp.call_tool.assert_called_once_with(
            "rea-investigation", "inspect_managed_artifact",
            {"path": str(test_file.resolve()), "detail": "summary"}
        )

    def test_javascript_diretorio_e_asar(self):
        (self.root / "app").mkdir()
        result = self.adapter.inspect_static("app", "javascript", approved=True)
        self.assertEqual(result["status"], "resultado_recebido")
        self.assertEqual(self.mcp.call_tool.call_args.args[1], "analyze_javascript_application")
        self.assertEqual(self.mcp.call_tool.call_args.args[2]["input_path"], str(self.root / "app"))

    def test_rejeita_paths_externos_links_e_modos_de_execucao(self):
        (self.root / "file.dll").write_bytes(b"binary")
        (self.root / "sym.dll").symlink_to(self.root / "file.dll")
        for name, typ in [
            ("../outside.dll", "managed"),
            ("sym.dll", "managed"),
            ("file.dll", "execute"),
            ("file.dll", "javascript"),
            ("not_found.dll", "managed"),
            ("", "managed"),
        ]:
            with self.subTest(name=name, typ=typ):
                r = self.adapter.inspect_static(name, typ, approved=True)
                self.assertNotEqual(r["status"], "resultado_recebido")
        self.mcp.call_tool.assert_not_called()

    def test_servidor_nao_habilitado_nao_inventa_evidencia(self):
        (self.root / "file.dll").write_bytes(b"binary")
        self.mcp.call_tool.return_value = {"status": "bloqueado", "motivo": "Servidor desabilitado"}
        r = self.adapter.inspect_static("file.dll", "managed", approved=True)
        self.assertEqual(r["status"], "bloqueado")
        self.assertFalse(r["evidencia_validada"])
        self.assertNotIn("resultado_mcp", r)

    def test_registro_arquivo_exemplo_conservador(self):
        config_path = PROJECT_ROOT / "config" / "mcp_servers.example.json"
        reg = json.loads(config_path.read_text(encoding="utf-8"))["servers"]["rea-investigation"]
        self.assertFalse(reg["enabled"])
        self.assertEqual(reg["command"], "node")
        self.assertNotIn("npx", " ".join(reg["args"]).lower())
        self.assertIn("mcp", reg["args"])
        self.assertEqual(reg["env_allowlist"], [])
        self.assertEqual(reg["allowed_resources"], [])
        self.assertEqual(reg["allowed_prompts"], [])
        self.assertNotIn("capture_process_scenario", reg["allowed_tools"])
        self.assertNotIn("start_frida_session", reg["allowed_tools"])
        self.assertNotIn("open_binary", reg["allowed_tools"])
        self.assertIn("inspect_managed_artifact", reg["allowed_tools"])

    def test_rea_exige_aprovacao_antes_de_invocar_mcp(self):
        (self.root / "safe.dll").write_bytes(b"fake")
        res = self.adapter.inspect_static("safe.dll", "managed")
        self.assertEqual(res["status"], "aguardando_aprovacao")
        self.assertFalse(res["executado"])
        self.mcp.call_tool.assert_not_called()

    def test_node_nao_e_permitido_no_default(self):
        config = MCPStackConfig.from_env({})
        self.assertNotIn("node", config.allowed_stdio_commands)
        self.assertNotIn("node.exe", config.allowed_stdio_commands)


class REAAPITests(unittest.TestCase):
    def setUp(self):
        self.runtime = InternalAgentRuntime()
        self.runtime.bootstrap()
        self.client = TestClient(create_app(
            runtime=self.runtime, api_token="rea-test-token",
            trusted_device_id="rea-test-device"
        ))

    def _headers(self):
        return {
            "X-Jarvis-Token": "rea-test-token",
            "X-Jarvis-Device-Id": "rea-test-device",
            "X-Jarvis-Nonce": str(uuid.uuid4()),
            "X-Jarvis-Timestamp": str(int(time.time())),
        }

    def test_rea_requer_dispositivo_confiavel(self):
        r = self.client.post("/api/rea/inspecionar", json={"caminho": "x.dll", "tipo": "managed"})
        self.assertNotEqual(r.status_code, 200)

    def test_rea_no_pc_sem_instalacao_nao_alega_resultado(self):
        r = self.client.post("/api/rea/inspecionar", json={
            "caminho": "inexistente.dll", "tipo": "managed", "aprovado": True
        }, headers=self._headers())
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "bloqueado")


if __name__ == "__main__":
    unittest.main()
