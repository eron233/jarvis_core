"""Procedural memory storage for reusable routines."""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ProceduralMemory:
    """Stores named procedures as ordered steps."""

    procedures: Dict[str, List[str]] = field(default_factory=dict)

    def register(self, name: str, steps: List[str]) -> None:
        self.procedures[name] = steps

    def get(self, name: str) -> List[str]:
        return self.procedures.get(name, [])
