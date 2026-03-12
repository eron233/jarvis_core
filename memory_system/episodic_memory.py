"""Episodic memory storage for time-ordered events."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class EpisodicMemory:
    """Tracks recent episodes for replay and reflection."""

    episodes: List[Dict[str, Any]] = field(default_factory=list)

    def remember(self, episode: Dict[str, Any]) -> None:
        self.episodes.append(episode)

    def recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self.episodes[-limit:]
