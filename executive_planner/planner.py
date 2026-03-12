"""High-level planning orchestration for JARVIS."""

from typing import Any, Dict, Optional


class ExecutivePlanner:
    """Builds draft plans from a goal and optional context."""

    def create_plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "goal": goal,
            "context": context or {},
            "steps": [],
            "status": "draft",
        }
