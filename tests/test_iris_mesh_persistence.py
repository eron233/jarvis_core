"""Inventario cifrado sobrevivendo a reinicio, sem considerar nos online."""
import secrets
import tempfile
from pathlib import Path
import unittest

from device.iris_mesh_persistence import PersistentIrisDeviceMesh, MeshStoreIntegrityError
from security.iris_instance_policy import IrisInstanceAuthority


class PersistentIrisMeshTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "mesh.iris"
        self.secret = secrets.token_urlsafe(32)
        self.key = secrets.token_bytes(32)
        self.now = 2_000_000_000.0
        self.auth = IrisInstanceAuthority(self.secret)

    def tearDown(self):
        self.dir.cleanup()

    def make(self, *, key=None):
        return PersistentIrisDeviceMesh(
            self.auth, self.path, storage_key=key if key is not None else self.key,
            clock=lambda: self.now,
        )

    def pair(self, mesh, *, mode="integrated", seconds=1800):
        offer = mesh.offer_device(
            device_name="Desktop privado", device_type="windows",
            surfaces={"presence.display", "compute.light"},
            mode=mode, locally_approved=True,
        )
        return mesh.approve_offer(
            IrisInstanceAuthority.OWNER_ID, self.secret,
            offer_id=offer["offer_id"],
            verification_code=offer["verification_code"],
            visit_seconds=seconds,
        )

    def test_reatach_apos_reinicio_precisa_novo_heartbeat_real(self):
        mesh = self.make()
        node = self.pair(mesh)
        self.assertTrue(self.path.exists())
        self.assertNotIn(b"Desktop privado", self.path.read_bytes())
        self.assertNotIn(node["node_token"].encode(), self.path.read_bytes())
        reopened = self.make()
        state = reopened.devices(IrisInstanceAuthority.OWNER_ID, self.secret)
        self.assertEqual(len(state), 1)
        self.assertFalse(state[0]["connected"])
        reopened.heartbeat(node["node_id"], node["node_token"])
        self.assertTrue(reopened.devices(
            IrisInstanceAuthority.OWNER_ID, self.secret,
        )[0]["connected"])

    def test_revogado_continua_revogado_apos_reinicio(self):
        mesh = self.make()
        node = self.pair(mesh)
        mesh.disconnect(IrisInstanceAuthority.OWNER_ID, self.secret, node_id=node["node_id"])
        reopened = self.make()
        self.assertEqual(reopened.devices(
            IrisInstanceAuthority.OWNER_ID, self.secret,
        ), [])
        with self.assertRaises(PermissionError):
            reopened.heartbeat(node["node_id"], node["node_token"])

    def test_visita_nao_renova_apos_expiracao(self):
        mesh = self.make()
        node = self.pair(mesh, mode="visit", seconds=60)
        self.now += 61
        reopened = self.make()
        with self.assertRaises(PermissionError):
            reopened.heartbeat(node["node_id"], node["node_token"])
        self.assertEqual(reopened.devices(
            IrisInstanceAuthority.OWNER_ID, self.secret,
        ), [])

    def test_chave_errada_e_arquivo_adulterado_recusados(self):
        mesh = self.make()
        self.pair(mesh)
        with self.assertRaises(MeshStoreIntegrityError):
            self.make(key=secrets.token_bytes(32))
        with open(self.path, "r+b") as f:
            f.seek(-8, 2)
            f.write(b"evilTEST")
        with self.assertRaises(MeshStoreIntegrityError):
            self.make()

    def test_chave_curta_nao_aceita(self):
        with self.assertRaises(ValueError):
            PersistentIrisDeviceMesh(self.auth, self.path, storage_key=b"1234")


if __name__ == "__main__":
    unittest.main()
