"""Helpers de priorizacao para tarefas do planejador."""

from typing import Any, Dict


class Prioritizer:
    """Calcula uma pontuacao simples e deterministica para uma tarefa."""

    def score(self, task: Dict[str, Any]) -> int:
        urgency = int(task.get("urgency", 0))
        impact = int(task.get("impact", task.get("importance", 0)))
        goal_priority = int(task.get("goal_priority", 0))
        return (goal_priority * 100) + (impact * 10) + urgency
