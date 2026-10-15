from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from memory_system.semantic_cache_engine import (
    SemanticCacheConfig,
    SemanticCacheEngine,
)


class FakeVectorBackend:
    def __init__(self, score: float = 0.95) -> None:
        self.score = score
        self.entry_id = None
        self.available = True

    def upsert(self, entry):
        self.entry_id = str(entry["id"])
        return True

    def search(self, query: str, domain: str, limit: int = 3):
        if self.entry_id is None:
            return []
        return [(self.entry_id, self.score)]

    def status(self):
        return {
            "configured": True,
            "active": True,
            "backend": "fake",
        }


class SemanticCacheEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.tmp.name) / "semantic_cache.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_exact_cache_works_without_any_model(self) -> None:
        config = SemanticCacheConfig(
            vector_enabled=False,
            embedding_model=None,
        )
        engine = SemanticCacheEngine(
            storage_path=self.cache_path,
            config=config,
        )
        engine.put("Qual e o status?", {"status": "ok"}, domain="runtime")

        result = engine.get("  QUAL E O STATUS? ", domain="runtime")

        self.assertEqual(result, {"status": "ok"})
        stats = engine.get_stats()
        self.assertEqual(stats["hits_exatos"], 1)
        self.assertEqual(stats["hits_vetoriais"], 0)
        self.assertFalse(stats["modelo_selecionado_pelo_sistema"])

    def test_without_model_similar_text_does_not_fake_semantic_hit(self) -> None:
        config = SemanticCacheConfig(
            vector_enabled=True,
            embedding_model=None,
        )
        engine = SemanticCacheEngine(
            storage_path=self.cache_path,
            config=config,
        )
        engine.put(
            "resuma o relatorio financeiro",
            {"resultado": "A"},
            domain="finance",
        )

        result = engine.get(
            "pode resumir o relatorio das financas?",
            domain="finance",
        )

        self.assertIsNone(result)
        stats = engine.get_stats()
        self.assertEqual(stats["hits_vetoriais"], 0)
        self.assertEqual(stats["misses"], 1)
        self.assertFalse(stats["cache_vetorial"]["configured"])

    def test_real_vector_contract_can_hit_when_backend_is_configured(self) -> None:
        backend = FakeVectorBackend(score=0.96)
        config = SemanticCacheConfig(
            vector_enabled=True,
            embedding_model="configured-by-owner",
            similarity_threshold=0.90,
        )
        engine = SemanticCacheEngine(
            storage_path=self.cache_path,
            config=config,
            vector_backend=backend,
        )
        engine.put(
            "qual a capital do brasil?",
            {"resposta": "Brasilia"},
            domain="knowledge",
        )

        result = engine.get(
            "me diga a capital brasileira",
            domain="knowledge",
        )

        self.assertEqual(result, {"resposta": "Brasilia"})
        stats = engine.get_stats()
        self.assertEqual(stats["hits_vetoriais"], 1)

    def test_vector_result_below_threshold_is_a_miss(self) -> None:
        backend = FakeVectorBackend(score=0.71)
        config = SemanticCacheConfig(
            vector_enabled=True,
            embedding_model="configured-by-owner",
            similarity_threshold=0.90,
        )
        engine = SemanticCacheEngine(
            storage_path=self.cache_path,
            config=config,
            vector_backend=backend,
        )
        engine.put("consulta original", {"resposta": 1})

        self.assertIsNone(engine.get("consulta diferente"))
        self.assertEqual(engine.get_stats()["misses"], 1)

    def test_stats_do_not_claim_unmeasured_token_savings(self) -> None:
        engine = SemanticCacheEngine(
            storage_path=self.cache_path,
            config=SemanticCacheConfig(),
        )
        engine.put(
            "teste",
            {"ok": True},
            tokens_saved_estimate=999999,
        )
        stats = engine.get_stats()

        self.assertNotIn("estimativa_tokens_economizados", stats)
        self.assertNotIn("taxa_eficiencia", stats)

    def test_cache_persists_entries_and_observed_stats(self) -> None:
        config = SemanticCacheConfig()
        engine = SemanticCacheEngine(
            storage_path=self.cache_path,
            config=config,
        )
        engine.put("persistir", {"valor": 42})
        self.assertEqual(engine.get("persistir"), {"valor": 42})

        reloaded = SemanticCacheEngine(
            storage_path=self.cache_path,
            config=config,
        )

        self.assertEqual(reloaded.get("persistir"), {"valor": 42})
        self.assertEqual(reloaded.get_stats()["hits_exatos"], 2)


if __name__ == "__main__":
    unittest.main()
