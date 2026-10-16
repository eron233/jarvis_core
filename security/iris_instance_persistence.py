"""Persistencia cifrada da identidade das instancias Iris (um processo).

Nao exposita HTTP. Chave de 32 bytes de um KMS/secret externo; nenhuma
chave administrativa, token em claro ou conversa e gravado no disco.
A camada transacional multi-processo e a rotacao de chaves ficam pendentes.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import os
import secrets
import tempfile
from typing import Callable
import time

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from security.iris_instance_policy import (
    IrisInstance, IrisInstanceAuthority, _COMMON, _OWNER_ONLY, _DELEGATABLE,
)


class IdentityStoreIntegrityError(Exception):
    pass


class PersistentIrisInstanceAuthority(IrisInstanceAuthority):
    """Store sealed em disco; compatibilidade com API opcional de instancia.

    Uso seguro: apenas um processo escreve um arquivo. Para um deployment SaaS
    multi-worker sera necessario banco transacional central e controle de versao.
    """

    _AAD = b"iris-identity-snapshot:v1"
    _MAX_BYTES = 512 * 1024

    def __init__(
        self, owner_token: str, storage_path: Path, *,
        storage_key: bytes, clock: Callable[[], float] = time.time,
    ) -> None:
        if type(storage_key) is not bytes or len(storage_key) != 32:
            raise ValueError("Chave de persistencia precisa ter 32 bytes.")
        self.storage_path = Path(storage_path)
        self._storage_key = storage_key
        self._loading = True
        super().__init__(owner_token, clock=clock)
        self._migration_required = False
        if self.storage_path.is_file():
            self._load(owner_token)
        self._loading = False
        if not self.storage_path.is_file() or self._migration_required:
            # Persistir imediatamente a remocao das capacidades legadas.
            self._save()

    def _cipher(self) -> AESGCM:
        key = HKDF(
            algorithm=hashes.SHA256(), length=32,
            salt=b"iris-v1-identity-persistence",
            info=b"identity-sealed-store",
        ).derive(self._storage_key)
        return AESGCM(key)

    def _save(self) -> None:
        if getattr(self, "_loading", False):
            return
        with self._lock:
            payload = {
                "schema_version": 1,
                "instances": [
                    {**asdict(x), "capabilities": sorted(x.capabilities)}
                    for x in self._records.values()
                ],
                "digests": dict(self._token_digests),
                "revoked": sorted(self._revoked),
                "feedback_sources": {
                    k: sorted(v) for k, v in self._feedback_sources.items()
                },
            }
            raw = json.dumps(
                payload, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
            if len(raw) > self._MAX_BYTES:
                raise ValueError("Limite do snapshot da autoridade excedido.")
            nonce = secrets.token_bytes(12)
            sealed = b"IRISID1" + nonce + self._cipher().encrypt(nonce, raw, self._AAD)
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(
                prefix=".iris-auth-", suffix=".tmp", dir=str(self.storage_path.parent)
            )
            try:
                if os.name != "nt":
                    os.fchmod(fd, 0o600)
                with os.fdopen(fd, "wb") as handle:
                    handle.write(sealed)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self.storage_path)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

    def _load(self, owner_token: str) -> None:
        sealed = self.storage_path.read_bytes()
        if len(sealed) < 35 or not sealed.startswith(b"IRISID1"):
            raise IdentityStoreIntegrityError("Snapshot da autoridade invalido.")
        try:
            nonce = sealed[7:19]
            raw = self._cipher().decrypt(nonce, sealed[19:], self._AAD)
            data = json.loads(raw.decode("utf-8"))
            if not isinstance(data, dict) or data.get("schema_version") != 1:
                raise ValueError("Schema inesperado.")
            rows = data["instances"]
            digests = data["digests"]
            revoked = data["revoked"]
            feedback_sources = data["feedback_sources"]
            if not isinstance(rows, list) or not 1 <= len(rows) <= 5000:
                raise ValueError("Quantidade de instancias invalida.")
            if not isinstance(digests, dict) or not isinstance(revoked, list):
                raise ValueError("Indices invalidos.")
            restored = {}
            for row in rows:
                role = row["role"]
                if role not in {"original", "resident", "delegate"}:
                    raise ValueError("Papel desconhecido.")
                existing = frozenset(row["capabilities"])
                legacy_device = frozenset({"device.local"})
                if role == "original":
                    if existing != _COMMON | _OWNER_ONLY:
                        raise ValueError("Original com capacidades invalidas.")
                    normalized = existing
                elif role == "resident":
                    if existing not in (_COMMON, _COMMON | legacy_device):
                        raise ValueError("Residente com capacidades inesperadas.")
                    normalized = _COMMON
                else:
                    if not existing <= (_DELEGATABLE | legacy_device):
                        raise ValueError("Delegada ultrapassou suas capacidades.")
                    normalized = existing - legacy_device
                    if not normalized:
                        raise ValueError("Delegada sem capacidades remanescentes.")
                if normalized != existing:
                    self._migration_required = True
                row = dict(row)
                row["capabilities"] = normalized
                item = IrisInstance(**row)
                if item.instance_id in restored:
                    raise ValueError("ID duplicado.")
                if role == "original" and item.instance_id != self.OWNER_ID:
                    raise ValueError("Original invalida.")
                if role == "delegate" and item.parent_id is None:
                    raise ValueError("Delegada sem pai.")
                if role != "delegate" and item.parent_id is not None:
                    raise ValueError("Pai indevido.")
                restored[item.instance_id] = item
            if set(restored) != set(digests):
                raise ValueError("Credenciais inconsistentes.")
            if self.OWNER_ID not in restored or restored[self.OWNER_ID].role != "original":
                raise ValueError("Original ausente.")
            if digests[self.OWNER_ID] != self._digest(owner_token):
                raise PermissionError("Segredo da Original diverge do store persistido.")
            for item in restored.values():
                if item.role == "delegate":
                    parent = restored.get(item.parent_id)
                    if parent is None or parent.tenant_id != item.tenant_id:
                        raise ValueError("Delegacao inconsistente.")
            for item in revoked:
                if item not in restored or item == self.OWNER_ID:
                    raise ValueError("Revogacao invalida.")
            if not isinstance(feedback_sources, dict):
                raise ValueError("Feedback invalido.")
            self._records = restored
            self._token_digests = dict(digests)
            self._revoked = set(revoked)
            self._feedback_sources = {
                name: set(ids) for name, ids in feedback_sources.items()
            }
        except PermissionError:
            raise
        except (InvalidTag, ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
            raise IdentityStoreIntegrityError("Falha de integridade da identidade Iris.") from exc

    def create_resident(self, *args, **kwargs):
        result = super().create_resident(*args, **kwargs)
        self._save()
        return result

    def delegate(self, *args, **kwargs):
        result = super().delegate(*args, **kwargs)
        self._save()
        return result

    def set_resident_preferences(self, *args, **kwargs):
        result = super().set_resident_preferences(*args, **kwargs)
        self._save()
        return result

    def revoke(self, *args, **kwargs):
        result = super().revoke(*args, **kwargs)
        self._save()
        return result

    def report_feedback(self, *args, **kwargs):
        result = super().report_feedback(*args, **kwargs)
        if result:
            self._save()
        return result
