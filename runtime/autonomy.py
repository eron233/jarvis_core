"""Controles de autonomia para execucao com supervisao."""

from __future__ import annotations

from typing import Any, Dict

from constitutional_core.policy import ConstitutionalPolicy, load_constitutional_policy


class AutonomyController:
    """Determina se uma tarefa pode ser executada de forma autonoma."""

    def __init__(self, policy: ConstitutionalPolicy | None = None) -> None:
        self.policy = policy or load_constitutional_policy()

    def set_policy(self, policy: ConstitutionalPolicy) -> None:
        self.policy = policy

    def evaluate(self, task: Dict[str, Any]) -> Dict[str, Any]:
        policy_evaluation = self.policy.evaluate_task(task)
        approved = bool(task.get("approved", task.get("approval", {}).get("approved", True)))

        if policy_evaluation["denied"]:
            return {
                "should_execute": False,
                "reason": "policy_denied",
                "reason_ptbr": "negada_pela_politica_constitucional",
                "approved": approved,
                "policy_evaluation": policy_evaluation,
            }

        if policy_evaluation["requires_human_approval"] and not approved:
            return {
                "should_execute": False,
                "reason": "requires_human_approval",
                "reason_ptbr": "requer_aprovacao_humana",
                "approved": approved,
                "policy_evaluation": policy_evaluation,
            }

        return {
            "should_execute": True,
            "reason": None,
            "reason_ptbr": None,
            "approved": approved,
            "policy_evaluation": policy_evaluation,
        }

    def should_execute(self, task: Dict[str, Any]) -> bool:
        return self.evaluate(task)["should_execute"]
