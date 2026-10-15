"""Fila de trabalhos pequenos para nos Iris autorizados, com contrato fixo.

Nenhum shell, script, instalador, entrada de microfone, captura de tela ou
executavel externo pode ser entregue pela fila. Somente operacoes puras e
limitadas, processadas por um agente voluntariamente instalado pelo titular.
O broker e VOLATIL: nao sustenta a propria Iris se o servidor cair.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import hmac
import json
import math
import re
import secrets
from threading import RLock
import time
from typing import Any, Callable

from device.iris_mesh import IrisDeviceMesh

MAX_PENDING_PER_INSTANCE = 64
MAX_PAYLOAD_BYTES = 4096
MAX_RESULT_BYTES = 4096
LEASE_SECONDS = 45
TASK_TTL_SECONDS = 600
MAX_TASKS_TOTAL = 1024

_OPERATIONS = frozenset({"text.word_count", "math.sum", "hash.sha256"})


def validate_operation(operation: str, payload: Any) -> dict[str, Any]:
    """Converte a tarefa a formato seguro e fechado, sem entrada arbitraria."""
    if operation not in _OPERATIONS or not isinstance(payload, dict):
        raise ValueError("Operacao nao autorizada.")
    if operation == "text.word_count":
        if set(payload) != {"text"} or not isinstance(payload["text"], str) or len(payload["text"]) > 2000:
            raise ValueError("Texto invalido ou longo demais.")
        safe = {"text": payload["text"]}
    elif operation == "hash.sha256":
        if set(payload) != {"text"} or not isinstance(payload["text"], str) or len(payload["text"]) > 2000:
            raise ValueError("Texto invalido ou longo demais.")
        safe = {"text": payload["text"]}
    else:
        values = payload.get("values")
        if (set(payload) != {"values"} or not isinstance(values, list)
            or not 1 <= len(values) <= 100
            or any(type(v) not in (int, float) or not math.isfinite(v)
                   or abs(v) > 1_000_000 for v in values)):
            raise ValueError("Numeros invalidos.")
        safe = {"values": values}
    if len(json.dumps(safe, ensure_ascii=False).encode("utf-8")) > MAX_PAYLOAD_BYTES:
        raise ValueError("Payload excede limite.")
    return safe


def execute_local_operation(operation: str, payload: dict[str, Any]) -> Any:
    """Executante deterministico e puro para o pequeno contrato de operacoes."""
    safe = validate_operation(operation, payload)
    if operation == "text.word_count":
        return {"words": len(safe["text"].split())}
    if operation == "math.sum":
        result = math.fsum(safe["values"])
        if not math.isfinite(result):
            raise ValueError("Resultado nao finito.")
        return {"sum": result}
    return {"sha256": sha256(safe["text"].encode("utf-8")).hexdigest()}


@dataclass
class BrokerJob:
    job_id: str
    instance_id: str
    operation: str
    payload: dict[str, Any]
    created: float
    status: str = "queued"
    assigned_node: str | None = None
    lease_digest: str | None = None
    lease_until: float | None = None
    attempts: int = 0
    result: Any = None


class IrisTaskBroker:
    """Fila de memoria com autenticação separada do JARVIS_TOKEN legado."""

    def __init__(self, mesh: IrisDeviceMesh, *, clock: Callable[[], float] = time.time) -> None:
        self.mesh = mesh
        self.clock = clock
        self._lock = RLock()
        self._jobs: dict[str, BrokerJob] = {}

    def _purge(self) -> None:
        # Retencao curta e nao configuravel de entradas/resultado.
        for job_id, job in tuple(self._jobs.items()):
            if self.clock() - job.created > TASK_TTL_SECONDS:
                self._jobs.pop(job_id, None)

    def submit(
        self, instance_id: str, instance_token: str,
        *, operation: str, payload: dict[str, Any],
    ) -> dict[str, Any]:
        self.mesh.authority.require(instance_id, instance_token, "device.local")
        safe = validate_operation(operation, payload)
        route = self.mesh.route(instance_id, instance_token, surface="compute.light")
        if route["status"] != "routed" or route.get("execution_kind") != "native_agent":
            return {"status": "unavailable", "submitted": False}
        if not any(
            device["node_id"] == route.get("node_id") and device["mode"] == "integrated"
            for device in self.mesh.devices(instance_id, instance_token)
        ):
            return {"status": "unavailable", "submitted": False}
        with self._lock:
            self._purge()
            open_tasks = sum(
                j.instance_id == instance_id and j.status in {"queued", "leased"}
                for j in self._jobs.values()
            )
            if open_tasks >= MAX_PENDING_PER_INSTANCE or len(self._jobs) >= MAX_TASKS_TOTAL:
                raise ValueError("Fila atingiu limite.")
            job_id = "iris-job-" + secrets.token_hex(16)
            self._jobs[job_id] = BrokerJob(
                job_id=job_id, instance_id=instance_id,
                operation=operation, payload=safe, created=self.clock(),
            )
            return {"status": "queued", "submitted": True, "job_id": job_id}

    def claim(self, node_id: str, node_token: str) -> dict[str, Any]:
        """Um agente de computador pareado recolhe trabalho do proprio dono."""
        instance_id = self.mesh.authorize_node(
            node_id, node_token, required_surface="compute.light",
        )
        with self._lock:
            self._purge()
            jobs = sorted(
                (job for job in self._jobs.values()
                 if job.instance_id == instance_id
                 and (job.status == "queued"
                      or (job.status == "leased"
                          and job.lease_until is not None
                          and self.clock() >= job.lease_until))),
                key=lambda job: (job.created, job.job_id),
            )
            if not jobs:
                return {"status": "idle"}
            job = jobs[0]
            job.status = "leased"
            job.assigned_node = node_id
            job.attempts += 1
            job.lease_until = self.clock() + LEASE_SECONDS
            lease = secrets.token_urlsafe(32)
            job.lease_digest = sha256(lease.encode("utf-8")).hexdigest()
            return {
                "status": "leased",
                "job_id": job.job_id,
                "operation": job.operation,
                "payload": dict(job.payload),
                "lease_token": lease,
                "lease_seconds": LEASE_SECONDS,
                "attempts": job.attempts,
            }

    def complete(
        self, node_id: str, node_token: str,
        *, job_id: str, lease_token: str, result: Any,
    ) -> dict[str, Any]:
        instance_id = self.mesh.authorize_node(
            node_id, node_token, required_surface="compute.light",
        )
        with self._lock:
            self._purge()
            job = self._jobs.get(job_id)
            if (
                not job or job.instance_id != instance_id
                or job.status != "leased" or job.assigned_node != node_id
                or job.lease_until is None or self.clock() >= job.lease_until
                or not isinstance(lease_token, str)
                or not job.lease_digest
                or not hmac.compare_digest(
                    sha256(lease_token.encode("utf-8")).hexdigest(),
                    job.lease_digest,
                )
            ):
                raise PermissionError("Entrega de tarefa nao autorizada ou fora do prazo.")
            try:
                encoded = json.dumps(
                    result, ensure_ascii=False, allow_nan=False,
                ).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ValueError("Resultado nao serializavel.") from exc
            if len(encoded) > MAX_RESULT_BYTES:
                raise ValueError("Resultado excede limite.")
            job.status = "completed"
            job.result = result
            job.lease_digest = None
            job.lease_until = None
            return {"status": "completed", "job_id": job_id, "verified": False}

    def inspect(
        self, instance_id: str, instance_token: str, *, job_id: str,
    ) -> dict[str, Any]:
        self.mesh.authority.require(instance_id, instance_token, "device.local")
        with self._lock:
            self._purge()
            job = self._jobs.get(job_id)
            if not job or job.instance_id != instance_id:
                raise PermissionError("Tarefa de outra instancia ou inexistente.")
            return {
                "job_id": job_id, "status": job.status,
                "result": job.result if job.status == "completed" else None,
                "attempts": job.attempts,
                "verified": False,
            }
