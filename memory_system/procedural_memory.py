"""Armazenamento de memoria procedural para rotinas reutilizaveis."""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class ProceduralMemory:
    """Armazena procedimentos nomeados como listas ordenadas de etapas."""

    procedures: Dict[str, List[str]] = field(default_factory=dict)

    def register(self, name: str, steps: List[str]) -> None:
        self.procedures[name] = steps

    def get(self, name: str) -> List[str]:
        return self.procedures.get(name, [])
