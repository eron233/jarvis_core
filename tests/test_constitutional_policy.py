"""Testes da politica viva derivada do constitutional core."""

from __future__ import annotations

from pathlib import Path
import json
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
    """Retorna o path isolado usado nos testes de politica constitucional."""

    return PROJECT_ROOT / "tests" / "_policy_artifacts" / f"{name}_{suffix}.json"


def reset_storage_path(path: Path) -> None:
    """Remove artefatos antigos para iniciar o teste do zero."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


class ConstitutionalPolicyTests(unittest.TestCase):
    """Valida o carregamento e o efeito da politica viva no sistema."""

    def test_policy_loader_reads_identity_and_principles(self) -> None:
        """Confirma leitura da identidade e dos principios constitucionais."""

        policy = load_constitutional_policy()
        report = policy.describe()

        self.assertEqual(report["identidade"]["nome_sistema"], "Sistema Cognitivo JARVIS")
        self.assertEqual(report["identidade"]["locale_padrao"], "pt-BR")
        self.assertEqual(len(report["principios_ativos"]), 4)
        self.assertIn("finance", report["dominios_autonomos"])

    def test_specialized_memory_models_are_protected_from_base_model_policy(self) -> None:
        """Separa modelo-base pendente dos modelos especializados da memoria."""

        constitution_path = PROJECT_ROOT / "constitutional_core" / "technology_constitution.json"
        constitution = json.loads(constitution_path.read_text(encoding="utf-8"))

        self.assertIsNone(constitution["model_policy"]["selected_base_model"])

        specialized = constitution["specialized_model_policy"]
        self.assertIn("not the JARVIS base model", specialized["base_model_distinction"])

        components = {
            item["component"]: item
            for item in specialized["components"]
        }

        for component in (
            "Qwen/Qwen3-Embedding-0.6B",
            "Qwen/Qwen3-Reranker-0.6B",
            "qwen3:4b",
        ):
            self.assertIn(component, components)
            self.assertFalse(components[component]["may_remove"])
            self.assertTrue(components[component]["replacement_allowed_when"])

        self.assertTrue(
            constitution["semantic_cache_policy"][
                "does_not_override_advanced_memory_specialized_models"
            ]
        )

    def test_sensitive_tasks_default_to_unapproved(self) -> None:
        """Ausencia de aprovacao explicita nunca libera efeitos sensiveis."""

        policy = load_constitutional_policy()
        cases = [
            {"effect_scope": "external"},
            {"effect_scope": "credential_change"},
            {"effect_scope": "destructive"},
            {"risk": 7},
            {"sensitive_action": True},
            {"requires_supervision": True},
            {"domain": "unknown_domain"},
        ]
        for extra in cases:
            with self.subTest(extra=extra):
                task = {"task_id": "consent-required", "goal": "Executar operacao", "domain": "runtime", **extra}
                outcome = policy.evaluate_task(task)
                self.assertTrue(outcome["requires_human_approval"])
                self.assertFalse(outcome["approved"])
                self.assertEqual(outcome["blocking_reason"], "requires_human_approval")

    def test_queue_cannot_invent_approval_for_sensitive_task(self) -> None:
        """Normalizacao e persistencia de fila nao podem aprovar tarefas."""

        queue = TaskQueue(storage_path=make_policy_artifact_path("no_approval", "queue"))
        task = queue.enqueue({
            "task_id": "sensitive-queued",
            "goal": "Operacao que exige aval",
            "domain": "runtime",
            "risk": 7,
        })
        self.assertFalse(task["approved"])
        self.assertFalse(task["approval"]["approved"])

        outcome = load_constitutional_policy().evaluate_task(queue.snapshot_items()[0])
        self.assertTrue(outcome["requires_human_approval"])
        self.assertFalse(outcome["approved"])
        self.assertEqual(outcome["blocking_reason"], "requires_human_approval")

    def test_validator_does_not_invent_sensitive_approval(self) -> None:
        """A passagem pelo validador nao pode preencher consentimento ausente com True."""

        task = {
            "task_id": "without-consent",
            "goal": "Atualizar credencial",
            "domain": "runtime",
            "effect_scope": "credential_change",
        }
        valid, issues = PlanValidator().validate_task(task)
        self.assertTrue(valid)
        self.assertEqual(issues, [])
        self.assertTrue(task["requires_supervision"])
        self.assertFalse(task["approved"])
        self.assertFalse(task["approval"]["approved"])

    def test_runtime_gate_reports_missing_sensitive_approval(self) -> None:
        """Gate de autonomia bloqueia e informa aprovacao efetiva da politica."""

        from runtime.autonomy import AutonomyController

        outcome = AutonomyController().evaluate({
            "task_id": "gate-consent",
            "goal": "Operacao externa",
            "domain": "runtime",
            "effect_scope": "external",
        })
        self.assertFalse(outcome["should_execute"])
        self.assertFalse(outcome["approved"])
        self.assertEqual(outcome["reason"], "requires_human_approval")

    def test_low_risk_autonomy_and_explicit_consent_remain_compatible(self) -> None:
        """Preserva tarefas internas simples e exige True explicito para excecao sensivel."""

        policy = load_constitutional_policy()
        internal = policy.evaluate_task({"goal": "Resumir estudo", "domain": "study"})
        self.assertFalse(internal["requires_human_approval"])
        self.assertTrue(internal["approved"])
        self.assertIsNone(internal["blocking_reason"])

        consented = policy.evaluate_task({
            "goal": "Operacao externa previamente aprovada",
            "domain": "runtime",
            "effect_scope": "external",
            "approval": {"approved": True},
        })
        self.assertTrue(consented["requires_human_approval"])
        self.assertTrue(consented["approved"])
        self.assertIsNone(consented["blocking_reason"])

    def test_validator_denies_absolutely_prohibited_task(self) -> None:
        """Garante negacao de tarefas que violam proibicoes absolutas."""

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
        """Verifica que tarefas sensiveis exigem aprovacao humana."""

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
        """Confirma que o runtime bloqueia execucao sem aprovacao quando necessario."""

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
