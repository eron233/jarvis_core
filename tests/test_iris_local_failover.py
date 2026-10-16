"""Lease do escritor com fencing: sem dupla escrita apos troca de lider."""
import secrets
import tempfile
import time
from pathlib import Path
import unittest

from device.iris_mesh import IrisDeviceMesh
from device.iris_local_failover import IrisLeaseCoordinator
from memory_system.iris_state_store import IrisEncryptedStateStore
from security.iris_instance_policy import IrisInstanceAuthority


class IrisLeaseFailoverTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "database.sqlite3"
        self.master = secrets.token_bytes(32)
        self.secret = secrets.token_urlsafe(32)
        self.auth = IrisInstanceAuthority(self.secret)
        self.alice = {"instance_id": self.auth.OWNER_ID, "token": self.secret}
        self.mesh = IrisDeviceMesh(self.auth)
        self.nodes = [self.pair("PC"), self.pair("Laptop")]
        self.store1 = IrisEncryptedStateStore(self.path, self.auth, root_key=self.master)
        self.store2 = IrisEncryptedStateStore(self.path, self.auth, root_key=self.master)
        self.first = IrisLeaseCoordinator(self.mesh, self.store1)
        self.second = IrisLeaseCoordinator(self.mesh, self.store2)

    def tearDown(self):
        self.store1.close()
        self.store2.close()
        self.folder.cleanup()

    def pair(self, name):
        offer = self.mesh.offer_device(
            device_name=name, device_type="windows",
            surfaces={"compute.light"}, locally_approved=True,
        )
        return self.mesh.approve_offer(
            self.alice["instance_id"], self.alice["token"],
            offer_id=offer["offer_id"],
            verification_code=offer["verification_code"],
        )

    def put(self, store, value, epoch=None, node=None, revision=0):
        return store.put(
            self.alice["instance_id"], self.alice["token"], "session",
            value, expected_revision=revision,
            fence_epoch=epoch, fence_node_id=node,
        )

    def test_expiracao_real_promove_segundo_processo_e_bloqueia_epoca_antiga(self):
        a,b = self.nodes
        lead = self.first.acquire(a["node_id"], a["node_token"], ttl_seconds=1.25)
        self.assertTrue(lead["acquired"])
        self.assertEqual(lead["epoch"], 1)
        denied = self.second.acquire(b["node_id"], b["node_token"], ttl_seconds=5)
        self.assertFalse(denied["acquired"])
        with self.assertRaises(PermissionError):
            self.put(self.store2, {"status": "sem fence"})
        self.assertEqual(
            self.put(self.store1, {"writer": "PC"},
                     epoch=lead["epoch"], node=a["node_id"])["revision"], 1,
        )
        time.sleep(1.5)
        takeover = self.second.acquire(b["node_id"], b["node_token"], ttl_seconds=10)
        self.assertTrue(takeover["acquired"])
        self.assertEqual(takeover["epoch"], 2)
        with self.assertRaises(PermissionError):
            self.put(self.store1, {"writer": "PC antigo"},
                     epoch=lead["epoch"], node=a["node_id"], revision=1)
        with self.assertRaises(PermissionError):
            self.first.renew(a["node_id"], a["node_token"],
                             epoch=lead["epoch"], ttl_seconds=5)
        result = self.put(self.store2, {"writer": "Laptop"},
                          epoch=takeover["epoch"], node=b["node_id"], revision=1)
        self.assertEqual(result["revision"], 2)
        self.assertEqual(self.store1.get(
            self.alice["instance_id"], self.alice["token"], "session",
        )["value"]["writer"], "Laptop")

    def test_release_troca_epoca_e_impede_token_antigo(self):
        a,b = self.nodes
        first = self.first.acquire(a["node_id"], a["node_token"], ttl_seconds=10)
        extended = self.first.renew(a["node_id"], a["node_token"],
                                    epoch=first["epoch"], ttl_seconds=30)
        self.assertTrue(extended["renewed"])
        self.assertTrue(self.first.release(
            a["node_id"], a["node_token"], epoch=first["epoch"],
        ))
        with self.assertRaises(PermissionError):
            self.first.renew(a["node_id"], a["node_token"],
                             epoch=first["epoch"])
        next_leader = self.second.acquire(b["node_id"], b["node_token"])
        self.assertEqual(next_leader["epoch"], first["epoch"] + 1)
        self.assertTrue(self.second.status(
            self.alice["instance_id"], self.alice["token"],
        )["active"])
        with self.assertRaises(PermissionError):
            self.put(self.store1, {"old": True}, first["epoch"], a["node_id"])
        self.put(self.store2, {"new": True}, next_leader["epoch"], b["node_id"])

    def test_reinicio_store_mantem_fencing_ativo(self):
        a,b = self.nodes
        lease = self.first.acquire(a["node_id"], a["node_token"], ttl_seconds=10)
        self.store2.close()
        self.store2 = IrisEncryptedStateStore(self.path, self.auth, root_key=self.master)
        with self.assertRaises(PermissionError):
            self.put(self.store2, {"outro": True})
        self.put(self.store2, {"ok": True}, epoch=lease["epoch"], node=a["node_id"])
        self.assertEqual(self.store1.get(
            self.alice["instance_id"], self.alice["token"], "session",
        )["revision"], 1)

    def test_no_revogado_nao_assume_leadership(self):
        a,b = self.nodes
        self.mesh.disconnect(
            self.alice["instance_id"], self.alice["token"], node_id=a["node_id"],
        )
        with self.assertRaises(PermissionError):
            self.first.acquire(a["node_id"], a["node_token"])
        self.assertTrue(self.second.acquire(
            b["node_id"], b["node_token"],
        )["acquired"])

    def test_outro_tenant_nao_controla_lease(self):
        bob = self.auth.create_resident(
            self.secret, tenant_id="tenant-bob",
            display_name="Iris Bob", user_consented=True,
        )
        a = self.nodes[0]
        self.first.acquire(a["node_id"], a["node_token"], ttl_seconds=10)
        with self.assertRaises(PermissionError):
            self.first.status(self.alice["instance_id"], bob["token"])
        # Uma instancia que nao optou por failover pode manter o comportamento local.
        self.assertEqual(self.store2.put(
            bob["instance_id"], bob["token"], "local", {"ok": 1},
            expected_revision=0,
        )["revision"], 1)


if __name__ == "__main__":
    unittest.main()
