"""Docker integration checks. Run only in explicitly opted-in CI with local image."""
import os
import unittest

from security.container_executor import ContainerExecutor


@unittest.skipUnless(os.environ.get("JARVIS_TWIN_RUN_DOCKER_SMOKE") == "1",
                     "Docker smoke test desativado fora do runner dedicado")
class DockerIsolationSmokeTests(unittest.TestCase):
    def setUp(self):
        self.executor = ContainerExecutor(
            enabled=True,
            image=os.environ.get("JARVIS_TWIN_DOCKER_IMAGE", ""),
        )

    def run_code(self, body, params=None):
        code = "def run_tool(params):\n" + "\n".join(
            "    " + line for line in body.splitlines()
        ) + "\n"
        return self.executor.execute(code, params or {}, timeout_seconds=8)

    def test_codigo_legitimo_e_argumentos(self):
        result = self.run_code("return {'soma': params['a'] + params['b']}",
                               {"a": 2, "b": 3})
        self.assertEqual(result["status"], "executado_sem_verificacao", result)
        self.assertEqual(result["resultado_declarado"]["soma"], 5)
        self.assertFalse(result["concluido_verificado"])

    def test_sem_rede_externa(self):
        result = self.run_code("""
import socket
try:
    sock = socket.create_connection(("1.1.1.1", 443), timeout=1)
    sock.close()
    return {"bloqueada": False}
except OSError:
    return {"bloqueada": True}
""".strip())
        self.assertEqual(result["status"], "executado_sem_verificacao", result)
        self.assertTrue(result["resultado_declarado"]["bloqueada"])

    def test_root_filesystem_readonly(self):
        result = self.run_code("""
try:
    with open('/jarvis_should_not_write', 'w') as f:
        f.write('teste')
    return {"bloqueado": False}
except OSError:
    return {"bloqueado": True}
""".strip())
        self.assertEqual(result["status"], "executado_sem_verificacao", result)
        self.assertTrue(result["resultado_declarado"]["bloqueado"])

    def test_nao_recebe_segredos_do_host(self):
        os.environ["JARVIS_TEST_SECRET"] = "valor_secreto_que_nao_pode_passar"
        try:
            result = self.run_code(
                "import os\nreturn {'segredo': os.getenv('JARVIS_TEST_SECRET')}")
        finally:
            os.environ.pop("JARVIS_TEST_SECRET", None)
        self.assertEqual(result["status"], "executado_sem_verificacao", result)
        self.assertIsNone(result["resultado_declarado"]["segredo"])

    def test_erro_de_execucao_nao_e_sucesso(self):
        result = self.run_code("raise ValueError('falha proposital')")
        self.assertEqual(result["status"], "erro_ferramenta", result)
        self.assertFalse(result["concluido_verificado"])


if __name__ == "__main__":
    unittest.main()
