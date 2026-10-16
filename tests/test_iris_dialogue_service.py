"""Conversas cifradas no mesmo contexto Iris, roteadas a um no de IA."""
from __future__ import annotations

import secrets
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest

from device.iris_inference_tasks import IrisLocalInferenceExecutor
from device.iris_mesh import IrisDeviceMesh
from device.iris_task_broker import IrisTaskBroker
from memory_system.iris_state_store import IrisEncryptedStateStore, StateConflictError
from runtime.iris_dialogue_service import IrisDialogueService
from security.iris_instance_policy import IrisInstanceAuthority


class FakeLocalModel:
    def __init__(self):
        self.config = SimpleNamespace(
            enabled=True, offline_mode=True, allow_remote_endpoints=False,
        )
        self.messages = []

    def chat(self, *, messages, tier, max_tokens, allow_external, data_classification):
        self.messages.append(messages)
        if allow_external or data_classification != "private":
            raise AssertionError("Privacidade desativada")
        return {
            "status": "sucesso", "conteudo": f"Resposta {len(self.messages)}",
            "modelo": "modelo-local-real-configurado-em-producao",
        }


class IrisDialogueServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "encrypted.sqlite3"
        self.key = secrets.token_bytes(32)
        self.secret = secrets.token_urlsafe(32)
        self.auth = IrisInstanceAuthority(self.secret)
        self.alice = {"instance_id": self.auth.OWNER_ID, "token": self.secret}
        self.bob = self.auth.create_resident(
            self.secret, tenant_id="conta-bob", display_name="Iris Bob",
            user_consented=True,
        )
        self.mesh = IrisDeviceMesh(self.auth)
        self.broker = IrisTaskBroker(self.mesh)
        self.store = IrisEncryptedStateStore(
            self.path, self.auth, root_key=self.key,
        )
        self.service = IrisDialogueService(self.broker, self.store)
        self.model = FakeLocalModel()
        self.executor = IrisLocalInferenceExecutor(self.model)
        offer = self.mesh.offer_device(
            device_name="Notebook autorizado", device_type="windows",
            surfaces={"compute.infer"}, locally_approved=True,
        )
        self.node = self.mesh.approve_offer(
            self.alice["instance_id"], self.alice["token"],
            offer_id=offer["offer_id"],
            verification_code=offer["verification_code"],
        )

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def perform_one(self):
        job = self.broker.claim(self.node["node_id"], self.node["node_token"])
        self.assertEqual(job["status"], "leased")
        answer = self.executor.execute(job["payload"])
        return self.broker.complete(
            self.node["node_id"], self.node["node_token"],
            job_id=job["job_id"], lease_token=job["lease_token"], result=answer,
        )

    def start(self, text="Oi Iris", who=None):
        user = who or self.alice
        return self.service.start(
            user["instance_id"], user["token"],
            conversation_id="minha-conversa", text=text,
        )

    def finish(self, who=None):
        user = who or self.alice
        return self.service.finish(
            user["instance_id"], user["token"],
            conversation_id="minha-conversa",
        )

    def test_conversa_real_persiste_e_proximo_turno_recupera_contexto(self):
        job = self.start("Olá!")
        self.assertEqual(job["status"], "queued")
        # A resposta so se torna parte da memoria apos confirmacao do executor.
        self.assertEqual(self.service.history(
            self.alice["instance_id"], self.alice["token"],
            conversation_id="minha-conversa",
        )["turns"], [])
        self.perform_one()
        replied = self.finish()
        self.assertEqual(replied["content"], "Resposta 1")
        second = self.start("Você lembra?")
        self.assertTrue(second["submitted"])
        self.perform_one()
        self.finish()
        self.assertEqual(len(self.model.messages), 2)
        self.assertEqual(self.model.messages[1][0],
                         {"role": "user", "content": "Olá!"})
        self.assertEqual(self.model.messages[1][1]["role"], "assistant")
        self.assertEqual(self.model.messages[1][-1]["content"], "Você lembra?")
        old = self.store
        old.close()
        self.store = IrisEncryptedStateStore(self.path, self.auth, root_key=self.key)
        recovered = IrisDialogueService(self.broker, self.store)
        history = recovered.history(
            self.alice["instance_id"], self.alice["token"],
            conversation_id="minha-conversa",
        )
        self.assertEqual(history["revision"], 4)
        self.assertEqual(len(history["turns"]), 4)
        self.assertFalse(history["has_pending"])

    def test_isolamento_de_residente_e_administrador(self):
        self.start("Esta conversa é particular.")
        self.perform_one()
        self.finish()
        history_bob = self.service.history(
            self.bob["instance_id"], self.bob["token"],
            conversation_id="minha-conversa",
        )
        self.assertEqual(history_bob["turns"], [])
        with self.assertRaises(PermissionError):
            self.service.history(
                self.alice["instance_id"], self.bob["token"],
                conversation_id="minha-conversa",
            )
        # A Original acessa apenas a propria conversa, nunca a do residente.
        owner_history = self.service.history(
            IrisInstanceAuthority.OWNER_ID, self.secret,
            conversation_id="minha-conversa",
        )
        self.assertEqual(len(owner_history["turns"]), 2)

    def test_turno_pendente_nao_aceita_sobrescrita(self):
        first = self.start()
        with self.assertRaises(StateConflictError):
            self.start("Segundo sem esperar")
        self.perform_one()
        self.assertEqual(self.finish()["status"], "completed")
        self.assertEqual(self.finish()["status"], "idle")

    def test_sem_modelo_ou_no_disponivel_nao_inventa_chat(self):
        self.mesh.disconnect(
            self.alice["instance_id"], self.alice["token"],
            node_id=self.node["node_id"],
        )
        self.assertEqual(self.start()["status"], "unavailable")
        self.assertEqual(self.service.history(
            self.alice["instance_id"], self.alice["token"],
            conversation_id="minha-conversa",
        )["revision"], 0)

    def test_identificador_invalido_ou_mensagem_extensa(self):
        with self.assertRaises(ValueError):
            self.service.start(self.alice["instance_id"], self.alice["token"],
                               conversation_id="../private", text="hello")
        with self.assertRaises(ValueError):
            self.start("x" * 801)


if __name__ == "__main__":
    unittest.main()
