"""Testes da comparacao de segredos e da guarda do fluxo privado do dono."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from interface.api.app import _secrets_match


class SecretComparisonTests(unittest.TestCase):
    """Valida a comparacao de segredos em tempo constante."""

    def test_aceita_somente_valores_identicos(self) -> None:
        """Confirma o resultado correto para valores iguais e diferentes."""

        self.assertTrue(_secrets_match("token-teste", "token-teste"))
        self.assertFalse(_secrets_match("token-test", "token-teste"))
        self.assertFalse(_secrets_match("outro-token-qualquer", "token-teste"))

    def test_trata_ausencia_de_valor_como_negacao(self) -> None:
        """Garante que a ausencia de segredo nunca seja tratada como acerto."""

        self.assertFalse(_secrets_match(None, "token-teste"))
        self.assertFalse(_secrets_match("token-teste", None))
        self.assertFalse(_secrets_match(None, None))

    def test_compara_sem_vazar_prefixo_acertado(self) -> None:
        """
        Um prefixo correto nao pode valer mais que um prefixo errado.

        A comparacao `==` de str encerra no primeiro byte diferente, o que
        transforma o tempo de resposta em um oraculo de prefixo sobre o token.
        """

        self.assertFalse(_secrets_match("token-tesX", "token-teste"))
        self.assertFalse(_secrets_match("Xoken-teste", "token-teste"))


class OwnerThoughtStreamGuardTests(unittest.TestCase):
    """Valida que o fluxo privado do dono usa a mesma guarda das demais rotas."""

    ROUTE = "/api/dono/pensamentos-privados"

    def build_client(self, name: str):
        """
        Reaproveita o montador de cliente da suite oficial da API.

        O import fica aqui dentro de proposito: no escopo do modulo o pytest
        coletaria a classe importada e reexecutaria toda a suite de API.
        """

        from tests.test_api import JarvisApiTests

        return JarvisApiTests.build_client(self, name)

    def test_exige_autenticacao_como_qualquer_rota_protegida(self) -> None:
        """A rota antes respondia 200 sem credencial; agora recusa o acesso."""

        client, _headers = self.build_client("owner_stream_sem_token")

        response = client.get(self.ROUTE)

        self.assertEqual(response.status_code, 401)

    def test_recusa_token_invalido(self) -> None:
        """Um token errado nao pode alcancar o motor de pensamentos."""

        client, _headers = self.build_client("owner_stream_token_errado")

        response = client.get(
            self.ROUTE,
            headers={"X-Jarvis-Token": "token-errado", "X-Jarvis-Device-Id": "eron-celular-principal"},
        )

        self.assertEqual(response.status_code, 401)

    def test_libera_o_dispositivo_principal_do_dono(self) -> None:
        """O dono autenticado continua recebendo o fluxo de pensamentos."""

        client, headers = self.build_client("owner_stream_dono")

        response = client.get(self.ROUTE, headers=headers)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "sucesso")

    def test_nega_dispositivo_confiavel_que_nao_e_o_principal(self) -> None:
        """
        A guarda compartilhada aceita qualquer dispositivo confiavel, mas os
        pensamentos privados permanecem restritos ao dispositivo principal.
        """

        client, headers = self.build_client("owner_stream_outro_dispositivo")
        runtime = client.app.state.runtime
        runtime.device_registry.ensure_device(
            device_id="tablet-secundario",
            nome="tablet-secundario",
            tipo="client",
            trusted=True,
            primary=False,
        )

        outro = dict(headers)
        outro["X-Jarvis-Device-Id"] = "tablet-secundario"
        response = client.get(self.ROUTE, headers=outro)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "negado")

    def test_registra_a_tentativa_negada_na_auditoria(self) -> None:
        """
        A validacao propria da rota nao passava pela auditoria, entao tentativas
        de ler os pensamentos do dono nao deixavam rastro.
        """

        client, _headers = self.build_client("owner_stream_auditoria")
        runtime = client.app.state.runtime

        client.get(self.ROUTE, headers={"X-Jarvis-Token": "token-errado", "X-Jarvis-Device-Id": "qualquer"})

        entradas = runtime.audit_logger.snapshot()["entries"]
        motivos = [
            valor
            for entrada in entradas
            for valor in [entrada.get("payload", {}).get("reason"), entrada.get("payload", {}).get("motivo")]
        ]
        self.assertIn("invalid_token", motivos)


if __name__ == "__main__":
    unittest.main()
