"""Unit tests for the deterministic semantic memory layer."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from memory_system.semantic_memory import SemanticMemory


def make_storage_path(name: str) -> Path:
    return PROJECT_ROOT / "tests" / "_semantic_memory_artifacts" / f"{name}.json"


class SemanticMemoryTests(unittest.TestCase):
    def test_add_entry_stores_required_fields(self) -> None:
        storage_path = make_storage_path("add_entry")
        memory = SemanticMemory(storage_path=storage_path)

        entry = memory.add_entry(
            content="Quarterly cash flow review",
            domain="finance",
            tags=["finance", "cashflow"],
            source="unit-test",
            importance=7,
            metadata={"task_id": "finance-1"},
        )

        self.assertEqual(entry["id"], "memory-0001")
        self.assertEqual(entry["domain"], "finance")
        self.assertEqual(entry["tags"], ["finance", "cashflow"])
        self.assertEqual(entry["source"], "unit-test")
        self.assertEqual(entry["importance"], 7)
        self.assertEqual(entry["metadata"]["task_id"], "finance-1")
        self.assertEqual(len(memory.entries), 1)

    def test_search_returns_most_relevant_entries(self) -> None:
        storage_path = make_storage_path("search")
        memory = SemanticMemory(storage_path=storage_path)

        memory.add_entry(
            content="Quarterly cash flow budget review",
            domain="finance",
            tags=["finance", "cashflow", "budget"],
            source="unit-test",
            importance=8,
            metadata={"task_id": "finance-1"},
        )
        memory.add_entry(
            content="Studio lighting checklist",
            domain="studio",
            tags=["studio", "lighting"],
            source="unit-test",
            importance=5,
            metadata={"task_id": "studio-1"},
        )

        results = memory.search("cash flow budget", limit=2)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["domain"], "finance")
        self.assertGreater(results[0]["score"], 0)

    def test_domain_filtering_returns_only_requested_domain(self) -> None:
        storage_path = make_storage_path("domain")
        memory = SemanticMemory(storage_path=storage_path)

        memory.add_entry(
            content="Study algebra review plan",
            domain="study",
            tags=["study", "algebra", "plan"],
            source="unit-test",
            importance=4,
            metadata={"task_id": "study-1"},
        )
        memory.add_entry(
            content="Finance budget planning",
            domain="finance",
            tags=["finance", "budget", "plan"],
            source="unit-test",
            importance=6,
            metadata={"task_id": "finance-2"},
        )

        results = memory.search("plan", domain="study", limit=5)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["domain"], "study")
        self.assertEqual(memory.get_by_domain("study")[0]["metadata"]["task_id"], "study-1")

    def test_persistence_roundtrip_restores_entries_and_facts(self) -> None:
        storage_path = make_storage_path("persistence")
        memory = SemanticMemory(storage_path=storage_path)

        memory.add_entry(
            content="Runtime initialized successfully",
            domain="system",
            tags=["runtime", "status"],
            source="unit-test",
            importance=5,
            metadata={"event": "bootstrap"},
        )
        memory.upsert(
            "runtime_status",
            "initialized",
            domain="system",
            tags=["runtime", "status"],
            source="unit-test",
            importance=5,
            metadata={"event": "bootstrap"},
        )

        stored_payload: dict[str, str] = {}

        def fake_write_text(_path: Path, text: str, encoding: str = "utf-8") -> int:
            stored_payload["text"] = text
            return len(text)

        def fake_read_text(_path: Path, encoding: str = "utf-8") -> str:
            return stored_payload["text"]

        path_type = type(memory.storage_path)

        with (
            patch.object(path_type, "write_text", autospec=True, side_effect=fake_write_text),
            patch.object(path_type, "exists", autospec=True, return_value=True),
            patch.object(path_type, "read_text", autospec=True, side_effect=fake_read_text),
        ):
            snapshot = memory.snapshot()

            restored_memory = SemanticMemory(storage_path=storage_path)
            restored_snapshot = restored_memory.load_snapshot()

        self.assertEqual(snapshot["entry_count"], 2)
        self.assertEqual(restored_snapshot["entry_count"], 2)
        self.assertEqual(restored_memory.get("runtime_status"), "initialized")
        self.assertEqual(restored_memory.search("runtime initialized")[0]["domain"], "system")
        self.assertEqual(SemanticMemory().storage_path.name, "semantic_memory_store.json")


if __name__ == "__main__":
    unittest.main()
