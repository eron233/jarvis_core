"""Semantic memory storage for facts and concepts."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class SemanticMemory:
    """Stores normalized facts keyed by concept."""

    facts: Dict[str, Any] = field(default_factory=dict)

    def upsert(self, concept: str, value: Any) -> None:
        self.facts[concept] = value

    def get(self, concept: str) -> Optional[Any]:
        return self.facts.get(concept)
