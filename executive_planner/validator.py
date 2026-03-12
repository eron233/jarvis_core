"""Validadores para planos gerados e tarefas executaveis."""

from typing import Any, Dict, List, Tuple


class PlanValidator:
    """Aplica verificacoes estruturais basicas em planos e tarefas."""

    def validate(self, plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
        issues: List[str] = []

        if not plan.get("goal"):
            issues.append("O plano esta sem meta definida.")

        if not isinstance(plan.get("steps", []), list):
            issues.append("As etapas do plano precisam ser uma lista.")

        return (len(issues) == 0, issues)

    def validate_task(self, task: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Aplica verificacoes constitucionais minimas para execucao de tarefas."""

        issues: List[str] = []

        if not task.get("task_id"):
            issues.append("A tarefa esta sem task_id.")

        if not task.get("goal"):
            issues.append("A tarefa esta sem meta.")

        if task.get("denied", False):
            issues.append("A tarefa foi negada pela politica ativa.")

        if task.get("unsafe", False):
            issues.append("A tarefa foi marcada como insegura para execucao deterministica.")

        return (len(issues) == 0, issues)
