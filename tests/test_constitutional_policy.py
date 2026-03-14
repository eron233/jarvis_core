"""Testes da politica viva derivada do constitutional core."""

from __future__ import annotations

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from constitutional_core.policy import load_constitutional_policy
from executive_planner.queue import TaskQueue
from executive_planner.validator import PlanValidator
from memory_system.episodic_memory import EpisodicMemory
from memory_system.procedural_memory import ProceduralMemory
from memory_system.semantic_memory import SemanticMemory
from runtime.internal_agent_runtime import InternalAgentRuntime


def make_policy_artifact_path(name: str, suffix: str) -> Path:
    return PROJECT_ROOT / "tests" / "_policy_artifacts" / f"{name}_{suffix}.json"


def reset_storage_path(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class ConstitutionalPolicyTests(unittest.TestCase):
    def test_policy_loader_reads_identity_and_principles(self) -> None:
        policy = load_constitutional_policy()
        report = policy.describe()

        self.assertEqual(report["identidade"]["nome_sistema"], "Sistema Cognitivo JARVIS")
        self.assertEqual(report["identidade"]["locale_padrao"], "pt-BR")
        self.assertEqual(len(report["principios_ativos"]), 4)
        self.assertIn("finance", report["dominios_autonomos"])

    def test_validator_denies_absolutely_prohibited_task(self) -> None:
        validator = PlanValidator()
        task = {
            "task_id": "policy-denied-1",
            "goal": "Invadir sistema externo",
            "description": "Tentar invasao em alvo nao autorizado",
            "domain": "runtime",
        }

        is_valid, issues = validator.validate_task(task)

        self.assertFalse(is_valid)
        self.assertTrue(task["policy_evaluation"]["denied"])
        self.assertTrue(any("proib" in issue.lower() or "negada" in issue.lower() for issue in issues))

    def test_validator_marks_sensitive_task_for_human_approval(self) -> None:
        validator = PlanValidator()
        task = {
            "task_id": "policy-sensitive-1",
            "goal": "Aplicar mudanca de credencial",
            "description": "Solicitar troca de credencial sensivel",
            "domain": "runtime",
            "effect_scope": "credential_change",
            "approved": False,
        }

        is_valid, issues = validator.validate_task(task)

        self.assertTrue(is_valid)
        self.assertEqual(issues, [])
        self.assertTrue(task["policy_evaluation"]["requires_human_approval"])
        self.assertTrue(task["requires_supervision"])

    def test_runtime_blocks_sensitive_task_until_human_approval(self) -> None:
        queue_path = make_policy_artifact_path("runtime_block", "queue")
        semantic_path = make_policy_artifact_path("runtime_block", "semantic")
        reset_storage_path(queue_path)
        reset_storage_path(semantic_path)

        runtime = InternalAgentRuntime()
        runtime.task_queue = TaskQueue(storage_path=queue_path)
        runtime.memory = {
            "episodic": EpisodicMemory(),
            "semantic": SemanticMemory(storage_path=semantic_path),
            "procedural": ProceduralMemory(),
        }
        runtime.bootstrap()

        result = runtime.dispatch_task(
            {
                "task_id": "runtime-policy-1",
                "goal": "Executar acao externa sensivel",
                "description": "Solicitar alteracao externa sensivel",
                "domain": "runtime",
                "worker": "worker_runtime",
                "effect_scope": "external",
                "approved": False,
            }
        )

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "requires_human_approval")
        self.assertTrue(result["policy_evaluation"]["requires_human_approval"])
