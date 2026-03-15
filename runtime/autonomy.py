"""
JARVIS - Gate de Autonomia

Responsavel por:
- decidir se uma tarefa pode ser executada automaticamente
- consultar a politica constitucional viva antes da execucao
- bloquear ou escalar tarefas sensiveis para aprovacao humana

Integracoes principais:
- constitutional_core.policy
- executive_planner.validator
- runtime.internal_agent_runtime
"""

from __future__ import annotations

from typing import Any, Dict

from constitutional_core.policy import ConstitutionalPolicy, load_constitutional_policy


#
# JARVIS_SECURITY_GATE
# ==================================================
# BLOCO: Controle de autonomia supervisionada
# ==================================================

class AutonomyController:
    """Determina se uma tarefa pode ser executada de forma autonoma."""

    def __init__(self, policy: ConstitutionalPolicy | None = None) -> None:
        """
        Inicializa o controlador de autonomia com a politica ativa.

        Parametros:
        - policy: politica opcional para injecao em testes ou bootstrap.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - define a base normativa usada nas decisoes de execucao.
        """

        self.policy = policy or load_constitutional_policy()

    def set_policy(self, policy: ConstitutionalPolicy) -> None:
        """
        Atualiza a politica usada pelo gate de autonomia.

        Parametros:
        - policy: nova politica constitucional carregada.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - altera as proximas decisoes de execucao automatica.
        """

        self.policy = policy

    def evaluate(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Avalia se a tarefa pode seguir para execucao automatica.

        Parametros:
        - task: tarefa candidata a execucao.

        Retorno:
        - dicionario com decisao, motivo e avaliacao de politica.

        Efeitos no sistema:
        - nenhum diretamente; o runtime usa essa resposta como gate.
        """

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
        """
        Retorna apenas o booleano de permissao de execucao.

        Parametros:
        - task: tarefa a ser verificada.

        Retorno:
        - `True` quando a tarefa pode ser executada agora.

        Efeitos no sistema:
        - nenhum; wrapper simples sobre `evaluate`.
        """

        return self.evaluate(task)["should_execute"]
