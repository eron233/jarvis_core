"""Testes de regressao das protecoes de seguranca da API do JARVIS."""

from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
import uuid
import zipfile

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from interface.api.app import create_app
from interface.api.web_session import AuthAttemptLimiter, WebSessionManager
from runtime.internal_agent_runtime import InternalAgentRuntime

TOKEN = "token-seguranca-teste"
DEVICE = "device-seguranca-teste"


class ApiSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())
        self.files_dir = self.temp_dir / "arquivos"
        self._previous_files_dir = os.environ.get("JARVIS_FILES_DIR")
        os.environ["JARVIS_FILES_DIR"] = str(self.files_dir)
        runtime = InternalAgentRuntime()
        runtime.bootstrap()
        self.app = create_app(runtime=runtime, api_token=TOKEN, trusted_device_id=DEVICE)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        if self._previous_files_dir is None:
            os.environ.pop("JARVIS_FILES_DIR", None)
        else:
            os.environ["JARVIS_FILES_DIR"] = self._previous_files_dir
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def auth_headers(self, mutating: bool = False) -> dict[str, str]:
        headers = {"X-Jarvis-Token": TOKEN, "X-Jarvis-Device-Id": DEVICE}
        if mutating:
            headers["X-Jarvis-Nonce"] = str(uuid.uuid4())
            headers["X-Jarvis-Timestamp"] = datetime.now(timezone.utc).isoformat()
        return headers

    def login(self) -> None:
        response = self.client.post("/api/auth/device-session", headers=self.auth_headers(mutating=True))
        self.assertEqual(response.status_code, 200)

    # --- sessao do painel -------------------------------------------------

    def test_sessao_do_painel_autentica_api_sem_token_no_navegador(self) -> None:
        self.assertEqual(self.client.get("/api/status").status_code, 401)
        self.login()
        self.assertEqual(self.client.get("/api/status").status_code, 200)

    def test_cookie_de_sessao_e_strict_httponly_e_expira(self) -> None:
        response = self.client.post("/api/auth/device-session", headers=self.auth_headers(mutating=True))
        cookie = response.headers["set-cookie"].lower()
        self.assertIn("httponly", cookie)
        self.assertIn("samesite=strict", cookie)
        self.assertIn("max-age=", cookie)

    def test_logout_revoga_sessao_mesmo_com_cookie_copiado(self) -> None:
        self.login()
        stolen_cookie = self.client.cookies.get("jarvis_trusted_device")
        self.client.delete("/api/auth/device-session")
        attacker = TestClient(self.app)
        attacker.cookies.set("jarvis_trusted_device", stolen_cookie)
        self.assertEqual(attacker.get("/api/status").status_code, 401)

    def test_cookie_forjado_nao_autentica(self) -> None:
        forged = TestClient(self.app)
        forged.cookies.set("jarvis_trusted_device", "v2.abc.ZGV2.9999999999.deadbeef")
        self.assertEqual(forged.get("/api/status").status_code, 401)

    def test_mutacao_via_cookie_exige_header_csrf(self) -> None:
        self.login()
        payload = {"task_id": "csrf-1", "goal": "x"}
        blocked = self.client.post("/api/tarefas", json=payload)
        self.assertEqual(blocked.status_code, 403)
        cross_site = self.client.post(
            "/api/tarefas", json=payload, headers={"X-Jarvis-Csrf": "1", "Origin": "https://evil.example"}
        )
        self.assertEqual(cross_site.status_code, 403)
        allowed = self.client.post("/api/tarefas", json=payload, headers={"X-Jarvis-Csrf": "1"})
        self.assertEqual(allowed.status_code, 200)

    def test_forca_bruta_de_token_e_bloqueada(self) -> None:
        for _ in range(10):
            response = self.client.get("/api/status", headers={"X-Jarvis-Token": "errado", "X-Jarvis-Device-Id": DEVICE})
            self.assertEqual(response.status_code, 401)
        blocked = self.client.get("/api/status", headers=self.auth_headers())
        self.assertEqual(blocked.status_code, 429)

    # --- endpoints antes expostos -------------------------------------------

    def test_pensamentos_privados_exigem_autenticacao(self) -> None:
        self.assertEqual(self.client.get("/api/dono/pensamentos-privados").status_code, 401)
        response = self.client.get("/api/dono/pensamentos-privados", headers=self.auth_headers())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "sucesso")

    def test_websocket_recusa_conexao_anonima(self) -> None:
        with self.assertRaises(WebSocketDisconnect) as ctx:
            with self.client.websocket_connect("/ws/live-stream") as ws:
                ws.receive_text()
        self.assertEqual(ctx.exception.code, 1008)

    def test_websocket_aceita_sessao_e_nao_retransmite_mensagens(self) -> None:
        self.login()
        with self.client.websocket_connect("/ws/live-stream") as ws:
            ws.send_text("ping")
            self.assertEqual(ws.receive_text(), "pong")

    def test_health_publico_nao_expoe_caminhos_nem_identidade(self) -> None:
        payload = self.client.get("/health").json()
        flattened = str(payload)
        self.assertNotIn("paths_persistentes", flattened)
        self.assertNotIn("access_bootstrap", flattened)
        self.assertNotIn("identidade_runtime", payload)
        self.assertIn("status", payload)

    def test_headers_de_seguranca(self) -> None:
        response = self.client.get("/painel")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", response.headers["content-security-policy"])

    # --- arquivos ------------------------------------------------------------

    def test_endpoints_de_arquivo_nao_saem_do_diretorio_permitido(self) -> None:
        for path, params in (
            ("/api/ingestao/universal", {"caminho_arquivo": "/etc/passwd"}),
            ("/api/ingestao/universal", {"caminho_arquivo": "../../etc/passwd"}),
            ("/api/arquivos/compactar", {"caminho": "/etc"}),
            ("/api/arquivos/descompactar", {"caminho": "/tmp/x.zip"}),
            ("/api/visao/analisar-imagem", {"caminho_imagem": "../segredo.png"}),
        ):
            with self.subTest(path=path, params=params):
                response = self.client.post(path, params=params, headers=self.auth_headers(mutating=True))
                self.assertEqual(response.status_code, 403)

    def test_descompactar_recusa_zip_slip(self) -> None:
        self.files_dir.mkdir(parents=True, exist_ok=True)
        malicious = self.files_dir / "malicioso.zip"
        with zipfile.ZipFile(malicious, "w") as archive:
            archive.writestr("../../fora.txt", "pwned")
        response = self.client.post(
            "/api/arquivos/descompactar",
            params={"caminho": "malicioso.zip"},
            headers=self.auth_headers(mutating=True),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "erro")
        self.assertFalse((self.files_dir.parent / "fora.txt").exists())
        self.assertFalse((self.temp_dir.parent / "fora.txt").exists())


class WebSessionUnitTests(unittest.TestCase):
    def test_sessao_expira(self) -> None:
        manager = WebSessionManager(ttl_seconds=60)
        cookie = manager.issue("segredo", "dev", now=1000)
        self.assertIsNotNone(manager.verify("segredo", cookie, now=1059))
        self.assertIsNone(manager.verify("segredo", cookie, now=1061))

    def test_troca_de_segredo_invalida_sessoes(self) -> None:
        manager = WebSessionManager()
        cookie = manager.issue("token-antigo", "dev")
        self.assertIsNone(manager.verify("token-novo", cookie))

    def test_device_id_com_pontos_sobrevive_ao_cookie(self) -> None:
        manager = WebSessionManager()
        cookie = manager.issue("s", "celular.principal.v2")
        self.assertEqual(manager.verify("s", cookie).device_id, "celular.principal.v2")

    def test_limitador_libera_apos_janela(self) -> None:
        limiter = AuthAttemptLimiter(max_failures=2, window_seconds=10)
        limiter.register_failure("ip", now=0)
        limiter.register_failure("ip", now=1)
        self.assertTrue(limiter.is_blocked("ip", now=2))
        self.assertFalse(limiter.is_blocked("ip", now=12))


if __name__ == "__main__":
    unittest.main()
