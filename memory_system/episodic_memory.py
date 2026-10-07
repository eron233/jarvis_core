"""
JARVIS - Memoria Episodica

Responsavel por:
- registrar eventos do runtime em ordem temporal
- apoiar auditoria, replay e relatorios operacionais
- persistir episodios entre reinicios quando um storage_path e configurado
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class EpisodicMemory:
    """Mantem episodios recentes com persistencia atomica opcional."""

    storage_path: Optional[Path] = None
    auto_persist: bool = False
    max_episodes: int = 10_000
    episodes: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.storage_path is not None:
            self.storage_path = Path(self.storage_path)

    def remember(self, episode: Dict[str, Any]) -> None:
        """Armazena um novo episodio no historico cronologico."""

        self.episodes.append(deepcopy(episode))
        if self.max_episodes > 0 and len(self.episodes) > self.max_episodes:
            self.episodes = self.episodes[-self.max_episodes :]
        if self.auto_persist:
            self._write_storage()

    def recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Recupera os episodios mais recentes."""

        if limit <= 0:
            return []
        return deepcopy(self.episodes[-limit:])

    def snapshot(self) -> Dict[str, Any]:
        """Persiste e retorna o estado episodico."""

        payload = self._build_snapshot()
        self._write_storage(payload)
        return payload

    def load_snapshot(self, snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Restaura episodios do payload informado ou do disco."""

        if snapshot is None:
            if self.storage_path is None or not self.storage_path.exists():
                self.episodes = []
                return self._build_snapshot()
            snapshot = json.loads(self.storage_path.read_text(encoding="utf-8"))

        loaded = snapshot.get("episodes", [])
        if not isinstance(loaded, list):
            raise ValueError("Snapshot episodico invalido: 'episodes' deve ser uma lista.")
        self.episodes = [deepcopy(item) for item in loaded if isinstance(item, dict)]
        if self.max_episodes > 0:
            self.episodes = self.episodes[-self.max_episodes :]
        return self._build_snapshot()

    def _build_snapshot(self) -> Dict[str, Any]:
        return {
            "version": "0.2.0",
            "episode_count": len(self.episodes),
            "episodes": deepcopy(self.episodes),
        }

    def _write_storage(self, snapshot: Optional[Dict[str, Any]] = None) -> None:
        if self.storage_path is None:
            return
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        payload = snapshot or self._build_snapshot()
        temp_path = self.storage_path.with_name(f"{self.storage_path.name}.tmp")
        temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(temp_path, self.storage_path)
