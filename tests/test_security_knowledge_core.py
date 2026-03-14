"""Testes unitarios para o nucleo de conhecimento de seguranca do JARVIS."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from security.security_knowledge_core import SecurityKnowledgeCore


class SecurityKnowledgeCoreTests(unittest.TestCase):
    def test_list_domains_exposes_expected_defensive_areas(self) -> None:
        core = SecurityKnowledgeCore()

        domains = core.list_domains()
        domain_ids = [domain["domain_id"] for domain in domains]

        self.assertEqual(len(domains), 5)
        self.assertEqual(
            domain_ids,
            [
                "identity_and_access",
                "application",
                "infrastructure",
                "continuity",
                "observability",
            ],
        )

    def test_get_control_returns_diagnostic_structure(self) -> None:
        core = SecurityKnowledgeCore()

        control = core.get_control("trusted_device_validation")

        self.assertEqual(control["domain_id"], "identity_and_access")
        self.assertIn("sinais_de_risco", control)
        self.assertIn("hipoteses_de_falha", control)
        self.assertIn("perguntas_de_diagnostico", control)
        self.assertGreaterEqual(len(control["perguntas_de_diagnostico"]), 2)

    def test_semantic_and_procedural_seeding_are_deterministic(self) -> None:
        core = SecurityKnowledgeCore()
        semantic_memory = SemanticMemory(storage_path=PROJECT_ROOT / "tests" / "_semantic_memory_artifacts" / "security_core.json")
        semantic_memory.entries = []
        semantic_memory.facts = {}
        procedural_memory = ProceduralMemory()

        result = core.seed_memories(semantic_memory=semantic_memory, procedural_memory=procedural_memory)

        self.assertEqual(result["semantic_entries_added"], core.build_knowledge_snapshot()["total_controles"])
        self.assertEqual(result["procedural_guides_added"], 5)
        self.assertEqual(semantic_memory.entries[0]["domain"], "security")
        self.assertIn("seguranca", semantic_memory.entries[0]["tags"])
        self.assertEqual(
            procedural_memory.get("security_review_identity_and_access"),
            [
                "inventariar ativos e controles relacionados",
                "revisar sinais de risco observados",
                "comparar hipoteses de falha com o estado atual",
                "registrar evidencias auditaveis",
                "escalar apenas o que exigir aprovacao humana",
            ],
        )

    def test_defensive_summary_reports_core_counts(self) -> None:
        core = SecurityKnowledgeCore()

        summary = core.build_defensive_summary()

        self.assertEqual(summary["mensagem"], "Nucleo de conhecimento defensivo carregado.")
        self.assertEqual(summary["idioma"], "pt-BR")
        self.assertEqual(summary["total_controles"], core.build_knowledge_snapshot()["total_controles"])


if __name__ == "__main__":
    unittest.main()
