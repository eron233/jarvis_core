"""Autonomy controls for gated execution."""

from typing import Any, Dict


class AutonomyController:
    """Determines whether a task can execute autonomously."""

    def should_execute(self, task: Dict[str, Any]) -> bool:
        requires_supervision = bool(task.get("requires_supervision", False))
        approved = bool(task.get("approved", True))
        return approved and not requires_supervision
