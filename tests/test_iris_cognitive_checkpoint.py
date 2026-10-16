"""Checkpoint de memorias cognitivas reais replicado entre dois stores."""
import secrets
import tempfile
from pathlib import Path
import unittest

from device.iris_mesh import IrisDeviceMesh
from device.iris_state_replication import IrisReplicaSource, IrisReplicaSink
from memory_system.iris_state_store import IrisEncryptedStateStore, StateConflictError
from memory_system.semantic_memory import SemanticMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.episodic_memory import EpisodicMemory
from runtime.cognitive_evolution import CognitiveEvolutionTracker
from runtime.iris_cognitive_checkpoint import IrisCognitiveCheckpoint
from security.iris_instance_policy import IrisInstanceAuthority


class IrisCognitiveCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.secret = secrets.token_urlsafe(32)
        self.auth = IrisInstanceAuthority(self.secret)
        self.alice = {"instance_id": self.auth.OWNER_ID, "token": self.secret}
        self.bob = self.auth.create_resident(
            self.secret, tenant_id="tenant-bob", display_name="Iris Bob",
            user_consented=True,
        )
        self.first = IrisEncryptedStateStore(
            self.root / "first.db", self.auth, root_key=secrets.token_bytes(32),
        )
        self.second = IrisEncryptedStateStore(
            self.root / "second.db", self.auth, root_key=secrets.token_bytes(32),
        )
        self.mesh = IrisDeviceMesh(self.auth)
        offer = self.mesh.offer_device(
            device_name="Notebook", device_type="linux",
            surfaces={"memory.sync"}, locally_approved=True,
        )
        self.node = self.mesh.approve_offer(
            self.alice["instance_id"], self.alice["token"],
            offer_id=offer["offer_id"],
            verification_code=offer["verification_code"],
        )

    def tearDown(self):
        self.first.close()
        self.second.close()
        self.tmp.cleanup()

    def components(self, name):
        return {
            "semantic": SemanticMemory(storage_path=self.root / f"{name}-semantic.json"),
            "procedural": ProceduralMemory(storage_path=None),
            "episodic": EpisodicMemory(storage_path=None),
            "evolution": CognitiveEvolutionTracker(storage_path=None, auto_persist=False),
        }

    def test_memoria_real_sobrevive_sem_gravar_json_aberto(self):
        modules = self.components("a")
        modules["semantic"].upsert("preferencia", "padrão Arcane")
        modules["episodic"].remember({
            "evento": "conversa", "detalhe": "a Iris aprende aos poucos",
        })
        snapshot = IrisCognitiveCheckpoint(
            self.first, self.alice["instance_id"], self.alice["token"],
            components=modules,
        )
        self.assertEqual(snapshot.capture(expected_revision=0)["revision"], 1)
        self.assertFalse((self.root / "a-semantic.json").exists())
        source = IrisReplicaSource(
            self.mesh, self.first, source_id="iris-source-cognitive-001",
        )
        sink = IrisReplicaSink(
            self.second, node_id=self.node["node_id"],
            node_token=self.node["node_token"],
            instance_id=self.alice["instance_id"],
            source_id="iris-source-cognitive-001",
        )
        sink.apply(source.document(
            self.node["node_id"], self.node["node_token"],
            "cognitive.checkpoint",
        ))
        modules_other = self.components("b")
        recovered = IrisCognitiveCheckpoint(
            self.second, self.alice["instance_id"], self.alice["token"],
            components=modules_other,
        )
        status = recovered.restore()
        self.assertTrue(status["restored"])
        self.assertEqual(status["revision"], 1)
        self.assertEqual(modules_other["semantic"].facts["preferencia"],
                         "padrão Arcane")
        self.assertEqual(
            modules_other["episodic"].episodes[0]["evento"], "conversa",
        )
        self.assertFalse((self.root / "b-semantic.json").exists())
        with self.assertRaises(StateConflictError):
            snapshot.capture(expected_revision=0)

    def test_outro_tenant_nao_recupera_memoria_alheia(self):
        source = self.components("private")
        source["episodic"].remember({"texto": "somente Alice"})
        IrisCognitiveCheckpoint(
            self.first, self.alice["instance_id"], self.alice["token"],
            components=source,
        ).capture(expected_revision=0)
        with self.assertRaises(PermissionError):
            IrisCognitiveCheckpoint(
                self.first, self.alice["instance_id"], self.bob["token"],
                components=self.components("fake"),
            )
        result = IrisCognitiveCheckpoint(
            self.first, self.bob["instance_id"], self.bob["token"],
            components=self.components("other"),
        ).restore()
        self.assertFalse(result["restored"])

    def test_checkpoint_grande_demais_e_rejeitado_sem_perda(self):
        modules = self.components("huge")
        modules["episodic"].remember({"texto": "X" * 70000})
        package = IrisCognitiveCheckpoint(
            self.first, self.alice["instance_id"], self.alice["token"],
            components=modules,
        )
        with self.assertRaises(ValueError):
            package.capture(expected_revision=0)
        self.assertFalse(self.first.get(
            self.alice["instance_id"], self.alice["token"],
            "cognitive.checkpoint",
        )["found"])


if __name__ == "__main__":
    unittest.main()
