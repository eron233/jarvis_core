"""Priority scoring helpers for planner tasks."""

from typing import Any, Dict


class Prioritizer:
    """Computes a simple weighted score for a task."""

    def score(self, task: Dict[str, Any]) -> int:
        urgency = int(task.get("urgency", 0))
        importance = int(task.get("importance", 0))
        return (importance * 10) + urgency
