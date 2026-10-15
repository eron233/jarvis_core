"""Replicacao *pull* cifrada de documentos entre instalacoes autorizadas.

Origem so exporta memórias do mesmo usuario que possui o nó pareado, com
"memory.sync" e modo integrado. Transporte HTTPS (exceto loopback local),
sem execucao de comandos, instalacao remota ou acesso a terceiros.

Isto e uma replica read-only de um escritor primario: divergencias falham
fechadas, nao ha promocao automatica de um segundo escritor nem consenso.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import re
import secrets
from threading import Event, RLock
import time
from typing import Any, Callable
from urllib.parse import quote, urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import build_opener, HTTPRedirectHandler, Request

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from device.iris_mesh import IrisDeviceMesh
from memory_system.iris_state_store import (
    IrisEncryptedStateStore, StateConflictError, StateCorruptionError,
    _MAX_DOCUMENT_BYTES, _MAX_KEYS_PER_INSTANCE,
)

_SOURCE_PATTERN = re.compile(r"^iris-source-[a-zA-Z0-9_-]{8,64}$")
_NODE_PATTERN = re.compile(r"^iris-node-[a-f0-9]{32}$")
_MAX_ENVELOPE_BYTES = 128 * 1024


class IrisReplicaIntegrityError(Exception):
    """Conteudo adulterado ou de outra instancia/source."""


class IrisReplicaTransportError(Exception):
    """Origem inacessivel ou resposta de protocolo invalida."""


def _json_bytes(value: Any) -> bytes:
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("JSON de replicacao invalido.") from exc
    if len(raw) > _MAX_ENVELOPE_BYTES:
        raise ValueError("Dados excedem limite de replicacao.")
    return raw


def _derive_key(node_id: str, token: str) -> bytes:
    if not _NODE_PATTERN.fullmatch(node_id) or not isinstance(token, str) or len(token) < 32:
        raise PermissionError("Credencial do no invalida.")
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=b"iris-replication-v1",
        info=node_id.encode("ascii"),
    ).derive(token.encode("utf-8"))


def _seal(node_id: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    nonce = secrets.token_bytes(12)
    encoded = _json_bytes(payload)
    encrypted = AESGCM(_derive_key(node_id, token)).encrypt(
        nonce, encoded, b"iris-replication-document:v1:" + node_id.encode("ascii")
    )
    return {
        "format": "iris-replica-aead-v1",
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "ciphertext": base64.b64encode(encrypted).decode("ascii"),
    }


def _unseal(node_id: str, token: str, envelope: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(envelope, dict) or set(envelope) != {"format", "nonce", "ciphertext"}:
        raise IrisReplicaIntegrityError("Envelope com campos invalidos.")
    if envelope["format"] != "iris-replica-aead-v1":
        raise IrisReplicaIntegrityError("Versao criptografica desconhecida.")
    try:
        nonce = base64.b64decode(envelope["nonce"], validate=True)
        ciphertext = base64.b64decode(envelope["ciphertext"], validate=True)
        if len(nonce) != 12 or len(ciphertext) > _MAX_ENVELOPE_BYTES:
            raise ValueError("Payload extenso ou nonce invalido.")
        raw = AESGCM(_derive_key(node_id, token)).decrypt(
            nonce, ciphertext, b"iris-replication-document:v1:" + node_id.encode("ascii")
        )
        result = json.loads(raw.decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("Documento invalido.")
        return result
    except (ValueError, TypeError, KeyError, InvalidTag, UnicodeDecodeError) as exc:
        raise IrisReplicaIntegrityError("Falha na autenticacao do snapshot.") from exc


class IrisReplicaSource:
    """Origem de leitura isolada por identidade de dispositivo pareado."""

    def __init__(
        self, mesh: IrisDeviceMesh, store: IrisEncryptedStateStore, *,
        source_id: str,
    ) -> None:
        if not isinstance(source_id, str) or not _SOURCE_PATTERN.fullmatch(source_id):
            raise ValueError("Identificador persistente da origem invalido.")
        if mesh.authority is not store.authority:
            raise ValueError("Malha e memoria precisam da mesma autoridade.")
        self.mesh, self.store, self.source_id = mesh, store, source_id

    def _tenant(self, node_id: str, node_token: str) -> str:
        return self.mesh.authorize_node(
            node_id, node_token, required_surface="memory.sync",
        )

    def manifest(self, node_id: str, node_token: str) -> dict[str, Any]:
        instance = self._tenant(node_id, node_token)
        with self.store._lock:
            rows = self.store._db.execute(
                "SELECT document_id, revision FROM iris_instance_state "
                "WHERE instance_id=? ORDER BY document_id LIMIT ?",
                (instance, _MAX_KEYS_PER_INSTANCE),
            ).fetchall()
        return {
            "source_id": self.source_id, "instance_id": instance,
            "documents": [{"document_id": name, "revision": revision}
                          for name, revision in rows],
        }

    def document(
        self, node_id: str, node_token: str, document_id: str,
    ) -> dict[str, Any]:
        instance = self._tenant(node_id, node_token)
        self.store._valid_key(document_id)
        with self.store._lock:
            row = self.store._get_row(instance, document_id)
            if row is None:
                raise LookupError("Documento inexistente.")
            revision = row[0]
            value = self.store._decrypt(instance, document_id, row)
        return _seal(node_id, node_token, {
            "version": 1, "source_id": self.source_id,
            "instance_id": instance, "document_id": document_id,
            "revision": revision, "value": value,
        })


class IrisReplicaSink:
    """Aplica snapshots monotônicos em um armazenamento local de apenas-replica.

    Um checkpoint de digest HMAC detecta alteracoes locais desde a ultima
    sincronizacao. O modo de bootstrap nao substitui documentos divergentes.
    A autenticacao da origem ocorre no envelope AEAD por token de no.
    """

    def __init__(
        self, store: IrisEncryptedStateStore, *,
        node_id: str, node_token: str, instance_id: str, source_id: str,
    ) -> None:
        if not _SOURCE_PATTERN.fullmatch(source_id):
            raise ValueError("Identificador de origem invalido.")
        _derive_key(node_id, node_token)
        if not store.authority.is_active_internal(instance_id):
            raise PermissionError("Identidade destinataria inativa.")
        self.store, self.node_id, self.node_token = store, node_id, node_token
        self.instance_id, self.source_id = instance_id, source_id
        with self.store._lock:
            self.store._db.execute("""
                CREATE TABLE IF NOT EXISTS iris_replica_checkpoints (
                    instance_id TEXT NOT NULL,
                    document_id TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    revision INTEGER NOT NULL,
                    fingerprint BLOB NOT NULL,
                    PRIMARY KEY (instance_id, document_id)
                )
            """)
            self.store._db.commit()

    def _fingerprint(self, value: Any) -> bytes:
        return hmac.new(self.store._root_key, _json_bytes(value), hashlib.sha256).digest()

    def apply(self, envelope: dict[str, Any]) -> dict[str, Any]:
        data = _unseal(self.node_id, self.node_token, envelope)
        if set(data) != {
            "version", "source_id", "instance_id", "document_id", "revision", "value",
        } or data["version"] != 1:
            raise IrisReplicaIntegrityError("Contrato de documento invalido.")
        if data["source_id"] != self.source_id or data["instance_id"] != self.instance_id:
            raise IrisReplicaIntegrityError("Origem ou identidade diferente da autorizada.")
        doc_id, version, value = data["document_id"], data["revision"], data["value"]
        self.store._valid_key(doc_id)
        if type(version) is not int or version < 1 or version > 2**63 - 1:
            raise IrisReplicaIntegrityError("Versao do estado invalida.")
        if not self.store.authority.is_active_internal(self.instance_id):
            raise PermissionError("Instancia revogada ou expirada.")
        encoded = _json_bytes(value)
        if len(encoded) > _MAX_DOCUMENT_BYTES:
            raise ValueError("Estado replica maior que 64 KiB.")
        fingerprint = self._fingerprint(value)
        with self.store._lock:
            db = self.store._db
            db.execute("BEGIN IMMEDIATE")
            try:
                # NUNCA importar snapshot para o banco marcado como escritor
                # cercado por lease; isso contornaria o token de fencing.
                if db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' "
                    "AND name='iris_writer_leases'"
                ).fetchone() is not None:
                    if db.execute(
                        "SELECT 1 FROM iris_writer_leases WHERE instance_id=?",
                        (self.instance_id,),
                    ).fetchone() is not None:
                        raise PermissionError("Nao replicar sobre banco de escritor protegido.")
                row = self.store._get_row(self.instance_id, doc_id)
                checkpoint = db.execute(
                    "SELECT source_id, revision, fingerprint FROM iris_replica_checkpoints "
                    "WHERE instance_id=? AND document_id=?",
                    (self.instance_id, doc_id),
                ).fetchone()
                if checkpoint is not None:
                    if checkpoint[0] != self.source_id:
                        raise StateConflictError("Documento pertence a outra origem.")
                    if row is None or row[0] != checkpoint[1] or not hmac.compare_digest(
                        self._fingerprint(self.store._decrypt(self.instance_id, doc_id, row)),
                        checkpoint[2],
                    ):
                        raise StateConflictError("Replica alterada localmente: sem sobrescrita.")
                elif row is not None:
                    current = self.store._decrypt(self.instance_id, doc_id, row)
                    if row[0] != version or not hmac.compare_digest(
                        self._fingerprint(current), fingerprint
                    ):
                        raise StateConflictError("Bootstrap recusa estado preexistente divergente.")
                if row is not None:
                    if row[0] > version:
                        raise StateConflictError("Versao mais antiga nao substitui dado local.")
                    if row[0] == version:
                        if not hmac.compare_digest(self._fingerprint(
                            self.store._decrypt(self.instance_id, doc_id, row)
                        ), fingerprint):
                            raise StateConflictError("Conflito de escritas na mesma versao.")
                        if checkpoint is None:
                            db.execute(
                                "INSERT INTO iris_replica_checkpoints VALUES (?, ?, ?, ?, ?)",
                                (self.instance_id, doc_id, self.source_id, version, fingerprint),
                            )
                        db.commit()
                        return {"status": "unchanged", "revision": version}
                elif checkpoint is not None:
                    raise StateConflictError("Replica apagada sem reconciliacao.")
                if row is None:
                    count = db.execute(
                        "SELECT COUNT(*) FROM iris_instance_state WHERE instance_id=?",
                        (self.instance_id,),
                    ).fetchone()[0]
                    if count >= _MAX_KEYS_PER_INSTANCE:
                        raise ValueError("Limite de documentos da instancia atingido.")
                nonce = secrets.token_bytes(12)
                ciphertext = self.store._cipher(self.instance_id).encrypt(
                    nonce, json.dumps(
                        value, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
                    ).encode("utf-8"),
                    self.store._aad(self.instance_id, doc_id, version),
                )
                db.execute(
                    "INSERT INTO iris_instance_state "
                    "(instance_id,document_id,revision,nonce,ciphertext) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(instance_id,document_id) DO UPDATE SET "
                    "revision=excluded.revision,nonce=excluded.nonce,ciphertext=excluded.ciphertext",
                    (self.instance_id, doc_id, version, nonce, ciphertext),
                )
                db.execute(
                    "INSERT INTO iris_replica_checkpoints "
                    "(instance_id,document_id,source_id,revision,fingerprint) VALUES (?,?,?,?,?) "
                    "ON CONFLICT(instance_id,document_id) DO UPDATE SET "
                    "source_id=excluded.source_id,revision=excluded.revision,"
                    "fingerprint=excluded.fingerprint",
                    (self.instance_id, doc_id, self.source_id, version, fingerprint),
                )
                db.commit()
                return {"status": "applied", "revision": version}
            except BaseException:
                db.rollback()
                raise


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class IrisReplicaPullClient:
    """Cliente HTTPS com consulta periodica e divergencia tratada como erro."""

    def __init__(
        self, endpoint: str, sink: IrisReplicaSink, *,
        transport: Callable[[str, dict[str, str]], dict[str, Any]] | None = None,
    ) -> None:
        url = urlsplit(endpoint)
        if url.scheme != "https" and not (
            url.scheme == "http" and url.hostname in {"localhost", "127.0.0.1", "::1"}
        ):
            raise ValueError("Replicacao remota exige HTTPS.")
        if not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
            raise ValueError("Endpoint de replicacao deve ser a raiz sem credenciais.")
        self.endpoint, self.sink = endpoint.rstrip("/"), sink
        self._transport = transport
        self._opener = build_opener(NoRedirect())
        self._lock = RLock()

    def _get(self, path: str) -> dict[str, Any]:
        headers = {"X-Iris-Node-Id": self.sink.node_id,
                   "X-Iris-Node-Token": self.sink.node_token}
        if self._transport is not None:
            value = self._transport(path, headers)
        else:
            request = Request(self.endpoint + path, headers=headers, method="GET")
            try:
                with self._opener.open(request, timeout=10) as response:
                    data = response.read(_MAX_ENVELOPE_BYTES + 1)
                if len(data) > _MAX_ENVELOPE_BYTES:
                    raise IrisReplicaTransportError("Resposta muito grande.")
                value = json.loads(data.decode("utf-8"))
            except (HTTPError, URLError, OSError, ValueError) as exc:
                raise IrisReplicaTransportError("Origem da replica indisponivel.") from exc
        if not isinstance(value, dict):
            raise IrisReplicaTransportError("Resposta inesperada de replicacao.")
        return value

    def sync_once(self) -> dict[str, int]:
        with self._lock:
            manifest = self._get("/api/iris/replication/manifest")
            if manifest.get("source_id") != self.sink.source_id:
                raise IrisReplicaIntegrityError("Fonte inesperada.")
            if manifest.get("instance_id") != self.sink.instance_id:
                raise IrisReplicaIntegrityError("Tentativa de replica de outro usuario.")
            docs = manifest.get("documents")
            if not isinstance(docs, list) or len(docs) > _MAX_KEYS_PER_INSTANCE:
                raise IrisReplicaIntegrityError("Manifesto invalido.")
            if len({d.get("document_id") for d in docs if isinstance(d, dict)}) != len(docs):
                raise IrisReplicaIntegrityError("Documento duplicado ou invalido no manifesto.")
            copied, unchanged = 0, 0
            for doc in docs:
                if not isinstance(doc, dict) or set(doc) != {"document_id", "revision"}:
                    raise IrisReplicaIntegrityError("Metadados invalidos.")
                self.sink.store._valid_key(doc["document_id"])
                if type(doc["revision"]) is not int or doc["revision"] < 1:
                    raise IrisReplicaIntegrityError("Versao invalida.")
                envelope = self._get(
                    "/api/iris/replication/documents/" + quote(doc["document_id"], safe="")
                )
                result = self.sink.apply(envelope)
                if result["status"] == "applied":
                    copied += 1
                else:
                    unchanged += 1
            return {"applied": copied, "unchanged": unchanged}

    def run_until(self, stop: Event, *, interval_seconds: float = 5.0) -> None:
        if not 1.0 <= interval_seconds <= 300.0:
            raise ValueError("Intervalo de replicacao fora do limite.")
        while not stop.is_set():
            self.sync_once()  # Falha na conexao/conflito encerra; nao ignora erro.
            stop.wait(interval_seconds)
