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
            max_memory_mb=128,
            max_cpu_time_seconds=3,
            data_dir=Path(self.temp_dir) / "sandbox_runs",
            enabled=True,
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

    def test_microsandbox_successful_execution(self):
        result = self.sandbox.execute_in_microsandbox(
            code_str="import math\na = 10; b = 20\nprint(a + b, math.floor(2.7))",
            tool_name="teste_soma",
        )
        self.assertTrue(result["sucesso"], result)
        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["resultado"]["saida"].strip(), "30 2")
        self.assertNotIn("pegada_memoria_mb", result)

    def test_sandbox_vem_desligado_por_padrao(self):
        previous = os.environ.pop("JARVIS_ENABLE_CODE_SANDBOX", None)
        try:
            default_engine = UltraLightweightSandboxEngine(data_dir=Path(self.temp_dir) / "default")
            result = default_engine.execute_in_microsandbox("print(1)")
        finally:
            if previous is not None:
                os.environ["JARVIS_ENABLE_CODE_SANDBOX"] = previous
        self.assertEqual(result["status"], "desativado")
        self.assertFalse(result["sucesso"])

    def test_microsandbox_ast_security_blocking(self):
        blocked_snippets = [
            "global x; x = 100",
            "import os\nos.system('id')",
            "import subprocess",
            "from os import path",
            "__import__('os')",
            "open('/etc/passwd').read()",
            "().__class__.__base__.__subclasses__()",
            "getattr(1, 'real')",
            "eval('1+1')",
        ]
        for code in blocked_snippets:
            with self.subTest(code=code):
                result = self.sandbox.execute_in_microsandbox(code_str=code, tool_name="teste_bloqueio")
                self.assertFalse(result["sucesso"])
                self.assertEqual(result["status"], "bloqueado_por_seguranca")

    def test_microsandbox_nao_vaza_ambiente_do_servidor(self):
        os.environ["JARVIS_TOKEN_TESTE_VAZAMENTO"] = "segredo"
        try:
            result = self.sandbox.execute_in_microsandbox("print('ok')")
        finally:
            os.environ.pop("JARVIS_TOKEN_TESTE_VAZAMENTO", None)
        self.assertTrue(result["sucesso"], result)

    def test_microsandbox_timeout(self):
        result = self.sandbox.execute_in_microsandbox("while True:\n    pass", tool_name="loop")
        self.assertFalse(result["sucesso"])
        self.assertIn(result["status"], {"timeout_excedido", "erro_subprocesso"})

    def test_nome_da_ferramenta_nao_escapa_do_diretorio(self):
        self.sandbox.execute_in_microsandbox("x = 1", tool_name="../../fora")
        runs = list((Path(self.temp_dir) / "sandbox_runs").iterdir())
        self.assertTrue(runs)
        for run in runs:
            self.assertNotIn("..", run.name)

    def test_api_microsandbox_endpoint(self):
        response = self.client.post(
            "/api/seguranca/micro-sandbox/executar?nome_ferramenta=teste_api",
            content="x = [i for i in range(100)]\nprint(len(x))",
            headers=self._get_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["resultado_sandbox"]["sucesso"], data)
        self.assertEqual(data["resultado_sandbox"]["resultado"]["saida"].strip(), "100")


if __name__ == "__main__":
    unittest.main()
