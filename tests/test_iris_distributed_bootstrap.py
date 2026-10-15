"""Bootstrap opcional da Iris: segredos, estado, reinicio e fail-closed."""
from pathlib import Path
import os
import secrets
import tempfile
import unittest

from runtime.iris_distributed_bootstrap import create_local_iris_stack
from security.iris_instance_policy import IrisInstanceAuthority


class IrisBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "iris-private"
        self.env = {
            "IRIS_OWNER_TOKEN": secrets.token_urlsafe(32),
            "IRIS_IDENTITY_KEY_HEX": secrets.token_hex(32),
            "IRIS_MESH_KEY_HEX": secrets.token_hex(32),
            "IRIS_STATE_KEY_HEX": secrets.token_hex(32),
            "IRIS_BROKER_KEY_HEX": secrets.token_hex(32),
            "IRIS_SOURCE_ID": "iris-source-test-instance-001",
        }

    def tearDown(self):
        self.tmp.cleanup()

    def test_reinicio_recupera_instancias_e_documentos_cifrados(self):
        instance = create_local_iris_stack(self.root, environ=self.env)
        try:
            alice = instance.authority.create_resident(
                self.env["IRIS_OWNER_TOKEN"],
                tenant_id="cliente-alice", display_name="Iris Alice",
                user_consented=True,
            )
            instance.store.put(
                alice["instance_id"], alice["token"], "memory",
                {"state": "persisted"}, expected_revision=0,
            )
            self.assertEqual(set(instance.api_options()), {
                "iris_instance_authority", "iris_device_mesh",
                "iris_state_store", "iris_task_broker",
                "iris_replica_source", "iris_dialogue_service",
            })
        finally:
            instance.close()
        after = create_local_iris_stack(self.root, environ=self.env)
        try:
            self.assertTrue(after.authority.require(
                alice["instance_id"], alice["token"], "memory.own",
            ))
            self.assertEqual(after.store.get(
                alice["instance_id"], alice["token"], "memory",
            )["value"], {"state": "persisted"})
            self.assertFalse(after.dialogue.history(
                alice["instance_id"], alice["token"],
                conversation_id="sample-session",
            )["has_pending"])
        finally:
            after.close()

    def test_recusa_configuracao_fraca_e_chaves_repetidas(self):
        bad = dict(self.env)
        bad["IRIS_OWNER_TOKEN"] = "admin"
        with self.assertRaises(ValueError):
            create_local_iris_stack(self.root, environ=bad)
        bad = dict(self.env)
        bad["IRIS_MESH_KEY_HEX"] = bad["IRIS_STATE_KEY_HEX"]
        with self.assertRaises(ValueError):
            create_local_iris_stack(self.root, environ=bad)
        bad = dict(self.env)
        bad["IRIS_BROKER_KEY_HEX"] = "zz" * 32
        with self.assertRaises(ValueError):
            create_local_iris_stack(self.root, environ=bad)
        bad = dict(self.env)
        bad.pop("IRIS_SOURCE_ID")
        with self.assertRaises(ValueError):
            create_local_iris_stack(self.root, environ=bad)

    def test_segundos_segredos_criticos_nao_podem_abrir_estado(self):
        initial = create_local_iris_stack(self.root, environ=self.env)
        initial.close()
        changed = dict(self.env)
        changed["IRIS_IDENTITY_KEY_HEX"] = secrets.token_hex(32)
        with self.assertRaises(Exception):
            create_local_iris_stack(self.root, environ=changed)

    @unittest.skipIf(os.name == "nt", "Permissoes POSIX nao se aplicam ao Windows")
    def test_impede_diretorio_publico_e_symlink(self):
        self.root.mkdir(mode=0o755)
        os.chmod(self.root, 0o755)
        with self.assertRaises(PermissionError):
            create_local_iris_stack(self.root, environ=self.env)
        target = Path(self.tmp.name) / "target"
        target.mkdir()
        link = Path(self.tmp.name) / "linked"
        link.symlink_to(target, target_is_directory=True)
        with self.assertRaises(ValueError):
            create_local_iris_stack(link, environ=self.env)


if __name__ == "__main__":
    unittest.main()
