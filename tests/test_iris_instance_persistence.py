"""Persistencia da identidade Iris cifrada e isolada de conversas."""
import secrets
import tempfile
from pathlib import Path
import unittest

from security.iris_instance_persistence import (
    PersistentIrisInstanceAuthority, IdentityStoreIntegrityError,
)
from security.iris_instance_policy import IrisInstanceAuthority


class PersistentIrisIdentityTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "private.iris"
        self.secret = secrets.token_urlsafe(32)
        self.key = secrets.token_bytes(32)
        self.now = 2_000_000_000.0

    def tearDown(self):
        self.dir.cleanup()

    def make(self, **kwargs):
        return PersistentIrisInstanceAuthority(
            kwargs.pop("owner_token", self.secret),
            self.path, storage_key=kwargs.pop("storage_key", self.key),
            clock=lambda: self.now,
        )

    def test_migracao_legacy_remove_integracao_de_residente_e_delegada(self):
        from dataclasses import replace
        auth = self.make()
        alice = auth.create_resident(
            self.secret, tenant_id="cliente-antigo",
            display_name="Iris antiga", user_consented=True,
        )
        child = auth.delegate(
            alice["instance_id"], alice["token"], capabilities={"chat.use"},
        )
        # Simula um snapshot cifrado produzido pela versao antiga.
        with auth._lock:
            for record_id in (alice["instance_id"], child["instance_id"]):
                old = auth._records[record_id]
                auth._records[record_id] = replace(
                    old, capabilities=old.capabilities | frozenset({"device.local"}),
                )
            auth._save()
        restored = self.make()
        self.assertNotIn("device.local", restored.capabilities(
            alice["instance_id"], alice["token"],
        ))
        self.assertNotIn("device.local", restored.capabilities(
            child["instance_id"], child["token"],
        ))
        with self.assertRaises(PermissionError):
            restored.require(
                alice["instance_id"], alice["token"], "device.local",
            )
        # Sanitizacao fica persistida imediatamente e nao renasce no restart.
        restarted = self.make()
        self.assertEqual(restarted.capabilities(
            child["instance_id"], child["token"],
        ), ["chat.use"])

    def test_delegada_legada_so_com_device_local_e_revogada_ao_reabrir(self):
        from dataclasses import replace
        original = self.make()
        resident = original.create_resident(
            self.secret, tenant_id="cliente-antigo-2",
            display_name="Cliente antigo", user_consented=True,
        )
        child = original.delegate(
            resident["instance_id"], resident["token"],
            capabilities={"chat.use"},
        )
        with original._lock:
            record = original._records[child["instance_id"]]
            original._records[child["instance_id"]] = replace(
                record, capabilities=frozenset({"device.local"}),
            )
            original._save()
        recovered = self.make()
        with self.assertRaises(PermissionError):
            recovered.require(child["instance_id"], child["token"], "chat.use")
        with self.assertRaises(PermissionError):
            recovered.require(child["instance_id"], child["token"], "device.local")
        self.assertTrue(recovered.require(
            resident["instance_id"], resident["token"], "chat.use",
        ))
        again = self.make()
        with self.assertRaises(PermissionError):
            again.capabilities(child["instance_id"], child["token"])

    def test_snapshot_inicial_ja_existe_e_nao_contem_token(self):
        auth = self.make()
        self.assertTrue(self.path.exists())
        saved = self.path.read_bytes()
        self.assertTrue(saved.startswith(b"IRISID1"))
        self.assertNotIn(self.secret.encode(), saved)
        self.assertNotIn(b"owner-private", saved)
        self.assertTrue(auth.require(
            IrisInstanceAuthority.OWNER_ID, self.secret, "system.admin",
        ))

    def test_residente_reabre_com_mesmo_token_e_permissoes(self):
        original = self.make()
        alice = original.create_resident(
            self.secret, tenant_id="tenant-alice",
            display_name="Íris do cliente", user_consented=True,
        )
        original.set_resident_preferences(
            alice["instance_id"], alice["token"],
            corridor_visible=True, feedback_opt_in=True,
        )
        original.report_feedback(alice["instance_id"], alice["token"], code="slow_response")
        reopened = self.make()
        self.assertTrue(reopened.require(alice["instance_id"], alice["token"], "chat.use"))
        self.assertNotIn("trade.use", reopened.capabilities(
            alice["instance_id"], alice["token"],
        ))
        self.assertEqual(len(reopened.corridor(self.secret)), 1)
        self.assertEqual(reopened.feedback_summary(self.secret), {})
        reopened.revoke(IrisInstanceAuthority.OWNER_ID, self.secret, alice["instance_id"])
        third = self.make()
        with self.assertRaises(PermissionError):
            third.capabilities(alice["instance_id"], alice["token"])

    def test_delegada_expira_apos_reinicio(self):
        auth = self.make()
        alice = auth.create_resident(
            self.secret, tenant_id="tenant-alice", display_name="Íris",
            user_consented=True,
        )
        child = auth.delegate(
            alice["instance_id"], alice["token"],
            capabilities={"chat.use"}, ttl_seconds=60,
        )
        self.assertTrue(self.make().require(
            child["instance_id"], child["token"], "chat.use",
        ))
        self.now += 61
        with self.assertRaises(PermissionError):
            self.make().require(child["instance_id"], child["token"], "chat.use")

    def test_rejeita_chave_errada_segredo_do_dono_errado_e_adulteracao(self):
        self.make()
        with self.assertRaises(IdentityStoreIntegrityError):
            self.make(storage_key=secrets.token_bytes(32))
        with self.assertRaises(PermissionError):
            self.make(owner_token=secrets.token_urlsafe(32))
        with open(self.path, "r+b") as file:
            file.seek(-4, 2)
            file.write(b"FAIL")
        with self.assertRaises(IdentityStoreIntegrityError):
            self.make()

    def test_chave_de_persistencia_precisa_ser_forte(self):
        with self.assertRaises(ValueError):
            PersistentIrisInstanceAuthority(self.secret, self.path, storage_key=b"x")


if __name__ == "__main__":
    unittest.main()
