"""Audit logging primitives for planner decisions."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class AuditLogger:
    """Stores lightweight audit entries in memory."""

    entries: List[Dict[str, Any]] = field(default_factory=list)

    def record(self, event: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "payload": payload or {},
        }
        self.entries.append(entry)
        return entry
