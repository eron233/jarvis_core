"""
JARVIS - Priorizador Deterministico

Responsavel por:
- calcular a prioridade relativa de tarefas do planner
- combinar urgencia, impacto e prioridade de objetivo
- manter a ordenacao reproduzivel entre ciclos

Integracoes principais:
- executive_planner.planner
- executive_planner.queue
- runtime.internal_agent_runtime
"""

from typing import Any, Dict


#
# JARVIS_PLANNER_LOGIC
# ==================================================
# BLOCO: Calculo de prioridade do planner
# ==================================================

class Prioritizer:
    """Calcula uma pontuacao simples e deterministica para uma tarefa."""

    def score(self, task: Dict[str, Any]) -> int:
        """
        Calcula a pontuacao deterministica de uma tarefa.

        Parametros:
        - task: tarefa normalizada pelo planner ou pela fila.

        Retorno:
        - inteiro usado para ordenar a fila de execucao.

        Efeitos no sistema:
        - nenhum; apenas orienta o ranking do ciclo atual.
        """

        urgency = int(task.get("urgency", 0))
        impact = int(task.get("impact", task.get("importance", 0)))
        goal_priority = int(task.get("goal_priority", 0))
        return (goal_priority * 100) + (impact * 10) + urgency
