"""Testes do modulo de autodefesa operacional do Jarvis."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from device.device_registry import DeviceRegistry
from executive_planner.queue import TaskQueue
from intent_layer.goal_manager import GoalManager
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime
from security.remediation_engine import RemediationEngine
from security.self_defense import SelfDefenseMonitor
from security.security_twin import SecurityTwin
from security.security_validation_engine import SecurityValidationEngine


def make_security_artifact_path(name: str, suffix: str) -> Path:
    """Retorna o path isolado usado nos testes do modulo de autodefesa."""

    return PROJECT_ROOT / "tests" / "_security_artifacts" / f"{name}_{suffix}.json"


def reset_storage_path(path: Path) -> None:
    """Limpa o artefato antes da execucao do teste."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class SelfDefenseTests(unittest.TestCase):
    """Valida o autodiagnostico defensivo integrado ao runtime."""

    def test_runtime_runs_self_defense_audit_and_persists_report(self) -> None:
        """Confirma que o runtime executa o autodiagnostico e salva o relatorio."""

        queue_path = make_security_artifact_path("self_defense", "queue")
        semantic_path = make_security_artifact_path("self_defense", "semantic")
        procedural_path = make_security_artifact_path("self_defense", "procedural")
        goals_path = make_security_artifact_path("self_defense", "goals")
        device_path = make_security_artifact_path("self_defense", "devices")
        report_path = make_security_artifact_path("self_defense", "report")
        twin_dir = PROJECT_ROOT / "tests" / "_security_artifacts" / "twin"
        for path in (queue_path, semantic_path, procedural_path, goals_path, device_path, report_path):
            reset_storage_path(path)

        runtime = InternalAgentRuntime()
        runtime.task_queue = TaskQueue(storage_path=queue_path)
        runtime.goal_manager = GoalManager(storage_path=goals_path)
        runtime.device_registry = DeviceRegistry(storage_path=device_path)
        runtime.memory = {
            "episodic": EpisodicMemory(),
            "semantic": SemanticMemory(storage_path=semantic_path),
            "procedural": ProceduralMemory(storage_path=procedural_path),
        }

        twin = SecurityTwin(storage_dir=twin_dir)
        runtime.self_defense_monitor = SelfDefenseMonitor(
            security_twin=twin,
            validation_engine=SecurityValidationEngine(twin=twin),
            remediation_engine=RemediationEngine(twin=twin),
            report_path=report_path,
        )

        report = runtime.run_self_defense_audit(
            environment_report={
                "host_api": "127.0.0.1",
                "porta_api": 8000,
                "painel_ativo": True,
                "autenticacao_configurada": {
                    "token_configurado": True,
                    "dispositivo_confiavel_configurado": True,
                },
            }
        )

        self.assertIn("modelo_ameaca", report)
        self.assertIn("validacao_controlada", report)
        self.assertIn("remediacao", report)
        self.assertTrue(report_path.exists())


if __name__ == "__main__":
    unittest.main()
