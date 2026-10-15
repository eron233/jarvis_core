"""Cifras reais, CAS e isolamento entre instancias no estado Iris."""
import secrets
import sqlite3
import tempfile
from pathlib import Path
import unittest

from memory_system.iris_state_store import (
    IrisEncryptedStateStore, StateConflictError, StateCorruptionError,
)
from security.iris_instance_policy import IrisInstanceAuthority


class IrisEncryptedStateTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = Path(self.folder.name) / "iris.sqlite3"
        self.secret = secrets.token_urlsafe(32)
        self.key = secrets.token_bytes(32)
        self.auth = IrisInstanceAuthority(self.secret)
        self.alice = self.auth.create_resident(
            self.secret, tenant_id="pessoa-alice", display_name="Iris Alice",
            user_consented=True,
        )
        self.bob = self.auth.create_resident(
            self.secret, tenant_id="pessoa-bob", display_name="Iris Bob",
            user_consented=True,
        )
        self.store = IrisEncryptedStateStore(self.path, self.auth, root_key=self.key)

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def test_documento_encriptado_com_persistencia_em_disco(self):
        instance_id = self.alice["instance_id"]
        token = self.alice["token"]
        value = {"estado": "pesquisando", "observacoes": ["minha conversa confidencial"]}
        self.assertEqual(self.store.get(instance_id, token, "memoria"), {
            "found": False, "revision": 0, "value": None,
        })
        self.assertEqual(
            self.store.put(instance_id, token, "memoria", value, expected_revision=0),
            {"revision": 1, "written": True},
        )
        self.assertEqual(self.store.get(instance_id, token, "memoria")["value"], value)
        self.store.close()
        # Não pode guardar texto sensivel em claro nem na pagina do SQLite.
        self.assertNotIn(b"minha conversa confidencial", self.path.read_bytes())
        self.store = IrisEncryptedStateStore(self.path, self.auth, root_key=self.key)
        again = self.store.get(instance_id, token, "memoria")
        self.assertEqual(again["revision"], 1)
        self.assertEqual(again["value"], value)
        self.assertEqual(
            self.store.put(instance_id, token, "memoria", {"novo": 2},
                           expected_revision=1)["revision"], 2,
        )

    def test_mesmo_nome_de_memoria_isolado_por_tenant(self):
        self.store.put(self.alice["instance_id"], self.alice["token"], "contexto",
                       {"dono": "Alice"}, expected_revision=0)
        self.store.put(self.bob["instance_id"], self.bob["token"], "contexto",
                       {"dono": "Bob"}, expected_revision=0)
        self.assertEqual(self.store.get(
            self.alice["instance_id"], self.alice["token"], "contexto",
        )["value"]["dono"], "Alice")
        self.assertEqual(self.store.get(
            self.bob["instance_id"], self.bob["token"], "contexto",
        )["value"]["dono"], "Bob")
        with self.assertRaises(PermissionError):
            self.store.get(self.alice["instance_id"], self.bob["token"], "contexto")
        self.assertEqual(
            self.store.document_revisions(self.alice["instance_id"], self.alice["token"]),
            [{"document_id": "contexto", "revision": 1}],
        )

    def test_concorrencia_otimista_sem_perda_silenciosa(self):
        i, t = self.alice["instance_id"], self.alice["token"]
        self.store.put(i, t, "status", {"numero": 1}, expected_revision=0)
        with self.assertRaises(StateConflictError):
            self.store.put(i, t, "status", {"numero": 2}, expected_revision=0)
        self.assertEqual(self.store.get(i, t, "status")["value"]["numero"], 1)
        self.store.put(i, t, "status", {"numero": 3}, expected_revision=1)
        self.assertEqual(self.store.get(i, t, "status")["revision"], 2)

    def test_chave_errada_ou_ciphertext_adulterado_falha_fechado(self):
        i, t = self.alice["instance_id"], self.alice["token"]
        self.store.put(i, t, "estado", {"privado": True}, expected_revision=0)
        wrong = IrisEncryptedStateStore(self.path, self.auth, root_key=secrets.token_bytes(32))
        try:
            with self.assertRaises(StateCorruptionError):
                wrong.get(i, t, "estado")
        finally:
            wrong.close()
        with sqlite3.connect(self.path) as db:
            db.execute(
                "UPDATE iris_instance_state SET ciphertext=? WHERE instance_id=?",
                (b"tampered", i),
            )
        with self.assertRaises(StateCorruptionError):
            self.store.get(i, t, "estado")

    def test_backup_consistente_e_cifrado(self):
        i, t = self.alice["instance_id"], self.alice["token"]
        self.store.put(i, t, "checkpoint", {"ok": "segredo privado"}, expected_revision=0)
        backup = Path(self.folder.name) / "backup.sqlite3"
        self.store.backup(backup)
        self.assertTrue(backup.exists())
        self.assertNotIn(b"segredo privado", backup.read_bytes())
        restored = IrisEncryptedStateStore(backup, self.auth, root_key=self.key)
        try:
            self.assertEqual(
                restored.get(i, t, "checkpoint")["value"]["ok"], "segredo privado",
            )
        finally:
            restored.close()

    def test_revogacao_impede_lectura_e_escrita(self):
        i, t = self.alice["instance_id"], self.alice["token"]
        self.store.put(i, t, "dados", {"teste": 1}, expected_revision=0)
        self.auth.revoke(IrisInstanceAuthority.OWNER_ID, self.secret, i)
        with self.assertRaises(PermissionError):
            self.store.get(i, t, "dados")
        with self.assertRaises(PermissionError):
            self.store.put(i, t, "dados", {}, expected_revision=1)

    def test_delegada_nao_ve_memoria_do_pai(self):
        i, t = self.alice["instance_id"], self.alice["token"]
        self.store.put(i, t, "resumo", {"privado": True}, expected_revision=0)
        child = self.auth.delegate(i, t, capabilities={"memory.own"}, ttl_seconds=600)
        self.assertFalse(self.store.get(
            child["instance_id"], child["token"], "resumo",
        )["found"])
        with self.assertRaises(PermissionError):
            self.store.get(i, child["token"], "resumo")

    def test_valida_payload_tamanho_revision_e_identificadores(self):
        i, t = self.alice["instance_id"], self.alice["token"]
        for doc in ("../segredo", ".hidden", "x/" + "x", ""):
            with self.subTest(doc=doc), self.assertRaises(ValueError):
                self.store.put(i, t, doc, {}, expected_revision=0)
        with self.assertRaises(ValueError):
            self.store.put(i, t, "safe", {"x": "a" * 66000}, expected_revision=0)
        with self.assertRaises(ValueError):
            self.store.put(i, t, "safe", {"x": float("nan")}, expected_revision=0)
        with self.assertRaises(ValueError):
            self.store.put(i, t, "safe", {}, expected_revision=True)
        with self.assertRaises(ValueError):
            IrisEncryptedStateStore(self.path, self.auth, root_key=b"weak")
        self.assertFalse(self.store.get(i, t, "safe")["found"])


if __name__ == "__main__":
    unittest.main()
