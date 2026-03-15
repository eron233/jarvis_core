"""Testes unitarios para o historico de evolucao cognitiva do JARVIS."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.cognitive_evolution import CognitiveEvolutionTracker


def make_cognitive_storage_path(name: str) -> Path:
    """Retorna o path isolado usado nos testes do mapa evolutivo."""

    return PROJECT_ROOT / "tests" / "_cognitive_evolution_artifacts" / f"{name}.json"


def reset_storage_path(path: Path) -> None:
    """Limpa o artefato persistente antes de cada cenario."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class CognitiveEvolutionTrackerTests(unittest.TestCase):
    """Valida persistencia, visualizacao e analise do historico cognitivo."""

    def test_record_event_and_roundtrip_persistence(self) -> None:
        """Confirma que eventos evolutivos sao persistidos e recarregados sem perda."""

        storage_path = make_cognitive_storage_path("roundtrip")
        reset_storage_path(storage_path)
        tracker = CognitiveEvolutionTracker(storage_path=storage_path)

        event = tracker.record_event(
            event_type="EVENT_NEW_KNOWLEDGE",
            region="study",
            connections_created=3,
            connections_strengthened=2,
            estimated_cognitive_impact=0.74,
            metadata={"source": "test"},
        )
        snapshot = tracker.snapshot()

        self.assertTrue(storage_path.exists())
        self.assertEqual(snapshot["event_count"], 1)
        self.assertEqual(event["regiao_cerebral"], "rede_neural_procedural")

        reloaded_tracker = CognitiveEvolutionTracker(storage_path=storage_path)
        reloaded_snapshot = reloaded_tracker.load_snapshot()
        self.assertEqual(reloaded_snapshot["event_count"], 1)
        self.assertEqual(reloaded_tracker.events[0]["tipo_evento"], "EVENT_NEW_KNOWLEDGE")
        self.assertEqual(reloaded_tracker.events[0]["metadata"]["source"], "test")

    def test_visualization_and_analysis_support_temporal_levels(self) -> None:
        """Verifica que o tracker filtra niveis temporais e gera analise util."""

        storage_path = make_cognitive_storage_path("levels")
        reset_storage_path(storage_path)
        tracker = CognitiveEvolutionTracker(storage_path=storage_path)
        now = datetime.now(timezone.utc)

        tracker.record_event(
            event_type="EVENT_NETWORK_RESTRUCTURE",
            region="runtime",
            connections_created=4,
            connections_strengthened=2,
            estimated_cognitive_impact=1.2,
            created_at=now.isoformat(),
        )
        tracker.record_event(
            event_type="EVENT_SKILL_IMPROVED",
            region="study",
            connections_created=1,
            connections_strengthened=5,
            estimated_cognitive_impact=1.1,
            created_at=(now - timedelta(days=2)).isoformat(),
        )
        tracker.record_event(
            event_type="EVENT_MEMORY_CONSOLIDATED",
            region="memory",
            connections_created=2,
            connections_strengthened=3,
            estimated_cognitive_impact=0.9,
            created_at=(now - timedelta(days=40)).isoformat(),
        )

        recent_visual = tracker.build_visualization_payload(level="recente")
        historical_visual = tracker.build_visualization_payload(level="historica")
        analysis = tracker.build_analysis(level="historica")

        self.assertEqual(recent_visual["eventos_considerados"], 1)
        self.assertEqual(historical_visual["eventos_considerados"], 3)
        self.assertEqual(historical_visual["nivel"], "historica")
        self.assertGreaterEqual(historical_visual["neuronios_simulados"], 1)
        self.assertTrue(any(region["growth_score"] > 0 for region in historical_visual["regioes"]))
        self.assertIn("regioes_mais_utilizadas", analysis)
        self.assertIn("conexoes_mais_fortes", analysis)
        self.assertGreaterEqual(len(analysis["regioes_mais_utilizadas"]), 1)


if __name__ == "__main__":
    unittest.main()
