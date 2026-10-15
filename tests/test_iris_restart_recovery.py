"""Retomada apos falha do processo usando os mesmos segredos e dados cifrados."""
from pathlib import Path
import secrets
import tempfile
import unittest

from device.iris_mesh_persistence import PersistentIrisDeviceMesh
from memory_system.iris_state_store import IrisEncryptedStateStore
from security.iris_instance_persistence import PersistentIrisInstanceAuthority


class IrisRestartRecoveryTests(unittest.TestCase):
    def test_troca_de_processo_com_um_so_estado_logico(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            identity_key = secrets.token_bytes(32)
            mesh_key = secrets.token_bytes(32)
            state_key = secrets.token_bytes(32)
            founder_secret = secrets.token_urlsafe(32)
            now = [1_900_000_000.0]
            clock = lambda: now[0]

            def open_node():
                identity = PersistentIrisInstanceAuthority(
                    founder_secret, root / "identity.iris",
                    storage_key=identity_key, clock=clock,
                )
                mesh = PersistentIrisDeviceMesh(
                    identity, root / "devices.iris",
                    storage_key=mesh_key, clock=clock,
                )
                state = IrisEncryptedStateStore(
                    root / "memory.sqlite3", identity, root_key=state_key,
                )
                return identity, mesh, state

            auth, mesh, state = open_node()
            user = auth.create_resident(
                founder_secret, tenant_id="cliente-001",
                display_name="Íris do proprietário", user_consented=True,
            )
            uid, token = user["instance_id"], user["token"]
            offer = mesh.offer_device(
                device_name="Notebook", device_type="windows",
                surfaces={"presence.display", "compute.light"},
                locally_approved=True,
            )
            laptop = mesh.approve_offer(
                uid, token, offer_id=offer["offer_id"],
                verification_code=offer["verification_code"],
            )
            offer = mesh.offer_device(
                device_name="Celular", device_type="android",
                surfaces={"compute.light"},
                locally_approved=True,
            )
            phone = mesh.approve_offer(
                uid, token, offer_id=offer["offer_id"],
                verification_code=offer["verification_code"],
            )
            state.put(uid, token, "identidade", {
                "contexto": "retomada", "preferencias": {"voz": "pt-BR"},
            }, expected_revision=0)
            state.close()

            # Novo processo, mesmo segredo e volume persistente, sem rede externa.
            auth2, mesh2, state2 = open_node()
            try:
                self.assertEqual(
                    state2.get(uid, token, "identidade")["value"]["contexto"],
                    "retomada",
                )
                self.assertEqual(len(mesh2.devices(uid, token)), 2)
                self.assertEqual(mesh2.continuity(uid, token)["active_nodes"], 0)

                # Apenas o aparelho que realmente reconectou volta a ser elegivel.
                mesh2.heartbeat(phone["node_id"], phone["node_token"])
                health = mesh2.continuity(uid, token)
                self.assertEqual(health["active_nodes"], 1)
                self.assertEqual(health["coordinator_candidate"], phone["node_id"])
                self.assertFalse(health["control_plane_running"])
                self.assertFalse(health["guaranteed_failover"])
                self.assertNotEqual(laptop["node_id"], phone["node_id"])
                self.assertEqual(state2.put(
                    uid, token, "identidade", {"contexto": "retomada revisada"},
                    expected_revision=1,
                )["revision"], 2)
            finally:
                state2.close()

            auth3, mesh3, state3 = open_node()
            try:
                self.assertEqual(state3.get(uid, token, "identidade")["revision"], 2)
                self.assertFalse(mesh3.devices(uid, token)[0]["connected"])
                auth3.revoke(auth3.OWNER_ID, founder_secret, uid)
                with self.assertRaises(PermissionError):
                    mesh3.heartbeat(phone["node_id"], phone["node_token"])
                with self.assertRaises(PermissionError):
                    state3.get(uid, token, "identidade")
            finally:
                state3.close()


if __name__ == "__main__":
    unittest.main()
