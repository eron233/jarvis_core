"""
JARVIS - Validador do Planejador

Responsavel por:
- validar planos e tarefas antes da execucao
- aplicar a politica viva do constitutional_core
- marcar tarefas que exigem supervisao humana
- sinalizar negacoes e problemas estruturais do planner

Integracoes principais:
- constitutional_core.policy
- executive_planner.planner
- runtime.autonomy
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Tuple

from constitutional_core.policy import ConstitutionalPolicy, load_constitutional_policy


#
# JARVIS_PLANNER_LOGIC
# ==================================================
# BLOCO: Validacao estrutural e constitucional
# ==================================================

class PlanValidator:
    """Aplica verificacoes estruturais basicas em planos e tarefas."""

    def __init__(self, policy: ConstitutionalPolicy | None = None) -> None:
        """
        Inicializa o validador com a politica constitucional ativa.

        Parametros:
        - policy: politica opcional para reaproveitamento em testes ou bootstrap.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - define a referencia de politica usada em todas as validacoes.
        """

        self.policy = policy or load_constitutional_policy()

    def set_policy(self, policy: ConstitutionalPolicy) -> None:
        """
        Substitui a politica ativa usada pelo validador.

        Parametros:
        - policy: nova politica constitucional carregada.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - passa a reger validacoes futuras com a nova politica.
        """

        self.policy = policy

    def describe_policy(self) -> Dict[str, Any]:
        """
        Expoe um resumo seguro da politica atual.

        Parametros:
        - nenhum.

        Retorno:
        - dicionario com identidade, principios e restricoes ativas.

        Efeitos no sistema:
        - nenhum; oferece introspeccao para runtime e API.
        """

        return self.policy.describe()

    def validate(self, plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Valida a estrutura minima de um plano ainda nao executado.

        Parametros:
        - plan: dicionario do plano montado pelo planner.

        Retorno:
        - tupla com status de validade e lista de problemas detectados.

        Efeitos no sistema:
        - nenhum; apenas avalia consistencia estrutural.
        """

        issues: List[str] = []

        if not plan.get("goal"):
            issues.append("O plano esta sem meta definida.")

        if not isinstance(plan.get("steps", []), list):
            issues.append("As etapas do plano precisam ser uma lista.")

        return (len(issues) == 0, issues)

    def validate_task(self, task: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Aplica verificacoes constitucionais minimas para execucao de tarefas."""

        issues: List[str] = []
        policy_evaluation = self.policy.evaluate_task(task)
        self._apply_policy_evaluation(task, policy_evaluation)

        if not task.get("task_id"):
            issues.append("A tarefa esta sem task_id.")

        if not task.get("goal"):
            issues.append("A tarefa esta sem meta.")

        if policy_evaluation["denied"] or task.get("denied", False):
            issues.extend(policy_evaluation["hard_violations"] or ["A tarefa foi negada pela politica ativa."])

        if task.get("unsafe", False):
            issues.append("A tarefa foi marcada como insegura para execucao deterministica.")

        return (len(issues) == 0, issues)

    @staticmethod
    def _apply_policy_evaluation(task: Dict[str, Any], policy_evaluation: Dict[str, Any]) -> None:
        """
        Mescla o resultado da politica na estrutura da tarefa.

        Parametros:
        - task: tarefa que sera enriquecida com decisoes constitucionais.
        - policy_evaluation: resultado retornado pela politica viva.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - atualiza campos de aprovacao, supervisao e negacao diretamente na tarefa.
        """

        approval = task.get("approval", {})
        if not isinstance(approval, dict):
            approval = {}

        merged_approval = deepcopy(approval)
        merged_approval["approved"] = bool(merged_approval.get("approved", task.get("approved", True)))
        merged_approval["requires_supervision"] = bool(
            merged_approval.get("requires_supervision", task.get("requires_supervision", False))
            or policy_evaluation["requires_human_approval"]
        )

        task["approval"] = merged_approval
        task["approved"] = merged_approval["approved"]
        task["requires_supervision"] = merged_approval["requires_supervision"]
        task["denied"] = bool(task.get("denied", False) or policy_evaluation["denied"])
        task["policy_evaluation"] = policy_evaluation
