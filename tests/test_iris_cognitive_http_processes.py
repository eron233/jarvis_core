"""E2E HTTP real: servidor e no trabalhador em processos independentes.

Cobre conexao, retomada de conversa apos restart e modelo FAKE declarado.
Nao simula velocidade, qualidade ou disponibilidade de um LLM fisico.
"""
from __future__ import annotations

import json
import multiprocessing
import secrets
import socket
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from device.iris_node_worker import IrisNodeWorker
from device.iris_inference_tasks import IrisLocalInferenceExecutor
from runtime.iris_distributed_bootstrap import create_local_iris_stack


def _serve_iris(root: str, environ: dict[str, str], port: int):
    import uvicorn
    from interface.api.app import create_app
    from runtime.internal_agent_runtime import InternalAgentRuntime

    stack = create_local_iris_stack(Path(root), environ=environ)
    try:
        app = create_app(
            runtime=InternalAgentRuntime(),
            api_token="legacy-test-only-not-for-production",
            trusted_device_id="test-local-workstation",
            **stack.api_options(),
        )
        uvicorn.run(
            app, host="127.0.0.1", port=port,
            log_level="critical", access_log=False,
        )
    finally:
        stack.close()


class MockModel:
    def __init__(self):
        self.config = SimpleNamespace(
            enabled=True, offline_mode=True, allow_remote_endpoints=False,
        )
        self.requests = []

    def chat(self, **kwargs):
        self.requests.append(kwargs["messages"])
        if kwargs["allow_external"] or kwargs["data_classification"] != "private":
            raise AssertionError("Tentativa de extrair dados privados.")
        return {
            "status": "sucesso", "modelo": "modelo-local-falso-de-teste",
            "conteudo": f"Falei pela vez {len(self.requests)}",
        }


class IrisE2eCognitiveHttpTests(unittest.TestCase):
    def test_conversa_via_http_e_reinicio_da_api(self):
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "private"
            env = {
                "IRIS_OWNER_TOKEN": secrets.token_urlsafe(32),
                "IRIS_IDENTITY_KEY_HEX": secrets.token_hex(32),
                "IRIS_MESH_KEY_HEX": secrets.token_hex(32),
                "IRIS_STATE_KEY_HEX": secrets.token_hex(32),
                "IRIS_BROKER_KEY_HEX": secrets.token_hex(32),
                "IRIS_SOURCE_ID": "iris-source-process-e2e-01",
            }
            stack = create_local_iris_stack(root, environ=env)
            try:
                alice = stack.authority.create_resident(
                    env["IRIS_OWNER_TOKEN"],
                    tenant_id="tenant-alice",
                    display_name="Íris da Alice",
                    user_consented=True,
                )
                offer = stack.mesh.offer_device(
                    device_name="Computador secundário",
                    device_type="linux",
                    surfaces={"compute.infer"},
                    locally_approved=True,
                )
                node = stack.mesh.approve_offer(
                    alice["instance_id"], alice["token"],
                    offer_id=offer["offer_id"],
                    verification_code=offer["verification_code"],
                )
            finally:
                stack.close()
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            endpoint = f"http://127.0.0.1:{port}"
            headers = {
                "X-Iris-Instance-Id": alice["instance_id"],
                "X-Iris-Instance-Token": alice["token"],
            }

            def http(method, route, body=None):
                encoded = json.dumps(body).encode() if body is not None else None
                request = Request(
                    endpoint + route, data=encoded, method=method,
                    headers={
                        **headers, "Content-Type": "application/json",
                    },
                )
                with urlopen(request, timeout=5) as response:
                    return json.loads(response.read())

            def launch():
                proc = context.Process(
                    target=_serve_iris, args=(str(root), env, port),
                )
                proc.start()
                for _ in range(90):
                    if not proc.is_alive():
                        self.fail("Servidor Iris terminou antes de iniciar.")
                    try:
                        http("GET", "/api/iris/instancia")
                        return proc
                    except (URLError, TimeoutError):
                        time.sleep(.1)
                self.fail("Servidor Iris nao iniciou a tempo.")

            def stop(proc):
                if proc is None:
                    return
                proc.terminate()
                proc.join(timeout=8)
                if proc.is_alive():
                    proc.kill()
                    proc.join(timeout=8)

            proc = None
            fake = MockModel()
            worker = IrisNodeWorker(
                endpoint, node["node_id"], node["node_token"],
                inference_executor=IrisLocalInferenceExecutor(fake),
            )
            try:
                proc = launch()
                task = http("POST", "/api/iris/dialogue/turn", {
                    "conversation_id": "test-chat",
                    "text": "Íris, consegue conversar?",
                })
                self.assertEqual(task["status"], "queued")
                self.assertEqual(worker.run_once()["status"], "completed")
                first = http("GET", "/api/iris/dialogue/test-chat/finish")
                self.assertEqual(first["content"], "Falei pela vez 1")
                self.assertEqual(len(http(
                    "GET", "/api/iris/dialogue/test-chat/history",
                )["turns"]), 2)
                stop(proc)
                proc = None
                with self.assertRaises(URLError):
                    http("GET", "/api/iris/dialogue/test-chat/history")
                proc = launch()
                self.assertEqual(len(http(
                    "GET", "/api/iris/dialogue/test-chat/history",
                )["turns"]), 2)
                second = http("POST", "/api/iris/dialogue/turn", {
                    "conversation_id": "test-chat",
                    "text": "Ainda lembra de mim?",
                })
                self.assertEqual(second["status"], "queued")
                self.assertEqual(worker.run_once()["status"], "completed")
                response = http("GET", "/api/iris/dialogue/test-chat/finish")
                self.assertEqual(response["content"], "Falei pela vez 2")
                self.assertIn(
                    {"role": "assistant", "content": "Falei pela vez 1"},
                    fake.requests[1],
                )
            finally:
                stop(proc)


if __name__ == "__main__":
    unittest.main()
