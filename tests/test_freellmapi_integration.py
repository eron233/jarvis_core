"""FreeLLMAPI: fail-closed offline/privacy, loopback-only and real HTTP transport."""
from __future__ import annotations

import json
import socket
import threading
import time
import unittest
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from interface.api.app import create_app
from runtime.freellmapi_backend import FreeLLMAPIBackend, validate_freellmapi_endpoint
from runtime.inference_stack import InferenceStackConfig, LocalInferenceRouter
from runtime.internal_agent_runtime import InternalAgentRuntime


class StubFreeLLMAPI(BaseHTTPRequestHandler):
    requests = []
    redirect = False

    def log_message(self, *args):
        pass

    def do_GET(self):
        type(self).requests.append(("GET", self.path, self.headers.get("Authorization"), None))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"data": [{"id": "auto:cheap"}]}).encode())

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        type(self).requests.append((
            "POST", self.path, self.headers.get("Authorization"), json.loads(raw)
        ))
        if type(self).redirect:
            self.send_response(302)
            self.send_header("Location", "https://example.net/steal")
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Routed-Via", "fake/verified-local-test")
        self.end_headers()
        self.wfile.write(json.dumps({
            "model": "test-model",
            "id": "stub-response",
            "choices": [{"message": {"role": "assistant", "content": "teste real de HTTP"},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 7, "completion_tokens": 5},
        }).encode())


class _FakeInference:
    def __init__(self, status="sucesso"):
        self.status = status
        self.calls = []

    @property
    def configured(self):
        return True

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "status": self.status,
            "provider": "mock",
            "modelo": kwargs["model"],
            "conteudo": "offline" if self.status == "sucesso" else None,
        }

    def list_models(self):
        self.calls.append({"probe": True})
        return {"status": "sucesso", "modelos": ["local"]}


class FreeLLMAPIRouterTests(unittest.TestCase):
    def test_default_config_is_offline_local_only(self):
        c = InferenceStackConfig.from_env({})
        self.assertTrue(c.offline_mode)
        self.assertFalse(c.freellmapi_enabled)
        self.assertEqual(c.provider_order, ("llamacpp", "ollama"))
        self.assertIsNone(c.freellmapi_model)
        self.assertIsNone(c.freellmapi_api_key)

    def test_endpoint_requires_exact_loopback(self):
        self.assertIsNone(validate_freellmapi_endpoint("http://127.0.0.1:3001/v1"))
        for endpoint in [
            "https://freellmapi.co/v1",
            "http://10.0.0.3:3001/v1",
            "http://user:pass@127.0.0.1:3001/v1",
            "http://127.0.0.1:3001/v1?secret=abc",
            "http://127.0.0.1:3001/v1#foo",
            "http://127.0.0.1:3001/v2",
            "http://notlocalhost/v1",
        ]:
            with self.subTest(endpoint=endpoint):
                self.assertIsNotNone(validate_freellmapi_endpoint(endpoint))

    def _router(self, **changes):
        data = dict(
            enabled=True, provider_order=("llamacpp", "freellmapi"),
            model_general="local-model",
            freellmapi_enabled=True, freellmapi_model="auto:cheap",
            freellmapi_api_key="supersecret",
            offline_mode=False,
        )
        data.update(changes)
        router = LocalInferenceRouter(InferenceStackConfig(**data))
        router.backends["llamacpp"] = _FakeInference(status="indisponivel")
        router.backends["freellmapi"] = _FakeInference()
        return router

    def test_offline_mode_never_calls_cloud_even_with_consent(self):
        r = self._router(offline_mode=True)
        out = r.chat([{"role": "user", "content": "Publico"}],
                     provider="freellmapi", allow_external=True, data_classification="public")
        self.assertEqual(out["status"], "bloqueado")
        self.assertEqual(r.backends["freellmapi"].calls, [])

    def test_external_provider_flag_required(self):
        r = self._router(freellmapi_enabled=False)
        out = r.chat([{"role": "user", "content": "Publico"}],
                     provider="freellmapi", allow_external=True, data_classification="public")
        self.assertEqual(out["status"], "bloqueado")
        self.assertEqual(r.backends["freellmapi"].calls, [])

    def test_without_consent_or_with_private_data_stays_local(self):
        for allowed, classification in [
            (False, "public"), (True, "private"), (False, "private"),
            (True, "unknown"),
        ]:
            with self.subTest(allowed=allowed, classification=classification):
                r = self._router()
                out = r.chat([{"role": "user", "content": "Segredo"}],
                             provider="freellmapi", allow_external=allowed,
                             data_classification=classification)
                self.assertEqual(out["status"], "bloqueado")
                self.assertEqual(r.backends["freellmapi"].calls, [])

    def test_offline_local_succeeds_without_cloud(self):
        r = self._router()
        r.backends["llamacpp"] = _FakeInference()
        out = r.chat([{"role": "user", "content": "off"}])
        self.assertEqual(out["status"], "sucesso")
        self.assertEqual(out["provider"], "mock")
        self.assertEqual(r.backends["freellmapi"].calls, [])

    def test_local_failure_goes_cloud_only_when_authorized(self):
        r = self._router()
        out = r.chat([{"role": "user", "content": "informacao publica"}],
                     allow_external=True, data_classification="public")
        self.assertEqual(out["status"], "sucesso")
        self.assertEqual(out["roteamento"]["attempts"][0]["status"], "indisponivel")
        self.assertEqual(r.backends["freellmapi"].calls[0]["model"], "auto:cheap")

    def test_external_route_without_local_model_uses_configured_cloud_alias(self):
        r = self._router(model_general=None)
        out = r.chat([{"role": "user", "content": "publico"}],
                     provider="freellmapi", allow_external=True,
                     data_classification="public")
        self.assertEqual(out["status"], "sucesso")
        self.assertEqual(r.backends["freellmapi"].calls[0]["model"], "auto:cheap")

    def test_no_cloud_model_means_no_request(self):
        r = self._router(freellmapi_model=None, model_general=None)
        result = r.chat([{"role": "user", "content": "publico"}],
                        provider="freellmapi", allow_external=True,
                        data_classification="public")
        self.assertEqual(result["status"], "indisponivel")
        self.assertEqual(r.backends["freellmapi"].calls, [])

    def test_benchmark_inherits_privacy_policy(self):
        r = self._router()
        blocked = r.benchmark_model(["publico"], provider="freellmapi")
        self.assertEqual(blocked["status"], "indisponivel")
        self.assertEqual(r.backends["freellmapi"].calls, [])
        okay = r.benchmark_model(["publico"], provider="freellmapi",
                                 allow_external=True, data_classification="public")
        self.assertEqual(okay["sucessos"], 1)

    def test_status_probe_skips_cloud_until_separate_opt_in(self):
        r = self._router()
        report = r.status(probe=True)
        self.assertNotIn("probe", report["providers"]["freellmapi"])
        self.assertEqual(r.backends["freellmapi"].calls, [])
        report = r.status(probe=True, probe_external=True)
        self.assertIn("probe", report["providers"]["freellmapi"])

    def test_no_api_token_in_status(self):
        r = LocalInferenceRouter(InferenceStackConfig(
            enabled=True, freellmapi_enabled=True,
            freellmapi_api_key="never-in-status",
        ))
        self.assertNotIn("never-in-status", json.dumps(r.status()))

    def test_from_env_enabled_only_when_explicit(self):
        c = InferenceStackConfig.from_env({
            "JARVIS_INFERENCE_ENABLED": "true",
            "JARVIS_INFERENCE_OFFLINE_MODE": "false",
            "JARVIS_FREELLMAPI_ENABLED": "true",
            "JARVIS_FREELLMAPI_MODEL": "auto:cheap",
            "JARVIS_INFERENCE_PROVIDER_ORDER": "llamacpp,ollama,freellmapi",
        })
        self.assertEqual(c.provider_order[-1], "freellmapi")
        self.assertFalse(c.offline_mode)
        self.assertTrue(c.freellmapi_enabled)
        self.assertEqual(c.freellmapi_model, "auto:cheap")


class FreeLLMAPIHTTPTests(unittest.TestCase):
    def setUp(self):
        StubFreeLLMAPI.requests = []
        StubFreeLLMAPI.redirect = False
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), StubFreeLLMAPI)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.backend = FreeLLMAPIBackend(
            base_url=f"http://127.0.0.1:{self.http.server_port}/v1",
            api_key="fake-for-test",
            timeout_seconds=5,
        )

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=3)

    def test_real_loopback_http_receives_chat_and_headers(self):
        result = self.backend.chat(model="auto:cheap", messages=[
            {"role": "user", "content": "Ola"},
        ])
        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["modelo_servido"], "fake/verified-local-test")
        self.assertTrue(result["processamento_externo_possivel"])
        self.assertFalse(result["custo_confirmado_zero"])
        method, path, key, body = StubFreeLLMAPI.requests[-1]
        self.assertEqual((method, path), ("POST", "/v1/chat/completions"))
        self.assertEqual(key, "Bearer fake-for-test")
        self.assertEqual(body["model"], "auto:cheap")
        self.assertFalse(body["stream"])

    def test_rejects_redirect_not_following_external_host(self):
        StubFreeLLMAPI.redirect = True
        out = self.backend.chat(model="auto", messages=[{"role": "user", "content": "abc"}])
        self.assertEqual(out["status"], "indisponivel")

    def test_catalog_is_not_proof_of_quota(self):
        result = self.backend.list_models()
        self.assertEqual(result["modelos"], ["auto:cheap"])
        self.assertIn("nao", result["observacao"])

    def test_no_credentials_no_http(self):
        backend = FreeLLMAPIBackend(base_url=self.backend.base_url, api_key=None)
        out = backend.chat(model="auto", messages=[{"role": "user", "content": "hi"}])
        self.assertEqual(out["status"], "indisponivel")
        self.assertEqual(StubFreeLLMAPI.requests, [])

    def test_request_size_is_bounded(self):
        out = self.backend.chat(model="auto", messages=[
            {"role": "user", "content": "x" * (600 * 1024)}
        ])
        self.assertEqual(out["status"], "bloqueado")
        self.assertEqual(StubFreeLLMAPI.requests, [])

    def test_extra_body_does_not_override_credentials_or_model(self):
        out = self.backend.chat(model="auto", messages=[{"role": "user", "content": "ok"}],
                                extra_body={"messages": [{"role": "user", "content": "override"}]})
        self.assertEqual(out["status"], "bloqueado")
        self.assertEqual(StubFreeLLMAPI.requests, [])


class FreeLLMAPITRUSTEDAPITests(unittest.TestCase):
    def setUp(self):
        self.runtime = InternalAgentRuntime()
        self.runtime.bootstrap()
        self.client = TestClient(create_app(runtime=self.runtime,
                                            api_token="llmapi-test-token",
                                            trusted_device_id="llmapi-test-device"))

    def _headers(self):
        return {
            "X-Jarvis-Token": "llmapi-test-token",
            "X-Jarvis-Device-Id": "llmapi-test-device",
            "X-Jarvis-Nonce": str(uuid.uuid4()),
            "X-Jarvis-Timestamp": str(int(time.time())),
        }

    def test_route_not_accessible_without_trusted_auth(self):
        r = self.client.post("/api/inferencia/chat?provider=freellmapi",
                             json=[{"role": "user", "content": "a"}])
        self.assertNotEqual(r.status_code, 200)

    def test_api_without_consent_never_calls_backend(self):
        from dataclasses import replace
        old = self.runtime.inference_router
        c = InferenceStackConfig(enabled=True, freellmapi_enabled=True,
                                  offline_mode=False, freellmapi_model="auto:cheap")
        r = LocalInferenceRouter(c)
        r.backends["freellmapi"] = _FakeInference()
        self.runtime.inference_router = r
        result = self.client.post("/api/inferencia/chat?provider=freellmapi",
                                  headers=self._headers(),
                                  json=[{"role": "user", "content": "not public"}])
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["status"], "bloqueado")
        self.assertEqual(r.backends["freellmapi"].calls, [])

    def test_api_with_public_consent_reaches_only_authorized_backend(self):
        c = InferenceStackConfig(enabled=True, freellmapi_enabled=True,
                                  offline_mode=False, freellmapi_model="auto:cheap")
        r = LocalInferenceRouter(c)
        r.backends["freellmapi"] = _FakeInference()
        self.runtime.inference_router = r
        result = self.client.post(
            "/api/inferencia/chat?provider=freellmapi&permitir_externo=true&classificacao=public",
            headers=self._headers(), json=[{"role": "user", "content": "publico"}]
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["status"], "sucesso")
        self.assertEqual(len(r.backends["freellmapi"].calls), 1)


if __name__ == "__main__":
    unittest.main()
