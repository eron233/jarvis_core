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
        client = TestClient(create_app(api_token="token-teste"))

        response = client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/painel")

    def test_painel_mobile_first_e_servido_pela_api(self) -> None:
        client = TestClient(create_app(api_token="token-teste"))

        response = client.get("/painel")

        self.assertEqual(response.status_code, 200)
        self.assertIn("<title>Painel JARVIS</title>", response.text)
        self.assertIn('name="viewport"', response.text)
        self.assertIn("Comando textual", response.text)
        self.assertIn("Atualizar resumo", response.text)


if __name__ == "__main__":
    unittest.main()
