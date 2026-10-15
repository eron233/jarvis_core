"""Registro cifrado de dispositivos pareados para reatach apos reiniciar a Iris.

Persistencia single-process de metadados e hashes de tokens. Ao restaurar,
TODOS os leases sao considerados offline ate novo heartbeat autenticado.
Nenhum dispositivo e descoberto, instalado, ligado ou controlado por isso.
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

from device.iris_mesh import (
    IrisDeviceMesh, MeshDevice, _DEVICE_ID_RE, _DEVICE_TYPES, _SURFACES, _BRIDGE,
    _UI_ONLY, _NATIVE,
)
from security.iris_instance_policy import IrisInstanceAuthority


class MeshStoreIntegrityError(Exception):
    pass


class PersistentIrisDeviceMesh(IrisDeviceMesh):
    """Armazena somente inventario privado; ofertas temporarias sao volatil."""

    _AAD = b"iris-mesh-registry:v1"

    def __init__(
        self, authority: IrisInstanceAuthority, path: Path, *,
        storage_key: bytes, clock: Callable[[], float] = time.time,
    ) -> None:
        if type(storage_key) is not bytes or len(storage_key) != 32:
            raise ValueError("Chave do inventario precisa ter 32 bytes.")
        self.path = Path(path)
        self._storage_key = storage_key
        super().__init__(authority, clock=clock)
        if self.path.is_file():
            self._load()

    def _cipher(self) -> AESGCM:
        return AESGCM(HKDF(
            algorithm=hashes.SHA256(), length=32,
            salt=b"iris-v1-mesh-registry",
            info=b"paired-device-inventory",
        ).derive(self._storage_key))

    def _save(self) -> None:
        with self._lock:
            rows = []
            for d in self._devices.values():
                item = asdict(d)
                item["surfaces"] = sorted(d.surfaces)
                rows.append(item)
            payload = {"schema_version": 1, "devices": rows}
            raw = json.dumps(
                payload, sort_keys=True, separators=(",", ":"),
                ensure_ascii=False, allow_nan=False,
            ).encode("utf-8")
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError("Inventario excedeu limite suportado.")
            nonce = secrets.token_bytes(12)
            encrypted = b"IRISMESH1" + nonce + self._cipher().encrypt(nonce, raw, self._AAD)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temp_path = tempfile.mkstemp(
                prefix=".iris-mesh-", suffix=".tmp", dir=str(self.path.parent)
            )
            try:
                if os.name != "nt":
                    os.fchmod(fd, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(encrypted)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temp_path, self.path)
            finally:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)

    def _load(self) -> None:
        sealed = self.path.read_bytes()
        if len(sealed) < 38 or not sealed.startswith(b"IRISMESH1"):
            raise MeshStoreIntegrityError("Inventario Iris invalido.")
        try:
            nonce = sealed[9:21]
            data = json.loads(
                self._cipher().decrypt(nonce, sealed[21:], self._AAD).decode("utf-8")
            )
            if not isinstance(data, dict) or data.get("schema_version") != 1:
                raise ValueError("Schema inesperado.")
            rows = data["devices"]
            if not isinstance(rows, list) or len(rows) > 5000:
                raise ValueError("Inventario incompativel.")
            restored = {}
            for row in rows:
                item = dict(row)
                item["surfaces"] = frozenset(item["surfaces"])
                node = MeshDevice(**item)
                if (not _DEVICE_ID_RE.fullmatch(node.node_id)
                    or node.node_id in restored
                    or node.device_type not in _DEVICE_TYPES
                    or node.mode not in {"integrated", "visit"}
                    or not self._allowed_surfaces(node.device_type, node.surfaces)
                    or node.execution_kind != self._execution_kind(node.device_type)
                    or len(node.token_digest) != 64
                    or not isinstance(node.instance_id, str)
                    or not isinstance(node.display_name, str)):
                    raise ValueError("Registro de no invalido.")
                # Reinicio nao significa que o dispositivo segue conectado.
                node.last_seen_at = float("-inf")
                restored[node.node_id] = node
            with self._lock:
                self._devices = restored
        except (InvalidTag, ValueError, TypeError, KeyError, UnicodeDecodeError) as exc:
            raise MeshStoreIntegrityError("Integridade do inventario Iris falhou.") from exc

    def approve_offer(self, *args, **kwargs):
        joined = super().approve_offer(*args, **kwargs)
        self._save()
        return joined

    def disconnect(self, *args, **kwargs):
        result = super().disconnect(*args, **kwargs)
        self._save()
        return result
