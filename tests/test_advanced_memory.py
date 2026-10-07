"""Testes da camada avancada de memoria do JARVIS."""

from pathlib import Path
import tempfile
import unittest

from memory_system.advanced_memory import AdvancedMemoryConfig
from memory_system.episodic_memory import EpisodicMemory
from memory_system.semantic_memory import SemanticMemory


class _FakeMem0:
    def remember(self, messages, user_id=None, metadata=None):
        return {"status": "sucesso", "resultado": {"messages": messages, "user_id": user_id}}

    def recall(self, query, user_id=None):
        return {"status": "sucesso", "results": [{"memory": query, "user_id": user_id}]}


class _FakeAdvancedRetriever:
    def __init__(self):
        self.indexed = []
        self.mem0 = _FakeMem0()

    def index_entry(self, entry):
        self.indexed.append(entry["id"])
        return True

    def rebuild(self, entries):
        self.indexed.extend(entry["id"] for entry in entries)
        return len(entries)

    def search(self, query, entries_by_id, domain=None, limit=5):
        selected = None
        for entry in entries_by_id.values():
            if domain is None or entry["domain"] == domain:
                selected = entry
                if "preferida" in entry["content"].lower():
                    break
        if selected is None:
            return []
        return [{
            "entry": selected,
            "score": 0.95,
            "vector_score": 0.93,
            "rerank_score": 0.97,
        }]

    def status(self):
        return {
            "enabled": True,
            "vector_available": True,
            "mem0_available": True,
            "fallback": "deterministic_token_search",
        }


class AdvancedMemoryTests(unittest.TestCase):
    def test_config_is_safe_and_disabled_by_default(self):
        config = AdvancedMemoryConfig.from_env(environ={}, project_root=Path("."))
        self.assertFalse(config.enabled)
        self.assertFalse(config.mem0_enabled)
        self.assertEqual(config.embedding_model, "Qwen/Qwen3-Embedding-0.6B")
        self.assertEqual(config.reranker_model, "Qwen/Qwen3-Reranker-0.6B")

    def test_config_reads_advanced_memory_environment(self):
        config = AdvancedMemoryConfig.from_env(
            environ={
                "JARVIS_ADVANCED_MEMORY_ENABLED": "true",
                "JARVIS_MEM0_ENABLED": "true",
                "JARVIS_VECTOR_TOP_K": "12",
                "JARVIS_QDRANT_COLLECTION": "teste_memoria",
            },
            project_root=Path("."),
        )
        self.assertTrue(config.enabled)
        self.assertTrue(config.mem0_enabled)
        self.assertEqual(config.vector_top_k, 12)
        self.assertEqual(config.qdrant_collection, "teste_memoria")

    def test_semantic_memory_uses_advanced_retrieval_when_available(self):
        fake = _FakeAdvancedRetriever()
        memory = SemanticMemory(
            storage_path=Path("unused.json"),
            advanced_retriever=fake,
        )
        memory.add_entry(
            "Memoria secundaria sobre compras",
            domain="personal",
            importance=1,
        )
        preferred = memory.add_entry(
            "Memoria preferida sobre arquitetura do Jarvis",
            domain="personal",
            importance=5,
        )

        results = memory.search("arquitetura cognitiva", domain="personal", limit=1)

        self.assertEqual(results[0]["id"], preferred["id"])
        self.assertEqual(results[0]["retrieval"]["mode"], "hybrid_vector_qwen")
        self.assertEqual(fake.indexed, ["memory-0001", "memory-0002"])

    def test_semantic_memory_keeps_deterministic_fallback(self):
        memory = SemanticMemory(
            storage_path=Path("unused.json"),
            advanced_retriever=None,
        )
        # Impede auto-configuracao para isolar o fallback no teste.
        memory.advanced_retriever = False
        memory.add_entry("fluxo de caixa mensal", domain="finance")
        results = memory.search("fluxo caixa", domain="finance")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["retrieval"]["mode"], "deterministic_token_search")

    def test_mem0_bridge_is_exposed_through_semantic_memory(self):
        memory = SemanticMemory(
            storage_path=Path("unused.json"),
            advanced_retriever=_FakeAdvancedRetriever(),
        )
        remembered = memory.remember_conversation(
            [{"role": "user", "content": "Meu projeto usa Qdrant."}],
            user_id="eron",
        )
        recalled = memory.recall_conversation("Qdrant", user_id="eron")
        self.assertEqual(remembered["status"], "sucesso")
        self.assertEqual(recalled["status"], "sucesso")
        self.assertEqual(recalled["results"][0]["user_id"], "eron")

    def test_episodic_memory_survives_restart(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "episodic.json"
            memory = EpisodicMemory(storage_path=path, auto_persist=True)
            memory.remember({"event": "bootstrap", "status": "ok"})
            memory.remember({"event": "command", "text": "status"})

            restored = EpisodicMemory(storage_path=path)
            snapshot = restored.load_snapshot()

            self.assertEqual(snapshot["episode_count"], 2)
            self.assertEqual(restored.recent(1)[0]["event"], "command")


if __name__ == "__main__":
    unittest.main()
