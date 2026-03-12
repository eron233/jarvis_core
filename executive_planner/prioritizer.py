"""Helpers de priorizacao para tarefas do planejador."""

from typing import Any, Dict


class Prioritizer:
    """Calcula uma pontuacao simples e deterministica para uma tarefa."""

    def score(self, task: Dict[str, Any]) -> int:
        urgency = int(task.get("urgency", 0))
        impact = int(task.get("impact", task.get("importance", 0)))
        return (impact * 10) + urgency
