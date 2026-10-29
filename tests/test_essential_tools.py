"""Integração real de consultas locais com inferência e limites de autoridade."""
import json
from types import SimpleNamespace

import pytest

from learning.research_knowledge_engine import ResearchKnowledgeEngine
from learning.codebase_intelligence_engine import CodebaseIntelligenceConfig, CodebaseIntelligenceEngine
from runtime.inference_stack import InferenceStackConfig, LocalInferenceRouter
from runtime.essential_tools import EssentialToolRegistry, EssentialToolAssistant


class ScriptedBackend:
    """Substitui somente o servidor de modelo, que não está provisionado no CI."""
    base_url = "http://127.0.0.1:8080/v1"

    def __init__(self, answers):
        self.answers = iter(answers)
        self.requests = []

    def chat(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs)))
        return next(self.answers)


def answer(content="", calls=None, **extra):
    return {"status": "sucesso", "provider": "llamacpp", "modelo": "fixture",
            "conteudo": content, "tool_calls": calls or [], "finish_reason": "stop",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            **extra}


def call(name="documents_search", arguments=None, call_id="call-1"):
    return {"id": call_id, "type": "function", "function": {
        "name": name, "arguments": json.dumps(arguments or {"query": "bateria"})}}


@pytest.fixture
def registry(tmp_path):
    knowledge = ResearchKnowledgeEngine(knowledge_dir=tmp_path, db_path=tmp_path / "knowledge.db")
    item = knowledge.ingest_source("Manual", "documento", "A bateria dura oito horas.")
    knowledge.ingest_document_chunks(item["item_id"], [{"text": "A bateria dura oito horas."}],
                                     source_path="manual.txt", source_sha256="a" * 64)
    (tmp_path / "app.py").write_text("def carregar():\n    return 8\n\ndef iniciar():\n    return carregar()\n")
    graph = CodebaseIntelligenceEngine(CodebaseIntelligenceConfig(
        project_root=tmp_path, db_path=tmp_path / "code.db"))
    graph.index(prefer_external=False)
    runtime = SimpleNamespace(research_knowledge_engine=knowledge,
        codebase_intelligence_engine=graph,
        web_browser_engine=SimpleNamespace(describe_capabilities=lambda: {"searxng": False}),
        mcp_manager=SimpleNamespace(status=lambda: {"enabled": False}),
        capability_foundry=SimpleNamespace(list_capabilities=lambda: []))
    return EssentialToolRegistry(runtime)


def assistant(registry, answers):
    router = LocalInferenceRouter(InferenceStackConfig(enabled=True,
        provider_order=("llamacpp",), model_general="fixture"))
    backend = ScriptedBackend(answers)
    router.backends = {"llamacpp": backend}
    return EssentialToolAssistant(router, registry), backend


def test_document_result_preserves_source_and_full_evidence(registry):
    result = registry.execute("documents_search", {"query": "bateria"})
    assert result["status"] == "sucesso"
    assert result["resultados"][0]["conteudo"] == "A bateria dura oito horas."
    assert result["resultados"][0]["source_path"] == "manual.txt"
    assert result["resultados"][0]["source_sha256"] == "a" * 64


def test_code_search_and_impact_use_local_graph(registry):
    assert registry.execute("code_search", {"query": "carregar"})["resultados"][0]["path"] == "app.py"
    impact = registry.execute("code_impact", {"symbol": "carregar"})
    assert impact["status"] == "sucesso"
    assert impact["impacto_direto_indireto"][0]["evidence_path"] == "app.py"


@pytest.mark.parametrize("name,args", [
    ("shell", {"command": "echo bad"}),
    ("documents_search", {"query": "x", "path": "/private"}),
    ("documents_search", {"query": ""}),
    ("documents_search", {"query": 1}),
    ("documents_search", {"query": "x" * 501}),
    ("documents_search", []),
    ("integrations_status", {"extra": True}),
    ("web_search", {"query": "bateria"}),
])
def test_unapproved_or_invalid_tool_never_executes(registry, name, args):
    assert registry.execute(name, args)["status"] == "bloqueado"


def test_default_schemas_do_not_offer_network(registry):
    names = {x["function"]["name"] for x in registry.schemas()}
    assert names == {"documents_search", "code_search", "code_impact", "integrations_status"}
    assert "web_fetch" in {x["function"]["name"] for x in registry.schemas(["web_fetch"])}


def test_tool_result_is_returned_to_model_before_final_answer(registry):
    runner, backend = assistant(registry, [answer(calls=[call()]), answer("Oito horas [manual.txt].")])
    out = runner.run("Quanto dura a bateria?")
    assert out["status"] == "sucesso"
    assert out["resposta"] == "Oito horas [manual.txt]."
    assert out["chamadas_modelo"] == 2
    tool_message = backend.requests[1]["messages"][-1]
    assert tool_message["role"] == "tool"
    assert tool_message["tool_call_id"] == "call-1"
    assert json.loads(tool_message["content"])["resultados"][0]["source_path"] == "manual.txt"
    assert backend.requests[1]["messages"][-2]["tool_calls"][0]["id"] == "call-1"


def test_budget_stops_repeated_tool_requests(registry):
    runner, backend = assistant(registry, [answer(calls=[call(call_id=f"c{i}")]) for i in range(5)])
    out = runner.run("Pesquise", max_rounds=1)
    assert out["status"] == "limite_atingido"
    assert out["resposta"] is None
    assert len(backend.requests) == 2
    assert backend.requests[-1]["tools"] is None


@pytest.mark.parametrize("response,status", [
    (answer("incompleta", finish_reason="length"), "incompleto"),
    ({"status": "indisponivel", "motivo": "Sem modelo"}, "indisponivel"),
    (answer(), "incompleto"),
    (answer(calls=[{"id": "a", "type": "function", "function": {"name": "documents_search", "arguments": "not-json"}}]), "chamada_invalida"),
    (answer(calls=[call(), call()]), "chamada_invalida"),
])
def test_failures_do_not_become_success(registry, response, status):
    runner, _ = assistant(registry, [response])
    out = runner.run("Pergunta")
    assert out["status"] == status
    assert out["resposta"] is None


def test_no_remote_model_even_if_legacy_router_allows_it(registry):
    runner, backend = assistant(registry, [answer("nao pode")])
    backend.base_url = "https://remote.invalid/v1"
    out = runner.run("Segredo")
    assert out["status"] == "indisponivel"
    assert not backend.requests


@pytest.mark.parametrize("repeated", ["á", '"\\'])
def test_oversized_result_remains_valid_json_and_is_marked(registry, repeated):
    registry.runtime.research_knowledge_engine.ingest_document_chunks("large", [
        {"text": "bateria " + repeated * 40000}])
    runner, backend = assistant(registry, [answer(calls=[call()]), answer("Resultado parcial")])
    out = runner.run("bateria")
    message = json.loads(backend.requests[1]["messages"][-1]["content"])
    assert message["truncado"] is True
    assert len(backend.requests[1]["messages"][-1]["content"]) <= 12500
    assert out["ferramentas"][0]["truncado"] is True


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from interface.api.app import create_app
    from runtime.internal_agent_runtime import InternalAgentRuntime
    from security.iris_instance_policy import IrisInstanceAuthority
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path / "runtime-data"))
    runtime = InternalAgentRuntime()
    authority = IrisInstanceAuthority("owner-essential-test-" + "a" * 32)
    client = TestClient(create_app(runtime=runtime, api_token="essential-test",
        trusted_device_id="essential-local", iris_instance_authority=authority))
    yield client, runtime, authority
    runtime.shutdown_vital_organs(reason="test_complete")
    client.close()


def api_headers(instance_id="iris-original", instance_token=None):
    import time
    import uuid
    return {"X-Jarvis-Token": "essential-test", "X-Jarvis-Device-Id": "essential-local",
        "X-Jarvis-Nonce": str(uuid.uuid4()), "X-Jarvis-Timestamp": str(int(time.time())),
        "X-Iris-Instance-Id": instance_id,
        "X-Iris-Instance-Token": instance_token or "owner-essential-test-" + "a" * 32}


def test_api_catalog_requires_owner_even_with_global_device_token(api_client):
    client, _, _ = api_client
    assert client.get("/api/assistente/ferramentas").status_code == 401
    headers = api_headers()
    headers.pop("X-Iris-Instance-Token")
    assert client.get("/api/assistente/ferramentas", headers=headers).status_code == 401
    out = client.get("/api/assistente/ferramentas", headers=api_headers())
    assert out.status_code == 200
    assert out.json()["rede_por_padrao"] is False


def test_resident_cannot_query_original_tools(api_client):
    client, _, authority = api_client
    resident = authority.create_resident("owner-essential-test-" + "a" * 32,
        tenant_id="resident-test", display_name="Residente", user_consented=True)
    out = client.post("/api/assistente/executar", headers=api_headers(
        resident["instance_id"], resident["token"]), json={"texto": "Busque meus documentos"})
    assert out.status_code == 403


def test_api_runs_local_tool_loop_and_rejects_replay(api_client, registry):
    client, runtime, _ = api_client
    runner, _ = assistant(registry, [answer(calls=[call()]), answer("Oito horas [manual.txt].")])
    runtime.bootstrap()
    runtime.tool_assistant = runner
    headers = api_headers()
    out = client.post("/api/assistente/executar", headers=headers, json={"texto": "Qual a autonomia?"})
    assert out.status_code == 200
    assert out.json()["resposta"] == "Oito horas [manual.txt]."
    assert client.post("/api/assistente/executar", headers=headers,
        json={"texto": "Repetir"}).status_code == 403


def test_local_provider_failure_falls_back_without_using_remote_gateway(registry):
    runner, first = assistant(registry, [{"status": "indisponivel"}])
    second = ScriptedBackend([answer("Resposta do Ollama", provider="ollama")])
    runner.router.config = InferenceStackConfig(enabled=True,
        provider_order=("llamacpp", "freellmapi", "ollama"), model_general="fixture")
    runner.router.backends["ollama"] = second
    out = runner.run("Olá")
    assert out["status"] == "sucesso"
    assert out["resposta"] == "Resposta do Ollama"
    assert out["provider"] == "ollama"
    assert out["chamadas_modelo"] == 2


def test_network_selection_does_not_allow_private_urls(registry):
    out = registry.execute("web_fetch", {"url": "http://127.0.0.1:8080/private"},
        allowed_tools=["web_fetch"])
    assert out["status"] == "bloqueado"


def test_web_tool_refuses_private_redirect_even_with_permissive_legacy_engine(registry, monkeypatch):
    from runtime.web_browser_engine import WebBrowserEngine
    from runtime.web_stack import WebStackConfig
    from urllib.request import Request
    engine = WebBrowserEngine(config=WebStackConfig(allow_private_targets=True,
        crawl4ai_enabled=True, playwright_enabled=True))
    monkeypatch.setattr(engine, "fetch_page_content", lambda url: {
        "status": "sucesso", "conteudo_texto_limpo": "PRIVATE CONTENT"})
    registry.runtime.web_browser_engine = engine

    class RedirectAttempt:
        def __init__(self, handler):
            self.handler = handler

        def open(self, req, timeout):
            return self.handler.redirect_request(Request("http://93.184.216.34"),
                None, 302, "Found", {}, "http://127.0.0.1/private")

    def opener(*handlers):
        redirect = next(h for h in handlers if hasattr(h, "redirect_request"))
        return RedirectAttempt(redirect)

    monkeypatch.setattr("runtime.web_stack.urllib.request.build_opener", opener)
    out = registry.execute("web_fetch", {"url": "http://93.184.216.34"}, allowed_tools=["web_fetch"])
    assert out["status"] != "sucesso"
    assert "PRIVATE CONTENT" not in json.dumps(out)


def test_public_fetch_rechecks_and_pins_dns_connection(registry, monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import socket
    import threading
    from runtime.web_browser_engine import WebBrowserEngine
    from runtime.web_stack import WebStackConfig

    class PrivateServer(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"PRIVATE THROUGH REBIND")

    server = ThreadingHTTPServer(("127.0.0.1", 0), PrivateServer)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    original = socket.getaddrinfo
    resolutions = []

    def rebind(host, port, *args, **kwargs):
        if host == "rebind.test":
            resolutions.append(host)
            ip = "93.184.216.34" if len(resolutions) <= 2 else "127.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]
        return original(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", rebind)
    monkeypatch.setattr("urllib.request.getproxies", lambda: {})
    monkeypatch.setattr("urllib.request._opener", None)
    registry.runtime.web_browser_engine = WebBrowserEngine(config=WebStackConfig())
    try:
        out = registry.execute("web_fetch", {"url": f"http://rebind.test:{server.server_port}"},
            allowed_tools=["web_fetch"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert out["status"] != "sucesso"
    assert "PRIVATE THROUGH REBIND" not in json.dumps(out)


def test_local_model_ignores_environment_proxy(registry, monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    prompts = []

    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            prompts.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"choices":[{"message":{"content":"remote answer"}}]}')

    proxy = ThreadingHTTPServer(("127.0.0.1", 0), Proxy)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr("urllib.request.getproxies", lambda: {"http": f"http://127.0.0.1:{proxy.server_port}"})
    monkeypatch.setattr("urllib.request.proxy_bypass", lambda host: False)
    monkeypatch.setattr("urllib.request._opener", None)
    router = LocalInferenceRouter(InferenceStackConfig(enabled=True,
        provider_order=("llamacpp",), model_general="fixture", timeout_seconds=1,
        llamacpp_base_url="http://127.0.0.1:1/v1"))
    try:
        out = EssentialToolAssistant(router, registry).run("PRIVATE PROMPT")
    finally:
        proxy.shutdown()
        proxy.server_close()
        thread.join(timeout=2)
    assert not prompts
    assert out["status"] == "indisponivel"


def test_loopback_model_does_not_follow_redirects(registry):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    followed = []

    class Redirect(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{self.server.server_port}/leak")
            self.end_headers()

        def do_GET(self):
            followed.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"choices":[{"message":{"content":"redirected"}}]}')

    server = ThreadingHTTPServer(("127.0.0.1", 0), Redirect)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    router = LocalInferenceRouter(InferenceStackConfig(enabled=True,
        provider_order=("llamacpp",), model_general="fixture", timeout_seconds=1,
        llamacpp_api_key="private-fixture-key", llamacpp_base_url=f"http://127.0.0.1:{server.server_port}/v1"))
    try:
        out = EssentialToolAssistant(router, registry).run("PRIVATE PROMPT")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not followed
    assert out["status"] == "indisponivel"


def test_backend_extra_fields_are_not_forwarded_to_next_prompt(registry):
    request = call()
    request["untrusted_extra"] = "x" * 100000
    request["function"]["untrusted_extra"] = "x" * 100000
    runner, backend = assistant(registry, [answer(calls=[request]), answer("Resultado")])
    assert runner.run("bateria")["status"] == "sucesso"
    accepted = backend.requests[1]["messages"][-2]["tool_calls"][0]
    assert set(accepted) == {"id", "type", "function"}
    assert set(accepted["function"]) == {"name", "arguments"}


def test_six_tool_calls_then_final_answer_have_hard_budget(registry):
    runner, backend = assistant(registry, [
        answer(calls=[call(call_id=f"a{i}") for i in range(3)]),
        answer(calls=[call(call_id=f"b{i}") for i in range(3)]),
        answer("Concluído a partir das consultas.")])
    out = runner.run("Pesquise")
    assert out["status"] == "sucesso"
    assert len(out["ferramentas"]) == 6
    assert len(backend.requests) == 3
    assert backend.requests[-1]["tools"] is None


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_real_local_http_transport_carries_tool_result(registry, host, monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import threading
    import socket
    received = []

    class Endpoint(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            received.append(payload)
            if len(received) == 1:
                message = {"role": "assistant", "content": None, "tool_calls": [call()]}
                finish = "tool_calls"
            else:
                result = json.loads(payload["messages"][-1]["content"])
                message = {"role": "assistant", "content": result["resultados"][0]["conteudo"]}
                finish = "stop"
            raw = json.dumps({"model": "fixture", "choices": [{
                "message": message, "finish_reason": finish}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Endpoint)
    original_dns = socket.getaddrinfo

    def local_dns(name, port, *args, **kwargs):
        if name == "localhost":
            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("::1", port, 0, 0)),
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
        return original_dns(name, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", local_dns)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        router = LocalInferenceRouter(InferenceStackConfig(enabled=True,
            provider_order=("llamacpp",), model_general="fixture", timeout_seconds=2,
            llamacpp_base_url=f"http://{host}:{server.server_port}/v1"))
        out = EssentialToolAssistant(router, registry).run("Quanto dura a bateria?")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert out["status"] == "sucesso"
    assert out["resposta"] == "A bateria dura oito horas."
    assert len(received) == 2
    assert received[0]["tools"][0]["function"]["name"] == "documents_search"


def test_api_absent_local_model_returns_unavailable(api_client):
    client, _, _ = api_client
    out = client.post("/api/assistente/executar", headers=api_headers(), json={"texto": "Olá"})
    assert out.status_code == 200
    assert out.json()["status"] == "indisponivel"
    assert out.json()["resposta"] is None


def test_existing_conversation_can_invoke_local_consultation(api_client, registry):
    client, runtime, _ = api_client
    runtime.bootstrap()
    runtime.tool_assistant, _ = assistant(registry, [answer(calls=[call()]), answer("Oito horas.")])
    out = client.post("/api/comando", headers=api_headers(),
        json={"texto": "consultar: Qual a duração da bateria?"})
    assert out.status_code == 200
    assert out.json()["resposta"] == "Oito horas."
    assert out.json()["acao"] == "tool_assistant"


def test_conversation_consultation_cannot_bypass_instance_guard(api_client):
    client, _, _ = api_client
    headers = api_headers()
    headers.pop("X-Iris-Instance-Token")
    out = client.post("/api/comando", headers=headers,
        json={"texto": "consultar: Qual a duração da bateria?"})
    assert out.status_code == 401


def test_native_consultation_sends_instance_credentials_and_waits_for_model(monkeypatch):
    from io import BytesIO
    from interface.native_app.api_client import JarvisApiClient
    received = []

    def transport(req, timeout):
        received.append((req, timeout))
        return BytesIO(b'{"resposta":"ok"}')

    monkeypatch.setattr("interface.native_app.api_client.request.urlopen", transport)
    config = SimpleNamespace(api_base_url="http://127.0.0.1:8000", api_token="api-token",
        device_id="local-device", request_timeout_seconds=10,
        assistant_timeout_seconds=500, iris_instance_id="iris-original", iris_instance_token="owner-token")
    client = JarvisApiClient(config)
    assert client.send_command("consultar: documentos")["resposta"] == "ok"
    req, timeout = received[0]
    assert timeout == 500
    assert req.get_header("X-iris-instance-id") == "iris-original"
    assert req.get_header("X-iris-instance-token") == "owner-token"
    client.send_command("status")
    assert received[1][1] == 10
