"""Testes unitarios para o painel mobile-first do JARVIS."""

from pathlib import Path
import sys
import unittest

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from interface.api.app import create_app


class JarvisDashboardTests(unittest.TestCase):
    def test_root_redireciona_para_o_painel(self) -> None:
        client = TestClient(
            create_app(
                api_token="token-teste",
                trusted_device_id="eron-celular-principal",
            )
        )

        response = client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/painel")

    def test_painel_exige_validacao_do_dispositivo_confiavel(self) -> None:
        client = TestClient(
            create_app(
                api_token="token-teste",
                trusted_device_id="eron-celular-principal",
            )
        )

        locked_response = client.get("/painel")

        self.assertEqual(locked_response.status_code, 200)
        self.assertIn("Acesso restrito por dispositivo confiável", locked_response.text)
        self.assertNotIn("Comando textual", locked_response.text)

        session_response = client.post(
            "/api/auth/device-session",
            headers={
                "X-Jarvis-Token": "token-teste",
                "X-Jarvis-Device-Id": "eron-celular-principal",
            },
        )
        self.assertEqual(session_response.status_code, 200)
        self.assertIn("jarvis_trusted_device", session_response.headers.get("set-cookie", ""))

        unlocked_response = client.get("/painel")
        self.assertEqual(unlocked_response.status_code, 200)
        self.assertIn("<title>Painel JARVIS</title>", unlocked_response.text)
        self.assertIn("Comando textual", unlocked_response.text)


if __name__ == "__main__":
    unittest.main()
