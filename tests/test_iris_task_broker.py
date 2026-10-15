"""Broker da Iris: autorizacao por no, isolamento e recuperacao de lease."""
from __future__ import annotations

import secrets
import unittest

from device.iris_mesh import IrisDeviceMesh
from device.iris_task_broker import IrisTaskBroker, execute_local_operation
from security.iris_instance_policy import IrisInstanceAuthority


class IrisTaskBrokerTests(unittest.TestCase):
    def setUp(self):
        self.now = 2_000_000_000.0
        self.secret = secrets.token_urlsafe(32)
        self.auth = IrisInstanceAuthority(self.secret, clock=lambda: self.now)
        self.mesh = IrisDeviceMesh(self.auth, clock=lambda: self.now)
        self.broker = IrisTaskBroker(self.mesh, clock=lambda: self.now)
        self.owner = IrisInstanceAuthority.OWNER_ID
        self.a = self.auth.create_resident(
            self.secret, tenant_id="conta-alice",
            display_name="Íris Alice", user_consented=True,
        )
        self.b = self.auth.create_resident(
            self.secret, tenant_id="conta-bob",
            display_name="Íris Bob", user_consented=True,
        )

    def attach(self, person, *, mode="integrated", kind="windows"):
        offer = self.mesh.offer_device(
            device_name="Cliente", device_type=kind,
            surfaces={"compute.light"}, mode=mode, locally_approved=True,
        )
        return self.mesh.approve_offer(
            person["instance_id"], person["token"],
            offer_id=offer["offer_id"],
            verification_code=offer["verification_code"],
        )

    def submit(self, person, operation="math.sum", payload=None):
        return self.broker.submit(
            person["instance_id"], person["token"],
            operation=operation, payload=payload or {"values": [1, 2, 3]},
        )

    def test_dois_nos_da_mesma_iris_executam_fila_completa(self):
        pc = self.attach(self.a)
        mobile = self.attach(self.a, kind="android")
        job1 = self.submit(self.a)
        job2 = self.submit(self.a, operation="text.word_count",
                           payload={"text": "Íris mora em dois aparelhos"})
        self.assertTrue(job1["submitted"])
        task_pc = self.broker.claim(pc["node_id"], pc["node_token"])
        task_mobile = self.broker.claim(mobile["node_id"], mobile["node_token"])
        self.assertEqual({task_pc["job_id"], task_mobile["job_id"]},
                         {job1["job_id"], job2["job_id"]})
        for node, task in ((pc, task_pc), (mobile, task_mobile)):
            result = execute_local_operation(task["operation"], task["payload"])
            receipt = self.broker.complete(
                node["node_id"], node["node_token"],
                job_id=task["job_id"], lease_token=task["lease_token"],
                result=result,
            )
            self.assertFalse(receipt["verified"])
        self.assertEqual(self.broker.claim(pc["node_id"], pc["node_token"])["status"], "idle")
        self.assertEqual(self.broker.inspect(
            self.a["instance_id"], self.a["token"], job_id=job1["job_id"],
        )["result"], {"sum": 6.0})

    def test_isolamento_de_dois_clientes(self):
        alice_pc = self.attach(self.a)
        bob_pc = self.attach(self.b)
        job = self.submit(self.a, "hash.sha256", {"text": "segredo"})
        self.assertEqual(self.broker.claim(bob_pc["node_id"], bob_pc["node_token"])["status"], "idle")
        with self.assertRaises(PermissionError):
            self.broker.inspect(self.b["instance_id"], self.b["token"],
                                job_id=job["job_id"])
        with self.assertRaises(PermissionError):
            self.broker.claim(alice_pc["node_id"], bob_pc["node_token"])
        task = self.broker.claim(alice_pc["node_id"], alice_pc["node_token"])
        with self.assertRaises(PermissionError):
            self.broker.complete(
                bob_pc["node_id"], bob_pc["node_token"],
                job_id=job["job_id"], lease_token=task["lease_token"],
                result={"sha256": "false"},
            )

    def test_token_de_lease_nao_e_intercambiavel_e_nao_reutiliza(self):
        pc = self.attach(self.a)
        job = self.submit(self.a)
        task = self.broker.claim(pc["node_id"], pc["node_token"])
        with self.assertRaises(PermissionError):
            self.broker.complete(
                pc["node_id"], pc["node_token"],
                job_id=job["job_id"], lease_token="invalid",
                result={"sum": 6},
            )
        self.broker.complete(
            pc["node_id"], pc["node_token"],
            job_id=job["job_id"], lease_token=task["lease_token"],
            result={"sum": 6},
        )
        with self.assertRaises(PermissionError):
            self.broker.complete(
                pc["node_id"], pc["node_token"],
                job_id=job["job_id"], lease_token=task["lease_token"],
                result={"sum": 6},
            )

    def test_tarefa_recupera_depois_lease_e_novo_no(self):
        pc = self.attach(self.a)
        tablet = self.attach(self.a, kind="android")
        job = self.submit(self.a)
        old = self.broker.claim(pc["node_id"], pc["node_token"])
        self.now += 46
        new = self.broker.claim(tablet["node_id"], tablet["node_token"])
        self.assertEqual(old["job_id"], new["job_id"])
        self.assertNotEqual(old["lease_token"], new["lease_token"])
        with self.assertRaises(PermissionError):
            self.broker.complete(
                pc["node_id"], pc["node_token"],
                job_id=old["job_id"], lease_token=old["lease_token"],
                result={"sum": 6},
            )
        self.broker.complete(
            tablet["node_id"], tablet["node_token"],
            job_id=new["job_id"], lease_token=new["lease_token"],
            result={"sum": 6},
        )
        self.assertEqual(self.broker.inspect(
            self.a["instance_id"], self.a["token"], job_id=job["job_id"],
        )["attempts"], 2)

    def test_visitante_nao_processa_e_nao_aceita_tarefas(self):
        visitor = self.attach(self.a, mode="visit")
        self.assertEqual(self.submit(self.a)["status"], "unavailable")
        with self.assertRaises(PermissionError):
            self.broker.claim(visitor["node_id"], visitor["node_token"])

    def test_revogacao_impede_computacao(self):
        pc = self.attach(self.a)
        job = self.submit(self.a)
        self.auth.revoke(self.owner, self.secret, self.a["instance_id"])
        with self.assertRaises(PermissionError):
            self.broker.claim(pc["node_id"], pc["node_token"])
        with self.assertRaises(PermissionError):
            self.broker.inspect(self.a["instance_id"], self.a["token"], job["job_id"])

    def test_negacao_de_payload_arbitrario_e_valores_invalidos(self):
        pc = self.attach(self.a)
        for operation, payload in (
            ("shell.exec", {"cmd": "ls"}),
            ("math.sum", {"values": [float("nan")]}),
            ("math.sum", {"values": [True]}),
            ("text.word_count", {"text": "x" * 3000}),
            ("hash.sha256", {"text": "foo", "path": "/etc/passwd"}),
        ):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                self.submit(self.a, operation, payload)

    def test_resultado_nao_confiavel_nao_e_auditoria(self):
        pc = self.attach(self.a)
        job = self.submit(self.a)
        task = self.broker.claim(pc["node_id"], pc["node_token"])
        receipt = self.broker.complete(
            pc["node_id"], pc["node_token"],
            job_id=job["job_id"], lease_token=task["lease_token"],
            result={"sum": 999},
        )
        self.assertFalse(receipt["verified"])

    def test_operacoes_puras_sem_acesso_ao_sistema(self):
        self.assertEqual(execute_local_operation(
            "text.word_count", {"text": "um dois tres"}), {"words": 3})
        self.assertEqual(execute_local_operation(
            "hash.sha256", {"text": ""})["sha256"],
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        with self.assertRaises(ValueError):
            execute_local_operation("python.eval", {"code": "1+1"})


if __name__ == "__main__":
    unittest.main()
