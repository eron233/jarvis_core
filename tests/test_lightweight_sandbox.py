import os
import unittest
import tempfile
import shutil
import time
import uuid
from pathlib import Path
from fastapi.testclient import TestClient

from interface.api.app import create_app
from runtime.internal_agent_runtime import InternalAgentRuntime
from security.lightweight_sandbox_engine import UltraLightweightSandboxEngine


class TestUltraLightweightSandbox(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sandbox = UltraLightweightSandboxEngine(
            max_memory_mb=256,
            max_cpu_time_seconds=3,
            data_dir=Path(self.temp_dir) / "sandbox_runs",
        )
        self.runtime = InternalAgentRuntime()
        self.runtime.bootstrap()
        self.runtime.lightweight_sandbox_engine = self.sandbox

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

    def test_execucao_bem_sucedida_retorna_resultado(self):
        code = "_out['soma'] = 10 + 20\n_out['lista'] = [i for i in range(5)]"
        result = self.sandbox.execute_in_microsandbox(code_str=code, tool_name="teste_soma")
        self.assertTrue(result["sucesso"])
        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["resultado"]["soma"], 30)
        self.assertEqual(result["resultado"]["lista"], [0, 1, 2, 3, 4])

    def test_memoria_reportada_e_medida_de_verdade(self):
        # Não é mais um valor fixo; deve ser um número >= 0 medido no processo filho.
        result = self.sandbox.execute_in_microsandbox(code_str="_out['x'] = 1", tool_name="mem")
        self.assertIn("pegada_memoria_mb", result)
        self.assertIsInstance(result["pegada_memoria_mb"], float)
        if os.name == "posix":
            self.assertGreater(result["pegada_memoria_mb"], 0.0)

    def test_bloqueia_global(self):
        result = self.sandbox.execute_in_microsandbox(code_str="global x\nx = 100", tool_name="g")
        self.assertFalse(result["sucesso"])
        self.assertEqual(result["status"], "bloqueado_por_seguranca")

    def test_bloqueia_import_de_os(self):
        # A falha crítica original: 'import os; os.system(...)' passava pelo validador.
        result = self.sandbox.execute_in_microsandbox(
            code_str="import os\n_out['r'] = os.getcwd()", tool_name="os_escape"
        )
        self.assertFalse(result["sucesso"])
        self.assertEqual(result["status"], "bloqueado_por_seguranca")
        self.assertIn("os", result["motivo"])

    def test_bloqueia_subprocess_e_socket(self):
        for mod in ("subprocess", "socket", "shutil", "ctypes"):
            result = self.sandbox.execute_in_microsandbox(
                code_str=f"import {mod}", tool_name=f"imp_{mod}"
            )
            self.assertFalse(result["sucesso"], f"{mod} deveria ser bloqueado")
            self.assertEqual(result["status"], "bloqueado_por_seguranca")

    def test_bloqueia_from_import_perigoso(self):
        result = self.sandbox.execute_in_microsandbox(
            code_str="from os import system", tool_name="from_os"
        )
        self.assertFalse(result["sucesso"])
        self.assertEqual(result["status"], "bloqueado_por_seguranca")

    def test_bloqueia_open_eval_exec(self):
        for snippet in ("open('/etc/passwd')", "eval('1+1')", "exec('x=1')", "__import__('os')"):
            result = self.sandbox.execute_in_microsandbox(code_str=snippet, tool_name="prim")
            self.assertFalse(result["sucesso"], f"{snippet} deveria ser bloqueado")
            self.assertEqual(result["status"], "bloqueado_por_seguranca")

    def test_bloqueia_fuga_por_dunder(self):
        # Rota clássica: ().__class__.__bases__[0].__subclasses__()
        code = "_out['c'] = ().__class__.__bases__[0].__subclasses__()"
        result = self.sandbox.execute_in_microsandbox(code_str=code, tool_name="dunder")
        self.assertFalse(result["sucesso"])
        self.assertEqual(result["status"], "bloqueado_por_seguranca")

    def test_import_permitido_da_allowlist_funciona(self):
        code = "import math\n_out['raiz'] = math.sqrt(16)"
        result = self.sandbox.execute_in_microsandbox(code_str=code, tool_name="math_ok")
        self.assertTrue(result["sucesso"])
        self.assertEqual(result["resultado"]["raiz"], 4.0)

    @unittest.skipUnless(os.name == "posix", "limites de recurso exigem POSIX")
    def test_limite_de_cpu_interrompe_loop_infinito(self):
        sandbox = UltraLightweightSandboxEngine(
            max_memory_mb=256,
            max_cpu_time_seconds=1,
            data_dir=Path(self.temp_dir) / "cpu_runs",
        )
        result = sandbox.execute_in_microsandbox(
            code_str="x = 0\nwhile True:\n    x += 1", tool_name="loop"
        )
        self.assertFalse(result["sucesso"])
        self.assertIn(result["status"], {"timeout_excedido", "erro_subprocesso"})

    def test_erro_de_execucao_e_reportado(self):
        result = self.sandbox.execute_in_microsandbox(
            code_str="_out['x'] = 1 / 0", tool_name="div_zero"
        )
        self.assertFalse(result["sucesso"])
        self.assertEqual(result["status"], "erro_execucao")

    def test_api_microsandbox_endpoint(self):
        code = "_out['x'] = [i for i in range(100)]"
        response = self.client.post(
            "/api/seguranca/micro-sandbox/executar?nome_ferramenta=teste_api",
            content=code,
            headers=self._get_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("resultado_sandbox", data)
        self.assertTrue(data["resultado_sandbox"]["sucesso"])

    def test_api_microsandbox_bloqueia_codigo_malicioso(self):
        response = self.client.post(
            "/api/seguranca/micro-sandbox/executar?nome_ferramenta=malicioso",
            content="import os\nos.system('echo vazou')",
            headers=self._get_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data["resultado_sandbox"]["sucesso"])
        self.assertEqual(data["resultado_sandbox"]["status"], "bloqueado_por_seguranca")


if __name__ == "__main__":
    unittest.main()
