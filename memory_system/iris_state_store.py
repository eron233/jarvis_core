"""Estado duravel e criptografado por instancia da Iris.

SQLite WAL + AES-256-GCM com chave derivada por identidade (HKDF). A leitura
depende de credencial individual da instancia e de capacidade memory.own.
Nao armazena tokens nem texto em claro. Isto NAO realiza replicacao P2P,
sincronizacao offline, quorum, eleicao ou failover entre processos.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import secrets
import sqlite3
from threading import RLock
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes

from security.iris_instance_policy import IrisInstanceAuthority

_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$")
_MAX_DOCUMENT_BYTES = 65536
_MAX_KEYS_PER_INSTANCE = 512


class StateConflictError(Exception):
    """Versao esperada diferente da versao persistida."""


class StateCorruptionError(Exception):
    """Autenticacao criptografica do registro falhou."""


class IrisEncryptedStateStore:
    """Armazenamento por instancia, ativado explicitamente pelo servidor.

    O arquivo SQLite pode sobreviver reinicios, mas deve residir em um volume
    privado com backup; a chave AES root de 32 bytes deve vir de KMS/secret
    externo ao Git. Perder a chave implica perder o conteudo cifrado.
    """

    def __init__(
        self, path: Path, authority: IrisInstanceAuthority,
        *, root_key: bytes,
    ) -> None:
        if type(root_key) is not bytes or len(root_key) != 32:
            raise ValueError("Chave mestra do store Iris precisa ter 32 bytes aleatorios.")
        self.authority = authority
        self._root_key = root_key
        self.path = Path(path)
        if self.path == Path(":memory:"):
            # Nome literal, diferentemente de um arquivo num volume local.
            db_path = ":memory:"
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            db_path = str(self.path)
        self._lock = RLock()
        self._db = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        self._db.execute("PRAGMA busy_timeout=10000")
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS iris_instance_state (
                instance_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                revision INTEGER NOT NULL CHECK (revision > 0),
                nonce BLOB NOT NULL,
                ciphertext BLOB NOT NULL,
                PRIMARY KEY (instance_id, document_id)
            )
        """)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    @staticmethod
    def _valid_key(document_id: str) -> None:
        if not isinstance(document_id, str) or not _KEY_PATTERN.fullmatch(document_id):
            raise ValueError("ID de documento invalido.")

    def _cipher(self, instance_id: str) -> AESGCM:
        key = HKDF(
            algorithm=hashes.SHA256(), length=32,
            salt=b"iris-state-store-v1",
            info=instance_id.encode("utf-8"),
        ).derive(self._root_key)
        return AESGCM(key)

    @staticmethod
    def _aad(instance_id: str, document_id: str, revision: int) -> bytes:
        return f"iris-v1:{instance_id}:{document_id}:{revision}".encode("utf-8")

    def _authorize(self, instance_id: str, token: str) -> None:
        # Delegadas com memory.own tem identidade distinta; nao herdam
        # leitura da memoria da Original/Residente sem uma concessao explicita.
        self.authority.require(instance_id, token, "memory.own")

    def _get_row(self, instance_id: str, document_id: str):
        return self._db.execute(
            "SELECT revision, nonce, ciphertext FROM iris_instance_state "
            "WHERE instance_id = ? AND document_id = ?",
            (instance_id, document_id),
        ).fetchone()

    def _decrypt(self, instance_id: str, document_id: str, row) -> Any:
        revision, nonce, ciphertext = row
        try:
            plaintext = self._cipher(instance_id).decrypt(
                nonce, ciphertext, self._aad(instance_id, document_id, revision)
            )
        except (InvalidTag, ValueError) as exc:
            raise StateCorruptionError("Registro indisponivel: integridade invalida.") from exc
        try:
            return json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise StateCorruptionError("Registro cifrado contem JSON invalido.") from exc

    def get(self, instance_id: str, token: str, document_id: str) -> dict[str, Any]:
        self._valid_key(document_id)
        with self._lock:
            self._authorize(instance_id, token)
            row = self._get_row(instance_id, document_id)
            if row is None:
                return {"found": False, "revision": 0, "value": None}
            return {
                "found": True, "revision": row[0],
                "value": self._decrypt(instance_id, document_id, row),
            }

    def put(
        self,
        instance_id: str,
        token: str,
        document_id: str,
        value: Any,
        *,
        expected_revision: int,
        fence_node_id: str | None = None,
        fence_epoch: int | None = None,
    ) -> dict[str, Any]:
        """Gravacao CAS: exige versao, nao sobrescreve concorrencia silenciosa."""
        self._valid_key(document_id)
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision precisa ser inteiro >= 0.")
        try:
            raw = json.dumps(
                value, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Documento nao serializavel como JSON seguro.") from exc
        if len(raw) > _MAX_DOCUMENT_BYTES:
            raise ValueError("Documento maior que o limite de 64 KiB.")

        with self._lock:
            self._authorize(instance_id, token)
            self._db.execute("BEGIN IMMEDIATE")
            try:
                # A criacao de um lease para esta instancia ativa fencing
                # permanentemente, inclusive apos reiniciar processos.
                has_leases = self._db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='iris_writer_leases'"
                ).fetchone() is not None
                if has_leases:
                    lease = self._db.execute(
                        "SELECT node_id, epoch, lease_until FROM iris_writer_leases "
                        "WHERE instance_id=?",
                        (instance_id,),
                    ).fetchone()
                    if lease is not None:
                        now = self._db.execute(
                            "SELECT (julianday('now') - 2440587.5) * 86400"
                        ).fetchone()[0]
                        if (
                            type(fence_epoch) is not int
                            or not isinstance(fence_node_id, str)
                            or lease[0] != fence_node_id
                            or lease[1] != fence_epoch
                            or lease[2] <= now
                        ):
                            raise PermissionError("Escrita sem lease e epoch valido.")
                row = self._get_row(instance_id, document_id)
                revision = row[0] if row else 0
                if revision != expected_revision:
                    raise StateConflictError("Conflito de revisao: atualize antes de gravar.")
                if not row:
                    count = self._db.execute(
                        "SELECT COUNT(*) FROM iris_instance_state WHERE instance_id=?",
                        (instance_id,),
                    ).fetchone()[0]
                    if count >= _MAX_KEYS_PER_INSTANCE:
                        raise ValueError("Limite de documentos por instancia atingido.")
                new_revision = revision + 1
                nonce = secrets.token_bytes(12)
                ciphertext = self._cipher(instance_id).encrypt(
                    nonce, raw, self._aad(instance_id, document_id, new_revision),
                )
                self._db.execute(
                    "INSERT INTO iris_instance_state (instance_id, document_id, revision, nonce, ciphertext) "
                    "VALUES (?, ?, ?, ?, ?) ON CONFLICT(instance_id, document_id) DO UPDATE "
                    "SET revision=excluded.revision, nonce=excluded.nonce, ciphertext=excluded.ciphertext",
                    (instance_id, document_id, new_revision, nonce, ciphertext),
                )
                self._db.commit()
                return {"revision": new_revision, "written": True}
            except BaseException:
                self._db.rollback()
                raise

    def document_revisions(self, instance_id: str, token: str) -> list[dict[str, Any]]:
        """Lista metadados apenas da propria instancia, nunca conteudo."""
        with self._lock:
            self._authorize(instance_id, token)
            rows = self._db.execute(
                "SELECT document_id, revision FROM iris_instance_state "
                "WHERE instance_id=? ORDER BY document_id LIMIT ?",
                (instance_id, _MAX_KEYS_PER_INSTANCE),
            ).fetchall()
            return [{"document_id": name, "revision": version} for name, version in rows]

    def backup(self, destination: Path) -> None:
        """Snapshot SQLite consistente; o backup permanece cifrado.

        Exige acao local do operador. Nao e endpoint HTTP nem replica real.
        """
        target = Path(destination)
        if target.resolve() == self.path.resolve():
            raise ValueError("Origem e destino do backup nao podem coincidir.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with sqlite3.connect(str(target), timeout=10) as backup_db:
                self._db.backup(backup_db)
