"""Eleicao com fencing de escrita em SQLite no MESMO host/volume.

Leases transacionais usam relogio do proprio SQLite e bloqueio BEGIN IMMEDIATE.
A epoca e conferida no MESMO commit do estado via IrisEncryptedStateStore.put.
Nao usar SQLite sobre NFS/SMB como coordenador distribuido: sem quorum entre
computadores, isolamento de particoes e consenso contra split-brain.
"""
from __future__ import annotations

from typing import Any

from device.iris_mesh import IrisDeviceMesh
from memory_system.iris_state_store import IrisEncryptedStateStore


class IrisLeaseCoordinator:
    """Prototipo de failover entre processos que compartilham o mesmo SQLite."""

    def __init__(
        self, mesh: IrisDeviceMesh, store: IrisEncryptedStateStore,
    ) -> None:
        if mesh.authority is not store.authority:
            raise ValueError("Autoridades de estado e malha diferentes.")
        if store.path.name == ":memory:":
            raise ValueError("Lease exige banco em disco persistente.")
        self.mesh, self.store = mesh, store
        with self.store._lock:
            self.store._db.execute("""
                CREATE TABLE IF NOT EXISTS iris_writer_leases (
                    instance_id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL,
                    epoch INTEGER NOT NULL CHECK (epoch >= 1),
                    lease_until REAL NOT NULL
                )
            """)
            self.store._db.commit()

    @staticmethod
    def _db_now(db) -> float:
        return db.execute(
            "SELECT (julianday('now') - 2440587.5) * 86400"
        ).fetchone()[0]

    def acquire(
        self, node_id: str, node_token: str, *,
        ttl_seconds: float = 10.0,
    ) -> dict[str, Any]:
        if type(ttl_seconds) not in (int, float) or not 1 <= ttl_seconds <= 300:
            raise ValueError("TTL precisa estar entre 1 e 300 segundos.")
        instance_id = self.mesh.authorize_node(
            node_id, node_token, required_surface="compute.light",
        )
        with self.store._lock:
            db = self.store._db
            db.execute("BEGIN IMMEDIATE")
            try:
                now = self._db_now(db)
                record = db.execute(
                    "SELECT node_id, epoch, lease_until FROM iris_writer_leases "
                    "WHERE instance_id=?", (instance_id,),
                ).fetchone()
                if record and record[2] > now and record[0] != node_id:
                    db.rollback()
                    return {
                        "acquired": False, "instance_id": instance_id,
                        "holder_node_id": record[0], "epoch": record[1],
                    }
                # A mesma instancia so incrementa epoca apos nova aquisicao,
                # nao ao renovar lease ainda valido de seu proprio no.
                if record is None:
                    epoch = 1
                elif record[0] == node_id and record[2] > now:
                    epoch = record[1]
                else:
                    epoch = record[1] + 1
                deadline = now + float(ttl_seconds)
                db.execute(
                    "INSERT INTO iris_writer_leases "
                    "(instance_id,node_id,epoch,lease_until) VALUES(?,?,?,?) "
                    "ON CONFLICT(instance_id) DO UPDATE SET node_id=excluded.node_id,"
                    "epoch=excluded.epoch,lease_until=excluded.lease_until",
                    (instance_id, node_id, epoch, deadline),
                )
                db.commit()
                return {
                    "acquired": True, "instance_id": instance_id,
                    "holder_node_id": node_id, "epoch": epoch,
                    "lease_until": deadline,
                }
            except BaseException:
                db.rollback()
                raise

    def renew(
        self, node_id: str, node_token: str, *,
        epoch: int, ttl_seconds: float = 10.0,
    ) -> dict[str, Any]:
        if type(epoch) is not int or epoch < 1:
            raise ValueError("Epoca invalida.")
        if type(ttl_seconds) not in (int, float) or not 1 <= ttl_seconds <= 300:
            raise ValueError("TTL invalido.")
        instance_id = self.mesh.authorize_node(
            node_id, node_token, required_surface="compute.light",
        )
        with self.store._lock:
            db = self.store._db
            db.execute("BEGIN IMMEDIATE")
            try:
                now = self._db_now(db)
                row = db.execute(
                    "SELECT node_id,epoch,lease_until FROM iris_writer_leases "
                    "WHERE instance_id=?", (instance_id,),
                ).fetchone()
                if not row or row[0] != node_id or row[1] != epoch or row[2] <= now:
                    raise PermissionError("Lease perdida, expirou ou mudou de epoca.")
                deadline = now + float(ttl_seconds)
                db.execute(
                    "UPDATE iris_writer_leases SET lease_until=? WHERE instance_id=?",
                    (deadline, instance_id),
                )
                db.commit()
                return {"renewed": True, "epoch": epoch, "lease_until": deadline}
            except BaseException:
                db.rollback()
                raise

    def release(
        self, node_id: str, node_token: str, *,
        epoch: int,
    ) -> bool:
        if type(epoch) is not int or epoch < 1:
            raise ValueError("Epoca invalida.")
        instance_id = self.mesh.authorize_node(
            node_id, node_token, required_surface="compute.light",
        )
        with self.store._lock:
            db = self.store._db
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT node_id,epoch FROM iris_writer_leases "
                    "WHERE instance_id=?", (instance_id,),
                ).fetchone()
                if not row or row != (node_id, epoch):
                    raise PermissionError("Liberacao de epoca alheia.")
                db.execute(
                    "UPDATE iris_writer_leases SET lease_until=0 WHERE instance_id=?",
                    (instance_id,),
                )
                db.commit()
                return True
            except BaseException:
                db.rollback()
                raise

    def status(self, instance_id: str, token: str) -> dict[str, Any]:
        self.mesh.authority.require(instance_id, token, "device.local")
        with self.store._lock:
            row = self.store._db.execute(
                "SELECT node_id,epoch,lease_until FROM iris_writer_leases "
                "WHERE instance_id=?", (instance_id,),
            ).fetchone()
            now = self._db_now(self.store._db)
        if not row:
            return {"active": False, "epoch": 0, "holder_node_id": None}
        return {
            "active": row[2] > now, "epoch": row[1],
            "holder_node_id": row[0] if row[2] > now else None,
        }
