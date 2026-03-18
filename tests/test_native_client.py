"""Testes do cliente nativo leve do JARVIS."""

from io import BytesIO
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from interface.native_client.jarvis_client import build_authenticated_headers, send_command


class _FakeHttpResponse:
    """Resposta HTTP minima para simular a API do cliente nativo."""

    def __init__(self, payload: bytes) -> None:
        """Inicializa a instancia e prepara o estado interno do componente."""
        self._payload = BytesIO(payload)

    def read(self) -> bytes:
        """Retorna o conteudo mantido por este helper de teste."""
        return self._payload.read()

    def __enter__(self) -> "_FakeHttpResponse":
        """Entra no contexto e retorna a propria instancia."""
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        """Encerra o contexto sem alterar a propagacao de excecoes."""
        return None


class NativeClientTests(unittest.TestCase):
    """Valida o contrato real do cliente nativo com a API endurecida."""

    def test_build_authenticated_headers_includes_nonce_and_timestamp(self) -> None:
        """Confirma que os headers anti-replay sao gerados automaticamente."""

        headers = build_authenticated_headers(
            token="token-teste",
            device_id="device-teste",
            nonce="nonce-fixo",
            timestamp="2026-03-15T12:00:00+00:00",
        )

        self.assertEqual(headers["X-Jarvis-Token"], "token-teste")
        self.assertEqual(headers["X-Jarvis-Device-Id"], "device-teste")
        self.assertEqual(headers["X-Jarvis-Nonce"], "nonce-fixo")
        self.assertEqual(headers["X-Jarvis-Timestamp"], "2026-03-15T12:00:00+00:00")

    @patch("interface.native_client.jarvis_client.request.urlopen")
    def test_send_command_envia_headers_compatíveis_com_api_atual(self, mock_urlopen) -> None:
        """Garante que o cliente leve envie token, device id, nonce e timestamp."""

        mock_urlopen.return_value = _FakeHttpResponse(b'{"resposta":"ok"}')

        payload = send_command(
            url="http://localhost:8000/api/comando",
            token="token-teste",
            device_id="device-teste",
            texto="status",
        )

        self.assertEqual(payload["resposta"], "ok")
        request_obj = mock_urlopen.call_args.args[0]
        headers = {key.lower(): value for key, value in request_obj.header_items()}
        self.assertEqual(headers["x-jarvis-token"], "token-teste")
        self.assertEqual(headers["x-jarvis-device-id"], "device-teste")
        self.assertIn("x-jarvis-nonce", headers)
        self.assertIn("x-jarvis-timestamp", headers)


if __name__ == "__main__":
    unittest.main()
