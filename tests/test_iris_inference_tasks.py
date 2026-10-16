"""Inferencia distribuida: motor local, privacidade e controle de agentes."""
from __future__ import annotations

import secrets
from types import SimpleNamespace
import unittest

from device.iris_inference_tasks import (
    IrisInferenceUnavailable, IrisLocalInferenceExecutor,
    validate_inference_request, validate_inference_result,
)
from device.iris_mesh import IrisDeviceMesh
from device.iris_node_worker import IrisNodeWorker
from device.iris_task_broker import IrisTaskBroker
from security.iris_instance_policy import IrisInstanceAuthority


def request(text: str = "Olá, Íris!"):
    return {
        "messages": [{"role": "user", "content": text}],
        "tier": "general",
        "max_tokens": 96,
    }


class FakeRouter:
    def __init__(self, *, active=True, offline=True, remote=False,
                 content="Eu estou aqui.", status="sucesso"):
        self.config = SimpleNamespace(enabled=active, offline_mode=offline,
                                      allow_remote_endpoints=remote)
        self.content = content
        self.status = status
        self.calls = []

    def chat(self, *, messages, tier, max_tokens, allow_external,
             data_classification):
        self.calls.append({
            "messages": messages, "tier": tier,
            "max_tokens": max_tokens, "allow_external": allow_external,
            "data_classification": data_classification,
        })
        return {"status": self.status, "conteudo": self.content,
                "modelo": "local-modelo-prova"}


class IrisInferenceTasksTests(unittest.TestCase):
    def setUp(self):
        self.now = 1_950_000_000.0
        self.owner_token = secrets.token_urlsafe(32)
        self.auth = IrisInstanceAuthority(
            self.owner_token, clock=lambda: self.now,
        )
        self.mesh = IrisDeviceMesh(self.auth, clock=lambda: self.now)
        self.broker = IrisTaskBroker(self.mesh, clock=lambda: self.now)
        self.user = {"instance_id": self.auth.OWNER_ID, "token": self.owner_token}
        self.other = self.auth.create_resident(
            self.owner_token, tenant_id="cliente-b", display_name="Íris B",
            user_consented=True,
        )

    def pair(self, user, surfaces=None):
        offer = self.mesh.offer_device(
            device_name="Computador com IA", device_type="windows",
            surfaces=set(surfaces or {"compute.infer"}),
            locally_approved=True,
        )
        return self.mesh.approve_offer(
            user["instance_id"], user["token"], offer_id=offer["offer_id"],
            verification_code=offer["verification_code"],
        )

    def submit(self, user, text="Olá"):
        return self.broker.submit(
            user["instance_id"], user["token"],
            operation="inference.chat", payload=request(text),
        )

    def test_rejeita_comandos_scripts_ferramentas_modelos_escolhidos(self):
        examples = [
            {"messages": [], "tier": "general", "max_tokens": 10},
            {"messages": [{"role": "system", "content": "sudo rm"}],
             "tier": "general", "max_tokens": 10},
            {"messages": [{"role": "user", "content": "ok"}],
             "tier": "general", "max_tokens": True},
            {"messages": [{"role": "user", "content": "ok"}],
             "tier": "coding", "max_tokens": 10},
            {"messages": [{"role": "user", "content": "ok"}],
             "tier": "general", "max_tokens": 10, "tools": [{"shell": True}]},
            {"messages": [{"role": "user", "content": "x" * 2001}],
             "tier": "general", "max_tokens": 10},
            {"messages": [{"role": "assistant", "content": "ok"}],
             "tier": "general", "max_tokens": 10},
        ]
        for item in examples:
            with self.subTest(item=item), self.assertRaises(ValueError):
                validate_inference_request(item)

    def test_motor_local_real_retorna_resultado_sem_enviar_para_nuvem(self):
        fake = FakeRouter()
        result = IrisLocalInferenceExecutor(fake).execute(request())
        self.assertEqual(result["content"], "Eu estou aqui.")
        self.assertEqual(len(fake.calls), 1)
        self.assertIs(fake.calls[0]["allow_external"], False)
        self.assertEqual(fake.calls[0]["data_classification"], "private")
        self.assertEqual(fake.calls[0]["max_tokens"], 96)

    def test_motor_remoto_nao_autorizado_ou_indisponivel_falha(self):
        for fake in (
            FakeRouter(active=False),
            FakeRouter(offline=False),
            FakeRouter(remote=True),
            FakeRouter(status="indisponivel"),
            FakeRouter(content=""),
        ):
            with self.subTest(config=fake.config, status=fake.status):
                with self.assertRaises((IrisInferenceUnavailable, ValueError)):
                    IrisLocalInferenceExecutor(fake).execute(request())

    def test_nao_permite_resultado_com_tool_calls(self):
        with self.assertRaises(ValueError):
            validate_inference_result({
                "content": "resposta", "model": "local",
                "tool_calls": [{"name": "shell.exec"}],
            })

    def test_nos_com_inferencia_sao_selecionados_na_mesma_iris(self):
        a = self.pair(self.user)
        b = self.pair(self.user)
        outsider = self.pair(self.other)
        one = self.submit(self.user, "Primeira pergunta")
        two = self.submit(self.user, "Segunda pergunta")
        self.assertTrue(one["submitted"])
        ticket_a = self.broker.claim(a["node_id"], a["node_token"])
        ticket_b = self.broker.claim(b["node_id"], b["node_token"])
        self.assertEqual(
            {ticket_a["job_id"], ticket_b["job_id"]},
            {one["job_id"], two["job_id"]},
        )
        self.assertEqual(self.broker.claim(
            outsider["node_id"], outsider["node_token"],
        )["status"], "idle")
        for node, ticket in ((a, ticket_a), (b, ticket_b)):
            result = IrisLocalInferenceExecutor(FakeRouter()).execute(ticket["payload"])
            receipt = self.broker.complete(
                node["node_id"], node["node_token"], job_id=ticket["job_id"],
                lease_token=ticket["lease_token"], result=result,
            )
            self.assertFalse(receipt["verified"])
        with self.assertRaises(PermissionError):
            self.broker.inspect(self.other["instance_id"], self.other["token"],
                                job_id=one["job_id"])
        saved = self.broker.inspect(
            self.user["instance_id"], self.user["token"], job_id=one["job_id"],
        )
        self.assertEqual(saved["result"]["content"], "Eu estou aqui.")

    def test_no_sem_inferencia_nao_recebe_prompt(self):
        ordinary = self.pair(self.user, {"compute.light"})
        inferred = self.pair(self.user, {"compute.infer"})
        self.submit(self.user, "Somente no de inferencia")
        self.assertEqual(self.broker.claim(
            ordinary["node_id"], ordinary["node_token"],
        )["status"], "idle")
        self.assertEqual(self.broker.claim(
            inferred["node_id"], inferred["node_token"],
        )["status"], "leased")

    def test_malha_reiniciada_enfileira_antes_de_heartbeat(self):
        node = self.pair(self.user)
        self.now += 91  # O estado restaurado considera o agente offline.
        devices = self.mesh.devices(self.user["instance_id"], self.user["token"])
        self.assertFalse(devices[0]["connected"])
        job = self.submit(self.user, "Voltei do desligamento")
        self.assertTrue(job["submitted"])
        ticket = self.broker.claim(node["node_id"], node["node_token"])
        self.assertEqual(ticket["job_id"], job["job_id"])
        self.assertTrue(self.mesh.devices(
            self.user["instance_id"], self.user["token"],
        )[0]["connected"])

    def test_expiracao_da_lease_reentrega_a_segundo_no(self):
        a = self.pair(self.user)
        b = self.pair(self.user)
        job = self.submit(self.user)
        first = self.broker.claim(a["node_id"], a["node_token"])
        self.now += 46
        after = self.broker.claim(b["node_id"], b["node_token"])
        self.assertEqual(first["job_id"], after["job_id"])
        self.assertNotEqual(first["lease_token"], after["lease_token"])
        with self.assertRaises(PermissionError):
            self.broker.complete(
                a["node_id"], a["node_token"],
                job_id=first["job_id"], lease_token=first["lease_token"],
                result={"content": "invalido", "model": "teste"},
            )

    def test_executor_worker_sem_backend_nao_finge_resposta(self):
        node = self.pair(self.user)
        job = self.submit(self.user)
        class StubWorker(IrisNodeWorker):
            def _post(self, path, payload=None):
                if path.endswith("/claim"):
                    return self.broker.claim(node["node_id"], node["node_token"])
                raise AssertionError("Nao deveria confirmar sem modelo.")
        worker = StubWorker(
            "http://localhost", node["node_id"], node["node_token"],
            inference_executor=IrisLocalInferenceExecutor(FakeRouter(active=False)),
        )
        worker.broker = self.broker
        with self.assertRaises(IrisInferenceUnavailable):
            worker.run_once()
        self.assertEqual(self.broker.inspect(
            self.user["instance_id"], self.user["token"], job_id=job["job_id"],
        )["status"], "leased")

    def test_worker_conversa_por_api_do_broker_e_devolve_resposta(self):
        node = self.pair(self.user)
        job = self.submit(self.user)
        class LocalWorker(IrisNodeWorker):
            def _post(self, path, payload=None):
                if path.endswith("/claim"):
                    return self.broker.claim(node["node_id"], node["node_token"])
                if path.endswith("/complete"):
                    return self.broker.complete(
                        node["node_id"], node["node_token"],
                        job_id=payload["job_id"],
                        lease_token=payload["lease_token"],
                        result=payload["result"],
                    )
                raise AssertionError("Rota proibida.")
        worker = LocalWorker(
            "http://localhost", node["node_id"], node["node_token"],
            inference_executor=IrisLocalInferenceExecutor(FakeRouter()),
        )
        worker.broker = self.broker
        result = worker.run_once()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(self.broker.inspect(
            self.user["instance_id"], self.user["token"],
            job_id=job["job_id"],
        )["result"]["content"], "Eu estou aqui.")


if __name__ == "__main__":
    unittest.main()
