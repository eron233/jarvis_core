"""Fila Iris: reinicio nao perde tarefas, mas reentrega pode duplicar efeito."""
from pathlib import Path
import secrets
import tempfile
import unittest

from device.iris_mesh import IrisDeviceMesh
from device.iris_task_persistence import PersistentIrisTaskBroker, BrokerStoreIntegrityError
from security.iris_instance_policy import IrisInstanceAuthority


class PersistentIrisBrokerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "queue.iris"
        self.secret = secrets.token_urlsafe(32)
        self.key = secrets.token_bytes(32)
        self.clock_now = 2_000_000_000.0
        self.auth = IrisInstanceAuthority(self.secret, clock=lambda: self.clock_now)
        self.mesh = IrisDeviceMesh(self.auth, clock=lambda: self.clock_now)
        self.user = {"instance_id": self.auth.OWNER_ID, "token": self.secret}
        offer = self.mesh.offer_device(
            device_name="Notebook", device_type="windows",
            surfaces={"compute.light"}, locally_approved=True,
        )
        self.pc = self.mesh.approve_offer(
            self.user["instance_id"], self.user["token"],
            offer_id=offer["offer_id"], verification_code=offer["verification_code"],
        )
        self.broker = self.open()

    def tearDown(self):
        self.temp.cleanup()

    def open(self, key=None):
        return PersistentIrisTaskBroker(
            self.mesh, self.path, storage_key=self.key if key is None else key,
            clock=lambda: self.clock_now,
        )

    def submit(self):
        return self.broker.submit(
            self.user["instance_id"], self.user["token"],
            operation="math.sum", payload={"values": [2, 4]},
        )

    def test_reinicia_com_lease_abandonada_recuperada(self):
        job = self.submit()
        previous = self.broker.claim(self.pc["node_id"], self.pc["node_token"])
        self.assertEqual(previous["status"], "leased")
        self.broker = self.open()
        recovered = self.broker.inspect(
            self.user["instance_id"], self.user["token"], job_id=job["job_id"],
        )
        self.assertEqual(recovered["status"], "queued")
        new = self.broker.claim(self.pc["node_id"], self.pc["node_token"])
        self.assertEqual(new["job_id"], previous["job_id"])
        self.assertNotEqual(new["lease_token"], previous["lease_token"])
        with self.assertRaises(PermissionError):
            self.broker.complete(
                self.pc["node_id"], self.pc["node_token"], job_id=job["job_id"],
                lease_token=previous["lease_token"], result={"sum": 6},
            )
        self.broker.complete(
            self.pc["node_id"], self.pc["node_token"], job_id=job["job_id"],
            lease_token=new["lease_token"], result={"sum": 6},
        )
        self.broker = self.open()
        self.assertEqual(self.broker.inspect(
            self.user["instance_id"], self.user["token"], job_id=job["job_id"],
        )["result"], {"sum": 6})

    def test_conteudo_privado_nao_fica_no_disco_em_claro(self):
        result = self.broker.submit(
            self.user["instance_id"], self.user["token"],
            operation="text.word_count",
            payload={"text": "uma frase exclusivamente particular"},
        )
        self.assertTrue(self.path.exists())
        self.assertNotIn(b"exclusivamente particular", self.path.read_bytes())
        self.assertTrue(result["submitted"])

    def test_chave_errada_e_dados_trocados_recusados(self):
        self.submit()
        with self.assertRaises(BrokerStoreIntegrityError):
            self.open(key=secrets.token_bytes(32))
        with open(self.path, "r+b") as f:
            f.seek(-3, 2)
            f.write(b"ERR")
        with self.assertRaises(BrokerStoreIntegrityError):
            self.open()

    def test_tarefa_expirada_nao_ressuscita(self):
        job = self.submit()
        self.clock_now += 601
        self.broker = self.open()
        with self.assertRaises(PermissionError):
            self.broker.inspect(
                self.user["instance_id"], self.user["token"], job_id=job["job_id"],
            )

    def test_chave_fraca_nao_aceita(self):
        with self.assertRaises(ValueError):
            self.open(key=b"short")


if __name__ == "__main__":
    unittest.main()
