"""Armazenamento de memoria episodica para eventos ordenados no tempo."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class EpisodicMemory:
    """Mantem episodios recentes para replay e reflexao futura."""

    episodes: List[Dict[str, Any]] = field(default_factory=list)

    def remember(self, episode: Dict[str, Any]) -> None:
        self.episodes.append(episode)

    def recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.episodes[-limit:]
