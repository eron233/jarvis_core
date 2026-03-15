"""Testes do controle de acesso inicial por voz, senha e modo guest."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from security.access_control import AccessControl


class AccessControlTests(unittest.TestCase):
    """Valida a politica inicial de acesso do Jarvis."""

    def test_special_phrase_returns_reserved_response_for_admin_voice(self) -> None:
        """Confirma a resposta reservada sem tratar voz textual como admin real."""

        access = AccessControl().evaluate(phrase="Jarvis ta ai", voice_id="eron")

        self.assertFalse(access["admin_access"])
        self.assertEqual(access["special_response"], "Sim, Sr. Maciel.")
        self.assertTrue(access["recognized_voice_matches_admin"])
        self.assertTrue(access["voice_is_informative_only"])

    def test_special_phrase_is_ignored_without_admin_voice(self) -> None:
        """Garante que a frase reservada seja ignorada sem a voz reconhecida."""

        access = AccessControl().evaluate(phrase="Jarvis ta ai", voice_id="visitante")

        self.assertEqual(access["access_level"], "guest")
        self.assertTrue(access["should_ignore"])

    def test_password_grants_admin_access(self) -> None:
        """Verifica que a senha administrativa concede acesso elevado."""

        access = AccessControl().evaluate(phrase="executar ciclo", password="alter ego")

        self.assertTrue(access["admin_access"])
        self.assertIn("senha", access["authenticated_by"])


if __name__ == "__main__":
    unittest.main()
