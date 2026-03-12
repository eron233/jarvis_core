"""Task queue primitives for the executive planner."""

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional


@dataclass
class TaskQueue:
    """FIFO queue for planner tasks."""

    items: Deque[Dict[str, Any]] = field(default_factory=deque)

    def enqueue(self, task: Dict[str, Any]) -> None:
        self.items.append(task)

    def dequeue(self) -> Optional[Dict[str, Any]]:
        if not self.items:
            return None
        return self.items.popleft()
