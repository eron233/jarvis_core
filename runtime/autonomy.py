"""Controles de autonomia para execucao com supervisao."""

from typing import Any, Dict


class AutonomyController:
    """Determina se uma tarefa pode ser executada de forma autonoma."""

    def should_execute(self, task: Dict[str, Any]) -> bool:
        requires_supervision = bool(task.get("requires_supervision", False))
        approved = bool(task.get("approved", True))
        return approved and not requires_supervision
