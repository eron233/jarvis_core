"""Sessoes web opacas, revogaveis e limitadas ao processo HTTP."""
from dataclasses import dataclass
import hashlib
import hmac
import json
import secrets
from threading import Lock
from time import monotonic
from typing import Callable


@dataclass(frozen=True)
class DashboardSession:
    device_id: str
    mode: str
    expires_at: float
    binding: bytes


class DashboardSessions:
    def __init__(self, ttl_seconds: int = 3600, capacity: int = 256,
                 clock: Callable[[], float] = monotonic):
        if ttl_seconds <= 0 or capacity <= 0:
            raise ValueError("Limites de sessao invalidos")
        self.ttl_seconds = ttl_seconds
        self._capacity = capacity
        self._clock = clock
        self._lock = Lock()
        self._key = secrets.token_bytes(32)
        self._entries: dict[bytes, DashboardSession] = {}

    def _binding(self, values: tuple[str, ...]) -> bytes:
        return hmac.digest(self._key, json.dumps(values).encode("utf-8"), "sha256")

    @staticmethod
    def _digest(token: str | None) -> bytes | None:
        if not isinstance(token, str) or len(token) != 43 or not token.isascii():
            return None
        return hashlib.sha256(token.encode("ascii")).digest()

    def issue(self, device_id: str, mode: str, binding: tuple[str, ...]) -> str:
        token = secrets.token_urlsafe(32)
        digest = self._digest(token)
        with self._lock:
            now = self._clock()
            for key in tuple(self._entries):
                if self._entries[key].expires_at <= now:
                    del self._entries[key]
            while len(self._entries) >= self._capacity:
                del self._entries[next(iter(self._entries))]
            self._entries[digest] = DashboardSession(
                device_id, mode, now + self.ttl_seconds, self._binding(binding)
            )
        return token

    def resolve(self, token: str | None, binding: tuple[str, ...]) -> DashboardSession | None:
        digest = self._digest(token)
        if digest is None:
            return None
        with self._lock:
            item = self._entries.get(digest)
            if item is None:
                return None
            if item.expires_at <= self._clock() or not hmac.compare_digest(item.binding, self._binding(binding)):
                del self._entries[digest]
                return None
            return item

    def revoke(self, token: str | None) -> None:
        digest = self._digest(token)
        if digest is not None:
            with self._lock:
                self._entries.pop(digest, None)
