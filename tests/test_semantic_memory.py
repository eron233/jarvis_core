"""Testes unitarios para a camada deterministica de memoria semantica."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from memory_system.semantic_memory import SemanticMemory


def make_storage_path(name: str) -> Path:
    return PROJECT_ROOT / "tests" / "_semantic_memory_artifacts" / f"{name}.json"


def reset_storage_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class SemanticMemoryTests(unittest.TestCase):
    def test_add_entry_stores_required_fields(self) -> None:
        storage_path = make_storage_path("add_entry")
        reset_storage_path(storage_path)
        memory = SemanticMemory(storage_path=storage_path)

        entry = memory.add_entry(
            content="Revisao trimestral do fluxo de caixa",
            domain="finance",
            tags=["finance", "fluxo_caixa"],
            source="unit-test",
            importance=7,
            metadata={"task_id": "finance-1"},
        )

        self.assertEqual(entry["id"], "memory-0001")
        self.assertEqual(entry["domain"], "finance")
        self.assertEqual(entry["tags"], ["finance", "fluxo_caixa"])
        self.assertEqual(entry["source"], "unit-test")
        self.assertEqual(entry["importance"], 7)
        self.assertEqual(entry["metadata"]["task_id"], "finance-1")
        self.assertEqual(len(memory.entries), 1)

    def test_search_returns_most_relevant_entries(self) -> None:
        storage_path = make_storage_path("search")
        reset_storage_path(storage_path)
        memory = SemanticMemory(storage_path=storage_path)

        memory.add_entry(
            content="Revisao trimestral do fluxo de caixa e do orcamento",
            domain="finance",
            tags=["finance", "fluxo_caixa", "orcamento"],
            source="unit-test",
            importance=8,
            metadata={"task_id": "finance-1"},
        )
        memory.add_entry(
            content="Checklist de iluminacao do estudio",
            domain="studio",
            tags=["studio", "iluminacao"],
            source="unit-test",
            importance=5,
            metadata={"task_id": "studio-1"},
        )

        results = memory.search("fluxo de caixa orcamento", limit=2)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["domain"], "finance")
        self.assertGreater(results[0]["score"], 0)
        self.assertGreater(results[0]["score"], results[1]["score"])

    def test_domain_filtering_returns_only_requested_domain(self) -> None:
        storage_path = make_storage_path("domain")
        reset_storage_path(storage_path)
        memory = SemanticMemory(storage_path=storage_path)

        memory.add_entry(
            content="Plano de revisao de algebra",
            domain="study",
            tags=["study", "algebra", "plano"],
            source="unit-test",
            importance=4,
            metadata={"task_id": "study-1"},
        )
        memory.add_entry(
            content="Planejamento financeiro do orcamento",
            domain="finance",
            tags=["finance", "orcamento", "plano"],
            source="unit-test",
            importance=6,
            metadata={"task_id": "finance-2"},
        )

        results = memory.search("plano", domain="study", limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["domain"], "study")
        self.assertEqual(memory.get_by_domain("study")[0]["metadata"]["task_id"], "study-1")

    def test_persistence_roundtrip_restores_entries_and_facts(self) -> None:
        storage_path = make_storage_path("persistence")
        reset_storage_path(storage_path)
        memory = SemanticMemory(storage_path=storage_path)

        memory.add_entry(
            content="Runtime inicializado com sucesso",
            domain="system",
            tags=["runtime", "estado"],
            source="unit-test",
            importance=5,
            metadata={"event": "bootstrap"},
        )
        memory.upsert(
            "runtime_status",
            "inicializado",
            domain="system",
            tags=["runtime", "estado"],
            source="unit-test",
            importance=5,
            metadata={"event": "bootstrap"},
        )

        snapshot = memory.snapshot()

        restored_memory = SemanticMemory(storage_path=storage_path)
        restored_snapshot = restored_memory.load_snapshot()

        self.assertEqual(snapshot["entry_count"], 2)
        self.assertEqual(restored_snapshot["entry_count"], 2)
        self.assertEqual(restored_memory.get("runtime_status"), "inicializado")
        self.assertEqual(restored_memory.search("runtime inicializado")[0]["domain"], "system")
        self.assertEqual(SemanticMemory().storage_path.name, "semantic_memory_store.json")


if __name__ == "__main__":
    unittest.main()
