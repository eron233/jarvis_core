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
            max_memory_mb=64,
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

    def test_microsandbox_successful_execution(self):
        code = "a = 10; b = 20; c = a + b"
        result = self.sandbox.execute_in_microsandbox(
            code_str=code,
            tool_name="teste_soma",
        )
        self.assertTrue(result["sucesso"])
        self.assertEqual(result["status"], "sucesso")
        self.assertLess(result["pegada_memoria_mb"], 5.0)

    def test_microsandbox_ast_security_blocking(self):
        code = "global x; x = 100"
        result = self.sandbox.execute_in_microsandbox(
            code_str=code,
            tool_name="teste_global",
        )
        self.assertFalse(result["sucesso"])
        self.assertEqual(result["status"], "bloqueado_por_seguranca")

    def test_api_microsandbox_endpoint(self):
        code = "x = [i for i in range(100)]"
        response = self.client.post(
            "/api/seguranca/micro-sandbox/executar?nome_ferramenta=teste_api",
            content=code,
            headers=self._get_headers(),
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("resultado_sandbox", data)
        self.assertTrue(data["resultado_sandbox"]["sucesso"])


if __name__ == "__main__":
    unittest.main()
