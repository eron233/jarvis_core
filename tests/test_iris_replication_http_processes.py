"""Replicacao real via loopback entre dois processos independentes.

Nao utiliza rede externa, nao pareia dispositivos fisicos, nao oferece quorum
ou failover do LLM. Executa transporte HTTP real e persiste dados em SQLite.
"""
from __future__ import annotations

import multiprocessing
import secrets
import socket
import tempfile
import time
import unittest
from pathlib import Path

from device.iris_mesh_persistence import PersistentIrisDeviceMesh
from device.iris_state_replication import (
    IrisReplicaSource, IrisReplicaSink, IrisReplicaPullClient,
    IrisReplicaTransportError,
)
from memory_system.iris_state_store import IrisEncryptedStateStore
from security.iris_instance_persistence import PersistentIrisInstanceAuthority


def _serve_origin(
    root: str, port: int, owner_token: str,
    identity_key: bytes, mesh_key: bytes, source_key: bytes,
    device_id: str, device_token: str,
) -> None:
    import uvicorn
    from interface.api.app import create_app
    from runtime.internal_agent_runtime import InternalAgentRuntime

    folder = Path(root)
    auth = PersistentIrisInstanceAuthority(
        owner_token, folder / "identity.sealed", storage_key=identity_key,
    )
    mesh = PersistentIrisDeviceMesh(
        auth, folder / "devices.sealed", storage_key=mesh_key,
    )
    mesh.heartbeat(device_id, device_token)
    state = IrisEncryptedStateStore(
        folder / "origin.sqlite3", auth, root_key=source_key,
    )
    source = IrisReplicaSource(
        mesh, state, source_id="iris-source-multiprocess-01",
    )
    app = create_app(
        runtime=InternalAgentRuntime(),
        api_token="integration-test-legacy-api-only",
        trusted_device_id="integration-test-local",
        iris_instance_authority=auth, iris_device_mesh=mesh,
        iris_state_store=state, iris_replica_source=source,
    )
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="critical",
                access_log=False)


class IrisHttpProcessReplicationTests(unittest.TestCase):
    def test_dois_processos_reiniciam_e_sincronizam(self):
        ctx = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            owner_token = secrets.token_urlsafe(32)
            identity_key = secrets.token_bytes(32)
            mesh_key = secrets.token_bytes(32)
            source_key = secrets.token_bytes(32)
            dest_key = secrets.token_bytes(32)
            auth = PersistentIrisInstanceAuthority(
                owner_token, root / "identity.sealed", storage_key=identity_key,
            )
            alice = {"instance_id": auth.OWNER_ID, "token": owner_token}
            mesh = PersistentIrisDeviceMesh(
                auth, root / "devices.sealed", storage_key=mesh_key,
            )
            offer = mesh.offer_device(
                device_name="Segundo computador local", device_type="linux",
                surfaces={"memory.sync", "compute.light"},
                locally_approved=True,
            )
            node = mesh.approve_offer(
                alice["instance_id"], alice["token"],
                offer_id=offer["offer_id"],
                verification_code=offer["verification_code"],
            )
            source = IrisEncryptedStateStore(
                root / "origin.sqlite3", auth, root_key=source_key,
            )
            try:
                source.put(
                    alice["instance_id"], alice["token"], "continuity",
                    {"message": "contexto sobrevivente", "stage": 1},
                    expected_revision=0,
                )
            finally:
                source.close()
            dest = IrisEncryptedStateStore(
                root / "destination.sqlite3", auth, root_key=dest_key,
            )
            sink = IrisReplicaSink(
                dest, node_id=node["node_id"],
                node_token=node["node_token"],
                instance_id=alice["instance_id"],
                source_id="iris-source-multiprocess-01",
            )
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            args = (
                str(root), port, owner_token, identity_key, mesh_key,
                source_key, node["node_id"], node["node_token"],
            )

            def start():
                process = ctx.Process(target=_serve_origin, args=args)
                process.start()
                return process

            def stop(process):
                if process is None:
                    return
                process.terminate()
                process.join(timeout=8)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=8)

            process = None
            try:
                replicator = IrisReplicaPullClient(
                    f"http://127.0.0.1:{port}", sink,
                )
                process = start()
                for attempt in range(75):
                    try:
                        result = replicator.sync_once()
                        break
                    except IrisReplicaTransportError:
                        if not process.is_alive():
                            self.fail("O processo de origem terminou antes do handshake.")
                        time.sleep(.1)
                else:
                    self.fail("A origem nao iniciou a replicacao no loopback.")
                self.assertEqual(result["applied"], 1)
                self.assertEqual(dest.get(
                    alice["instance_id"], alice["token"], "continuity",
                )["value"]["message"], "contexto sobrevivente")

                stop(process)
                process = None
                with self.assertRaises(IrisReplicaTransportError):
                    replicator.sync_once()

                # A replica continua consultavel sem a origem em execucao.
                self.assertEqual(dest.get(
                    alice["instance_id"], alice["token"], "continuity",
                )["revision"], 1)
                second_writer = IrisEncryptedStateStore(
                    root / "origin.sqlite3", auth, root_key=source_key,
                )
                try:
                    second_writer.put(
                        alice["instance_id"], alice["token"], "continuity",
                        {"message": "continuou", "stage": 2},
                        expected_revision=1,
                    )
                finally:
                    second_writer.close()

                process = start()
                for attempt in range(75):
                    try:
                        newer = replicator.sync_once()
                        break
                    except IrisReplicaTransportError:
                        if not process.is_alive():
                            self.fail("Origem nao reiniciou.")
                        time.sleep(.1)
                else:
                    self.fail("Origem nao retornou no loopback.")
                self.assertEqual(newer["applied"], 1)
                self.assertEqual(dest.get(
                    alice["instance_id"], alice["token"], "continuity",
                )["value"]["stage"], 2)
            finally:
                stop(process)
                dest.close()


if __name__ == "__main__":
    unittest.main()
