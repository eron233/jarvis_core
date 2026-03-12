"""Validation helpers for generated plans."""

from typing import Any, Dict, List, Tuple


class PlanValidator:
    """Applies baseline structural validation to plans."""

    def validate(self, plan: Dict[str, Any]) -> Tuple[bool, List[str]]:
        issues: List[str] = []

        if not plan.get("goal"):
            issues.append("Plan is missing a goal.")

        if not isinstance(plan.get("steps", []), list):
            issues.append("Plan steps must be a list.")

        return (len(issues) == 0, issues)
