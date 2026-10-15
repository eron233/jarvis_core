"""Replicacao automatizavel da Iris: identidade, AEAD, versionamento e forks."""
import secrets
import tempfile
from pathlib import Path
import unittest
from threading import Event

from device.iris_mesh import IrisDeviceMesh
from device.iris_state_replication import (
    IrisReplicaSource, IrisReplicaSink, IrisReplicaPullClient,
    IrisReplicaIntegrityError, IrisReplicaTransportError, _seal,
)
from memory_system.iris_state_store import IrisEncryptedStateStore, StateConflictError
from security.iris_instance_policy import IrisInstanceAuthority


class IrisStateReplicationTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        self.secret = secrets.token_urlsafe(32)
        self.now = 2_000_000_000.0
        self.auth = IrisInstanceAuthority(self.secret, clock=lambda: self.now)
        self.mesh = IrisDeviceMesh(self.auth, clock=lambda: self.now)
        self.alice = self.auth.create_resident(
            self.secret, tenant_id="cliente-alice",
            display_name="Iris Alice", user_consented=True,
        )
        self.bob = self.auth.create_resident(
            self.secret, tenant_id="cliente-bob",
            display_name="Iris Bob", user_consented=True,
        )
        self.main = IrisEncryptedStateStore(
            self.root / "main.db", self.auth, root_key=secrets.token_bytes(32),
        )
        self.replica_key = secrets.token_bytes(32)
        self.replica = IrisEncryptedStateStore(
            self.root / "replica.db", self.auth, root_key=self.replica_key,
        )
        self.source_id = "iris-source-primary-001"
        self.source = IrisReplicaSource(self.mesh, self.main, source_id=self.source_id)
        self.node = self.pair(self.alice)
        self.sink = IrisReplicaSink(
            self.replica, node_id=self.node["node_id"],
            node_token=self.node["node_token"],
            instance_id=self.alice["instance_id"], source_id=self.source_id,
        )
        def transport(path, headers):
            node_id, token = headers["X-Iris-Node-Id"], headers["X-Iris-Node-Token"]
            if path == "/api/iris/replication/manifest":
                return self.source.manifest(node_id, token)
            prefix = "/api/iris/replication/documents/"
            if path.startswith(prefix):
                return self.source.document(node_id, token, path[len(prefix):])
            raise ValueError("Rota desconhecida")
        self.client = IrisReplicaPullClient("https://example.invalid", self.sink,
                                            transport=transport)

    def tearDown(self):
        self.main.close()
        self.replica.close()
        self.dir.cleanup()

    def pair(self, person, kind="windows", mode="integrated", surfaces=None):
        offer = self.mesh.offer_device(
            device_name="Dispositivo autorizado", device_type=kind,
            surfaces=surfaces or {"memory.sync", "compute.light"},
            mode=mode, locally_approved=True,
        )
        return self.mesh.approve_offer(
            person["instance_id"], person["token"],
            offer_id=offer["offer_id"], verification_code=offer["verification_code"],
        )

    def seed(self, document="historia", value=None):
        return self.main.put(
            self.alice["instance_id"], self.alice["token"], document,
            value if value is not None else {"memoria": "tudo bem"},
            expected_revision=0,
        )

    def test_replica_aead_entre_stores_criptografados_por_chaves_diferentes(self):
        self.seed(value={"memoria": "a nossa Iris lembra"})
        summary = self.client.sync_once()
        self.assertEqual(summary["applied"], 1)
        restored = self.replica.get(
            self.alice["instance_id"], self.alice["token"], "historia",
        )
        self.assertEqual(restored["value"], {"memoria": "a nossa Iris lembra"})
        self.assertEqual(restored["revision"], 1)
        self.assertEqual(self.client.sync_once(), {"applied": 0, "unchanged": 1})
        with self.replica._lock:
            raw = self.replica._db.execute(
                "SELECT ciphertext FROM iris_instance_state"
            ).fetchone()[0]
        self.assertNotIn(b"a nossa Iris lembra", raw)

    def test_duas_revisoes_avancam_sem_silenciar_conflito(self):
        self.seed()
        self.client.sync_once()
        self.main.put(
            self.alice["instance_id"], self.alice["token"], "historia",
            {"memoria": "revisada"}, expected_revision=1,
        )
        self.assertEqual(self.client.sync_once()["applied"], 1)
        self.assertEqual(self.replica.get(
            self.alice["instance_id"], self.alice["token"], "historia",
        )["revision"], 2)
        self.assertEqual(self.replica.get(
            self.alice["instance_id"], self.alice["token"], "historia",
        )["value"]["memoria"], "revisada")

    def test_bootstrap_apos_multiplas_revisoes_recupera_ultima_versao(self):
        self.seed()
        for version in (1, 2, 3):
            self.main.put(
                self.alice["instance_id"], self.alice["token"], "historia",
                {"revisao": version}, expected_revision=version,
            )
        self.client.sync_once()
        self.assertEqual(self.replica.get(
            self.alice["instance_id"], self.alice["token"], "historia",
        )["revision"], 4)

    def test_reinicio_recupera_checkpoint_e_rejeita_edicao_na_replica(self):
        self.seed()
        self.client.sync_once()
        self.replica.close()
        self.replica = IrisEncryptedStateStore(
            self.root / "replica.db", self.auth, root_key=self.replica_key,
        )
        self.sink = IrisReplicaSink(
            self.replica, node_id=self.node["node_id"],
            node_token=self.node["node_token"],
            instance_id=self.alice["instance_id"], source_id=self.source_id,
        )
        self.assertEqual(self.sink.apply(
            self.source.document(self.node["node_id"], self.node["node_token"], "historia")
        )["status"], "unchanged")
        self.replica.put(
            self.alice["instance_id"], self.alice["token"], "historia",
            {"modificacao": "na replica"}, expected_revision=1,
        )
        with self.assertRaises(StateConflictError):
            self.sink.apply(self.source.document(
                self.node["node_id"], self.node["node_token"], "historia",
            ))

    def test_duas_contas_sem_vazamento(self):
        self.seed()
        self.main.put(
            self.bob["instance_id"], self.bob["token"], "segredo",
            {"bob": "privado"}, expected_revision=0,
        )
        self.client.sync_once()
        self.assertFalse(self.replica.get(
            self.bob["instance_id"], self.bob["token"], "segredo",
        )["found"])
        self.assertEqual(self.source.manifest(
            self.node["node_id"], self.node["node_token"],
        )["instance_id"], self.alice["instance_id"])
        with self.assertRaises(PermissionError):
            self.replica.get(
                self.alice["instance_id"], self.bob["token"], "historia",
            )

    def test_instancia_revogada_impede_exportacao_e_aplicacao(self):
        self.seed()
        snapshot = self.source.document(
            self.node["node_id"], self.node["node_token"], "historia",
        )
        self.auth.revoke(IrisInstanceAuthority.OWNER_ID, self.secret,
                         self.alice["instance_id"])
        with self.assertRaises(PermissionError):
            self.source.manifest(self.node["node_id"], self.node["node_token"])
        with self.assertRaises(PermissionError):
            self.sink.apply(snapshot)

    def test_patinete_smarttv_ou_visita_nao_replica(self):
        visitor = self.pair(self.bob, mode="visit",
                            surfaces={"memory.sync"})
        with self.assertRaises(PermissionError):
            self.source.manifest(visitor["node_id"], visitor["node_token"])
        with self.assertRaises(PermissionError):
            self.mesh.offer_device(
                device_name="Patinete", device_type="scooter",
                surfaces={"memory.sync"}, locally_approved=True,
            )
        with self.assertRaises(PermissionError):
            self.mesh.offer_device(
                device_name="TV", device_type="smart_tv",
                surfaces={"memory.sync"}, locally_approved=True,
            )

    def test_rejeita_payload_alterado_token_errado_e_fonte_forjada(self):
        self.seed()
        encrypted = self.source.document(
            self.node["node_id"], self.node["node_token"], "historia",
        )
        tampered = dict(encrypted)
        tampered["ciphertext"] = tampered["ciphertext"][:-7] + "AAAAAAA"
        with self.assertRaises(IrisReplicaIntegrityError):
            self.sink.apply(tampered)
        with self.assertRaises(IrisReplicaIntegrityError):
            IrisReplicaSink(
                self.replica,
                node_id=self.node["node_id"], node_token=secrets.token_urlsafe(32),
                instance_id=self.alice["instance_id"], source_id=self.source_id,
            ).apply(encrypted)
        malicious = _seal(self.node["node_id"], self.node["node_token"], {
            "version": 1, "source_id": "iris-source-other-000",
            "instance_id": self.alice["instance_id"],
            "document_id": "historia", "revision": 1, "value": {"false": True},
        })
        with self.assertRaises(IrisReplicaIntegrityError):
            self.sink.apply(malicious)

    def test_documento_preexistente_diferente_provoca_conflito(self):
        self.seed()
        self.replica.put(
            self.alice["instance_id"], self.alice["token"], "historia",
            {"outra": "versao"}, expected_revision=0,
        )
        with self.assertRaises(StateConflictError):
            self.client.sync_once()
        self.assertEqual(self.replica.get(
            self.alice["instance_id"], self.alice["token"], "historia",
        )["value"], {"outra": "versao"})

    def test_divergencia_local_apos_sync_nao_e_sobrescrita(self):
        self.seed()
        self.client.sync_once()
        self.replica.put(
            self.alice["instance_id"], self.alice["token"], "historia",
            {"revisao": "local"}, expected_revision=1,
        )
        self.main.put(
            self.alice["instance_id"], self.alice["token"], "historia",
            {"revisao": "origem"}, expected_revision=1,
        )
        with self.assertRaises(StateConflictError):
            self.client.sync_once()
        self.assertEqual(self.replica.get(
            self.alice["instance_id"], self.alice["token"], "historia",
        )["value"], {"revisao": "local"})

    def test_nao_aceita_https_inseguro_ou_origem_errada(self):
        for endpoint in ("http://example.com", "https://login:pass@host",
                         "https://host/path", "https://host?q=1"):
            with self.assertRaises(ValueError):
                IrisReplicaPullClient(endpoint, self.sink)
        with self.assertRaises(IrisReplicaIntegrityError):
            IrisReplicaPullClient(
                "http://localhost", self.sink,
                transport=lambda *args: {
                    "source_id": "iris-source-wrong-111",
                    "instance_id": self.alice["instance_id"], "documents": [],
                }
            ).sync_once()

    def test_poller_retoma_apos_indisponibilidade_transitoria(self):
        self.seed()
        stop = Event()
        attempts = {"count": 0}
        def flaky(path, headers):
            if path == "/api/iris/replication/manifest":
                attempts["count"] += 1
                if attempts["count"] == 1:
                    raise IrisReplicaTransportError("queda transitoria")
                stop.set()
                return self.source.manifest(
                    headers["X-Iris-Node-Id"], headers["X-Iris-Node-Token"],
                )
            return self.source.document(
                headers["X-Iris-Node-Id"], headers["X-Iris-Node-Token"],
                path.rsplit("/", 1)[-1],
            )
        puller = IrisReplicaPullClient(
            "https://example.invalid", self.sink, transport=flaky,
        )
        stats = puller.run_until(stop, interval_seconds=1.0)
        self.assertEqual(stats, {"successful_syncs": 1, "transport_errors": 1})
        self.assertEqual(self.replica.get(
            self.alice["instance_id"], self.alice["token"], "historia",
        )["value"], {"memoria": "tudo bem"})

    def test_replicacao_nao_fura_lock_do_banco_primario(self):
        from device.iris_local_failover import IrisLeaseCoordinator
        self.seed()
        coordinator = IrisLeaseCoordinator(self.mesh, self.replica)
        leader = coordinator.acquire(
            self.node["node_id"], self.node["node_token"], ttl_seconds=10,
        )
        self.assertTrue(leader["acquired"])
        with self.assertRaises(PermissionError):
            self.client.sync_once()
        self.assertFalse(self.replica.get(
            self.alice["instance_id"], self.alice["token"], "historia",
        )["found"])

    def test_poller_parada_sem_trabalho_indevido(self):
        self.seed()
        finished = Event()
        finished.set()
        self.client.run_until(finished, interval_seconds=1.0)
        self.assertFalse(self.replica.get(
            self.alice["instance_id"], self.alice["token"], "historia",
        )["found"])


if __name__ == "__main__":
    unittest.main()
