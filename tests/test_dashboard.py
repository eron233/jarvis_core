"""Testes unitarios para o painel mobile-first do JARVIS."""

from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import unittest

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from interface.api.app import create_app
from runtime.system_config import JarvisEnvironmentConfig
from runtime.internal_agent_runtime import InternalAgentRuntime
from security.access_control import AccessControl


class JarvisDashboardTests(unittest.TestCase):
    """Valida redirecionamento e protecao do painel web."""

    def build_client(self, name: str, simple_web_login: bool = False) -> TestClient:
        """Cria um cliente isolado do painel com configuracao dedicada."""

        scenario_dir = PROJECT_ROOT / "tests" / "_dashboard_artifacts" / name
        if scenario_dir.exists():
            shutil.rmtree(scenario_dir)

        env = {
            "JARVIS_ENV": "test",
            "JARVIS_TOKEN": "token-teste",
            "JARVIS_TRUSTED_DEVICE_ID": "eron-celular-principal",
            "JARVIS_ADMIN_PASSWORD": "senha-admin-segura-2026",
            "JARVIS_ENABLE_DASHBOARD": "true",
            "JARVIS_SIMPLE_WEB_LOGIN": "true" if simple_web_login else "false",
            "JARVIS_DATA_DIR": str(scenario_dir / "data"),
            "JARVIS_LOGS_DIR": str(scenario_dir / "logs"),
            "JARVIS_REPORTS_DIR": str(scenario_dir / "reports"),
        }
        config = JarvisEnvironmentConfig.from_env(environ=env, project_root=PROJECT_ROOT)
        runtime = InternalAgentRuntime()
        runtime.access_control = AccessControl.from_plaintext("senha-admin-segura-2026")
        return TestClient(create_app(runtime=runtime, deployment_config=config))

    def test_root_redireciona_para_o_painel(self) -> None:
        """Confirma que a raiz do servico redireciona para o painel."""

        client = self.build_client("root_redirect")

        response = client.get("/", follow_redirects=False)

        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/painel")

    def test_painel_exige_validacao_do_dispositivo_confiavel(self) -> None:
        """Verifica que o painel so abre apos a sessao do dispositivo confiavel."""

        client = self.build_client("trusted_dashboard")

        locked_response = client.get("/painel")

        self.assertEqual(locked_response.status_code, 200)
        self.assertIn("Acesso restrito por dispositivo confiavel", locked_response.text)
        self.assertNotIn("Converse com o Jarvis", locked_response.text)

        session_response = client.post(
            "/api/auth/device-session",
            headers={
                "X-Jarvis-Token": "token-teste",
                "X-Jarvis-Device-Id": "eron-celular-principal",
                "X-Jarvis-Nonce": "dashboard-session",
                "X-Jarvis-Timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
        self.assertEqual(session_response.status_code, 200)
        self.assertIn("jarvis_trusted_device", session_response.headers.get("set-cookie", ""))

        unlocked_response = client.get("/painel")
        self.assertEqual(unlocked_response.status_code, 200)
        self.assertIn("<title>Painel JARVIS</title>", unlocked_response.text)
        self.assertIn("Converse com o Jarvis", unlocked_response.text)
        self.assertIn("Abrir visão do sistema", unlocked_response.text)
        self.assertIn("Cérebro cognitivo evolutivo", unlocked_response.text)
        self.assertIn("Central de voz", unlocked_response.text)
        self.assertIn("Ativar voz", unlocked_response.text)

    def test_assets_do_brain_avatar_sao_servidos_pela_api(self) -> None:
        """Confirma que os modulos JS do brain avatar ficam acessiveis pelo mesmo servidor."""

        client = self.build_client("brain_avatar_assets")

        response = client.get("/brain-avatar/evolution_map.js")

        self.assertEqual(response.status_code, 200)
        self.assertIn("createEvolutionMap", response.text)

    def test_painel_permite_recuperacao_por_senha_admin_quando_flag_simples_esta_ativa(self) -> None:
        """Valida o fluxo emergencial de acesso web sem depender de device id."""

        client = self.build_client("simple_web_dashboard", simple_web_login=True)

        locked_response = client.get("/painel")

        self.assertEqual(locked_response.status_code, 200)
        self.assertIn('"simple_web_login": true', locked_response.text)
        self.assertIn("adminPasswordInput", locked_response.text)
        self.assertNotIn("Converse com o Jarvis", locked_response.text)

        denied_response = client.post(
            "/api/auth/device-session",
            headers={
                "X-Jarvis-Nonce": "simple-dashboard-invalid",
                "X-Jarvis-Timestamp": datetime.now(timezone.utc).isoformat(),
            },
            json={"admin_password": "senha-errada"},
        )
        self.assertEqual(denied_response.status_code, 401)
        self.assertEqual(denied_response.json()["detail"], "Senha administrativa invalida.")

        session_response = client.post(
            "/api/auth/device-session",
            headers={
                "X-Jarvis-Nonce": "simple-dashboard-valid",
                "X-Jarvis-Timestamp": datetime.now(timezone.utc).isoformat(),
            },
            json={"admin_password": "senha-admin-segura-2026"},
        )
        self.assertEqual(session_response.status_code, 200)
        self.assertEqual(session_response.json()["modo"], "simple_web_login")
        self.assertIn("jarvis_trusted_device", session_response.headers.get("set-cookie", ""))

        unlocked_response = client.get("/painel")
        self.assertEqual(unlocked_response.status_code, 200)
        self.assertIn("<title>Painel JARVIS</title>", unlocked_response.text)
        self.assertIn('"simple_web_login": true', unlocked_response.text)
        self.assertIn("Sessão web simples ativa", unlocked_response.text)
        self.assertIn("Central de voz", unlocked_response.text)


if __name__ == "__main__":
    unittest.main()
