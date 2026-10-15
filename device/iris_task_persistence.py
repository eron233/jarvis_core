"""Broker Iris com fila criptografada duravel entre reinicios do coordenador.

Uma unica instancia escritora por arquivo; recarrega leases abandonados como
queued para processar novamente. Entrega e *at-least-once*, NAO exactly-once.
Sem consenso, replicacao por rede ou garantias de disponibilidade sem servidor.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import os
import secrets
import tempfile
import time
from typing import Callable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from device.iris_task_broker import (
    BrokerJob, IrisTaskBroker, validate_operation, TASK_TTL_SECONDS, MAX_TASKS_TOTAL,
)
from device.iris_mesh import IrisDeviceMesh


class BrokerStoreIntegrityError(Exception):
    pass


class PersistentIrisTaskBroker(IrisTaskBroker):
    _AAD = b"iris-task-broker-v1"

    def __init__(
        self, mesh: IrisDeviceMesh, path: Path, *,
        storage_key: bytes, clock: Callable[[], float] = time.time,
    ) -> None:
        if type(storage_key) is not bytes or len(storage_key) != 32:
            raise ValueError("A chave da fila cifrada precisa ter 32 bytes.")
        self.path = Path(path)
        self._storage_key = storage_key
        super().__init__(mesh, clock=clock)
        if self.path.exists():
            self._load()

    def _cipher(self):
        return AESGCM(HKDF(
            algorithm=hashes.SHA256(), length=32,
            salt=b"iris-v1-broker-persistence",
            info=b"task-queue-sealed",
        ).derive(self._storage_key))

    def _save(self) -> None:
        with self._lock:
            jobs = [asdict(job) for job in self._jobs.values()]
            raw = json.dumps(
                {"schema_version": 1, "jobs": jobs}, sort_keys=True,
                ensure_ascii=False, separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
            if len(raw) > 8 * 1024 * 1024:
                raise ValueError("Fila de tarefas excedeu tamanho maximo.")
            nonce = secrets.token_bytes(12)
            ciphertext = b"IRISJOB1" + nonce + self._cipher().encrypt(
                nonce, raw, self._AAD,
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix=".iris-jobs-", suffix=".tmp",
                                        dir=str(self.path.parent))
            try:
                if os.name != "nt":
                    os.fchmod(fd, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(ciphertext)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp, self.path)
            finally:
                if os.path.exists(temp):
                    os.unlink(temp)

    def _load(self) -> None:
        data = self.path.read_bytes()
        if len(data) < 38 or not data.startswith(b"IRISJOB1"):
            raise BrokerStoreIntegrityError("Fila Iris invalida.")
        try:
            raw = self._cipher().decrypt(
                data[8:20], data[20:], self._AAD,
            )
            payload = json.loads(raw.decode("utf-8"))
            if payload["schema_version"] != 1:
                raise ValueError("Versao de fila nao suportada.")
            records = payload["jobs"]
            if not isinstance(records, list) or len(records) > MAX_TASKS_TOTAL:
                raise ValueError("Quantidade de tarefas invalida.")
            restored: dict[str, BrokerJob] = {}
            for record in records:
                job = BrokerJob(**record)
                if (
                    job.job_id in restored or not job.job_id.startswith("iris-job-")
                    or job.status not in {"queued", "leased", "completed"}
                    or type(job.created) not in (int, float)
                    or job.created > self.clock() + 120
                    or type(job.attempts) is not int or job.attempts < 0
                ):
                    raise ValueError("Registro de tarefa invalido.")
                validate_operation(job.operation, job.payload)
                if self.clock() - job.created > TASK_TTL_SECONDS:
                    continue
                if job.status == "leased":
                    # Uma lease anterior nao e assumida valida apos restart.
                    job.status = "queued"
                    job.assigned_node = None
                    job.lease_digest = None
                    job.lease_until = None
                restored[job.job_id] = job
            with self._lock:
                self._jobs = restored
        except (InvalidTag, ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
            raise BrokerStoreIntegrityError("Fila Iris adulterada ou incompativel.") from exc

    def submit(self, *args, **kwargs):
        response = super().submit(*args, **kwargs)
        if response.get("submitted"):
            self._save()
        return response

    def claim(self, *args, **kwargs):
        response = super().claim(*args, **kwargs)
        if response.get("status") == "leased":
            self._save()
        return response

    def complete(self, *args, **kwargs):
        response = super().complete(*args, **kwargs)
        self._save()
        return response
