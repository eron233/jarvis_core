"""Validation helpers for generated plans and executable tasks."""

from typing import Any, Dict, List, Tuple


class PlanValidator:
    """Applies baseline structural validation to plans and tasks."""

    def validate(self, plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
        issues: List[str] = []

        if not plan.get("goal"):
            issues.append("Plan is missing a goal.")

        if not isinstance(plan.get("steps", []), list):
            issues.append("Plan steps must be a list.")

        return (len(issues) == 0, issues)

    def validate_task(self, task: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Applies minimal constitutional checks for planner task execution."""

        issues: List[str] = []

        if not task.get("task_id"):
            issues.append("Task is missing a task_id.")

        if not task.get("goal"):
            issues.append("Task is missing a goal.")

        if task.get("denied", False):
            issues.append("Task is explicitly denied by policy.")

        if task.get("unsafe", False):
            issues.append("Task is marked unsafe for deterministic execution.")

        return (len(issues) == 0, issues)
