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
        # A asserção anterior era `< 5.0` e passava contra uma constante de 3.8
        # embutida no motor: nada media memoria. O valor agora vem do pico real
        # medido pelo processo filho, entao o que se verifica e que houve
        # medicao e que ela ficou dentro do limite configurado.
        self.assertTrue(result["memoria_medida"])
        self.assertIsNotNone(result["pegada_memoria_mb"])
        self.assertGreater(result["pegada_memoria_mb"], 0)
        # O pico nao e comparado com o limite: `ru_maxrss` cobre toda a vida do
        # processo, inclusive a inicializacao do interpretador, que acontece
        # antes de o limite ser imposto. Quem verifica a imposicao do limite e
        # `test_aplica_limite_real_de_memoria`.
        self.assertEqual(result["limite_memoria_mb"], 64)

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


    def test_bloqueia_importacao_de_modulos_do_sistema(self) -> None:
        """
        O portao AST recusava apenas `global` e `nonlocal`, que nao tem relacao
        com seguranca, enquanto `import os` e `import subprocess` passavam.
        """

        for codigo in (
            "import os\nos.system('id')",
            "import subprocess\nsubprocess.run(['id'])",
            "from socket import socket",
            "import shutil",
        ):
            with self.subTest(codigo=codigo.splitlines()[0]):
                resultado = self.sandbox.execute_in_microsandbox(codigo, "import_proibido")
                self.assertEqual(resultado["status"], "bloqueado_por_seguranca")
                self.assertFalse(resultado["sucesso"])

    def test_bloqueia_execucao_dinamica_de_codigo(self) -> None:
        """`eval`, `exec` e `__import__` contornariam a analise estatica."""

        for codigo in ("eval('1+1')", "exec('x=1')", "__import__('os')", "open('/etc/passwd')"):
            with self.subTest(codigo=codigo):
                resultado = self.sandbox.execute_in_microsandbox(codigo, "chamada_proibida")
                self.assertEqual(resultado["status"], "bloqueado_por_seguranca")

    def test_bloqueia_caminho_de_volta_pelos_atributos_internos(self) -> None:
        """`().__class__.__bases__` alcanca os builtins a partir de qualquer objeto."""

        resultado = self.sandbox.execute_in_microsandbox(
            "x = ().__class__.__bases__[0].__subclasses__()",
            "fuga_dunder",
        )
        self.assertEqual(resultado["status"], "bloqueado_por_seguranca")

    def test_aplica_limite_real_de_memoria(self) -> None:
        """
        `max_memory_mb` era guardado e nunca usado: o invólucro so limitava CPU,
        entao uma ferramenta podia alocar toda a RAM disponivel.
        """

        resultado = self.sandbox.execute_in_microsandbox(
            "x = bytearray(300 * 1024 * 1024)",
            "estouro_de_memoria",
        )
        self.assertEqual(resultado["status"], "limite_memoria_excedido")
        self.assertFalse(resultado["sucesso"])

    def test_declara_quais_limites_foram_aplicados(self) -> None:
        """O relatorio precisa dizer o que foi de fato imposto pelo SO."""

        resultado = self.sandbox.execute_in_microsandbox("a = 1", "limites")
        self.assertIn("RLIMIT_AS", resultado["limites_aplicados"])
        self.assertIn("RLIMIT_CPU", resultado["limites_aplicados"])

    def test_codigo_legitimo_continua_executando(self) -> None:
        """As restricoes nao podem impedir uma ferramenta comum de rodar."""

        resultado = self.sandbox.execute_in_microsandbox(
            "total = sum(i * i for i in range(1000))",
            "calculo_legitimo",
        )
        self.assertTrue(resultado["sucesso"])


if __name__ == "__main__":
    unittest.main()


class SandboxInputArgsTests(unittest.TestCase):
    """A ferramenta precisa receber os argumentos que o chamador enviou."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.sandbox = UltraLightweightSandboxEngine(
            max_memory_mb=64,
            max_cpu_time_seconds=3,
            data_dir=Path(self.temp_dir) / "sandbox_runs",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_entrada_chega_a_ferramenta(self) -> None:
        """
        `input_args` era aceito e descartado em silencio: a ferramenta rodava
        sem as entradas enviadas. O assert dentro do codigo so passa se os
        valores tiverem realmente chegado.
        """

        resultado = self.sandbox.execute_in_microsandbox(
            'assert entrada["a"] == 7 and entrada["b"] == "texto"',
            "com_entrada",
            input_args={"a": 7, "b": "texto"},
        )

        self.assertEqual(resultado["status"], "sucesso")

    def test_entrada_ausente_vira_dicionario_vazio(self) -> None:
        """Sem argumentos a ferramenta ainda encontra a variavel definida."""

        resultado = self.sandbox.execute_in_microsandbox("assert entrada == {}", "sem_entrada")

        self.assertEqual(resultado["status"], "sucesso")

    def test_entrada_nao_serializavel_e_recusada(self) -> None:
        """Argumentos que nao viram JSON precisam falhar de forma explicita."""

        resultado = self.sandbox.execute_in_microsandbox(
            "x = 1", "entrada_ruim", input_args={"obj": object()}
        )

        self.assertEqual(resultado["status"], "entrada_invalida")
        self.assertFalse(resultado["sucesso"])

    def test_erro_dentro_da_ferramenta_nao_e_reportado_como_sucesso(self) -> None:
        """
        Uma excecao dentro do sandbox aparecia so no resultado interno, enquanto
        a resposta ao chamador continuava dizendo "sucesso".
        """

        resultado = self.sandbox.execute_in_microsandbox('raise ValueError("falhou")', "erro")

        self.assertEqual(resultado["status"], "erro_execucao")
        self.assertFalse(resultado["sucesso"])
