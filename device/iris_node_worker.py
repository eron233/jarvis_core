"""Agente de computacao limitado da malha Iris, iniciado voluntariamente.

Nao instala nada, nao explora rede, nao executa scripts, nao acessa arquivos,
nao abre programas e nao tem poderes de administrador. Trabalhos sempre sao
puxados de um servidor previamente configurado e autenticados por token.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler, Request

from device.iris_task_broker import execute_local_operation
from device.iris_inference_tasks import IrisLocalInferenceExecutor, IrisInferenceUnavailable


class IrisNodeTransportError(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        # Credenciais nao podem acompanhar redirecionamentos arbitrarios.
        return None


class IrisNodeWorker:
    def __init__(
        self, endpoint: str, node_id: str, node_token: str,
        *, inference_executor: IrisLocalInferenceExecutor | None = None,
    ):
        url = urlsplit(endpoint)
        if url.username is not None or url.password is not None:
            raise ValueError("Credenciais na URL nao sao aceitas.")
        if url.query or url.fragment or url.path not in {"", "/"}:
            raise ValueError("A URL deve apontar para a raiz da API.")
        if url.scheme != "https" and not (
            url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("Conexao remota exige HTTPS.")
        if not url.hostname or not isinstance(node_id, str) or not isinstance(node_token, str):
            raise ValueError("Credenciais de no ausentes.")
        if not node_id.startswith("iris-node-") or len(node_token) < 30:
            raise ValueError("Identidade de no invalida.")
        self.endpoint = endpoint.rstrip("/")
        self.node_id = node_id
        self._node_token = node_token
        self._opener = build_opener(NoRedirect())
        self._inference_executor = inference_executor

    def _post(self, path: str, payload: dict | None = None) -> dict:
        data = json.dumps(payload if payload is not None else {}).encode("utf-8")
        request = Request(
            self.endpoint + path,
            data=data, method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Iris-Node-Id": self.node_id,
                "X-Iris-Node-Token": self._node_token,
            },
        )
        try:
            with self._opener.open(request, timeout=10) as response:
                raw = response.read(65537)
        except (HTTPError, URLError, OSError) as exc:
            raise IrisNodeTransportError("Servidor Iris nao respondeu a requisicao.") from exc
        if len(raw) > 65536:
            raise IrisNodeTransportError("Resposta do servidor excedeu limite.")
        try:
            body = json.loads(raw)
        except (UnicodeDecodeError, ValueError) as exc:
            raise IrisNodeTransportError("Resposta invalida.") from exc
        if not isinstance(body, dict):
            raise IrisNodeTransportError("Formato de resposta invalido.")
        return body

    def run_once(self) -> dict:
        task = self._post("/api/iris/no/tarefa/claim")
        if task.get("status") == "idle":
            return {"status": "idle"}
        if task.get("status") != "leased":
            raise IrisNodeTransportError("Contrato de tarefa desconhecido.")
        operation = task.get("operation")
        payload = task.get("payload")
        job_id = task.get("job_id")
        lease_token = task.get("lease_token")
        if not isinstance(job_id, str) or not isinstance(lease_token, str):
            raise IrisNodeTransportError("Lease invalido.")
        # O contrato de operacao nao confia no payload recebido: valida antes.
        if operation == "inference.chat":
            if self._inference_executor is None:
                self._inference_executor = IrisLocalInferenceExecutor()
            # Se o modelo estiver indisponivel, nao confirmar a tarefa. O
            # broker tentara reentregar apos expirar a lease.
            result = self._inference_executor.execute(payload)
        else:
            result = execute_local_operation(operation, payload)
        receipt = self._post("/api/iris/no/tarefa/complete", {
            "job_id": job_id, "lease_token": lease_token, "result": result,
        })
        if receipt.get("status") != "completed" or receipt.get("job_id") != job_id:
            raise IrisNodeTransportError("Confirmacao de resultado invalida.")
        return {"status": "completed", "job_id": job_id, "verified": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Worker Iris: tarefas puras autorizadas.")
    parser.add_argument("--cycles", type=int, default=1, help="Numero maximo de consultas (1-100).")
    args = parser.parse_args(argv)
    if not 1 <= args.cycles <= 100:
        parser.error("Informe 1 a 100 ciclos.")
    worker = IrisNodeWorker(
        os.environ.get("IRIS_NODE_ENDPOINT", ""),
        os.environ.get("IRIS_NODE_ID", ""),
        os.environ.get("IRIS_NODE_TOKEN", ""),
    )
    for attempt in range(args.cycles):
        outcome = worker.run_once()
        print(json.dumps(outcome, ensure_ascii=False))
        if attempt < args.cycles - 1 and outcome["status"] == "idle":
            time.sleep(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
