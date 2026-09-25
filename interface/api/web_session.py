"""
JARVIS - Sessao web assinada e limitador de tentativas de autenticacao

Responsavel por:
- emitir cookies de sessao assinados por HMAC, com expiracao e revogacao
- invalidar todas as sessoes quando o token ou a senha administrativa mudam
- limitar tentativas de autenticacao falhas por origem (anti forca bruta)

Integracoes principais:
- interface.api.app
"""

from __future__ import annotations

import base64
from collections import deque
from dataclasses import dataclass
import hashlib
import hmac
import secrets
import threading
import time
from typing import Deque, Dict, Optional


SESSION_VERSION = "v2"
DEFAULT_SESSION_TTL_SECONDS = 7 * 24 * 3600


def secrets_match(provided: Optional[str], expected: Optional[str]) -> bool:
    """Compara segredos em tempo constante; valores vazios nunca casam."""

    if not provided or not expected:
        return False
    return hmac.compare_digest(str(provided).encode("utf-8"), str(expected).encode("utf-8"))


def _b64encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def _b64decode(value: str) -> str:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding).decode("utf-8")


@dataclass(frozen=True)
class WebSession:
    """Sessao web valida ja verificada."""

    session_id: str
    device_id: str
    expires_at: int


class WebSessionManager:
    """Emite e verifica cookies de sessao `v2.<sid>.<device>.<exp>.<assinatura>`."""

    def __init__(self, ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS) -> None:
        self.ttl_seconds = max(60, int(ttl_seconds))
        self._revoked: Dict[str, int] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(secret_material: str) -> bytes:
        return hashlib.sha256(f"jarvis-web-session|{secret_material}".encode("utf-8")).digest()

    def issue(self, secret_material: str, device_id: str, now: Optional[float] = None) -> str:
        """Gera um novo cookie assinado para o dispositivo informado."""

        issued_at = int(now if now is not None else time.time())
        payload = ".".join(
            [
                SESSION_VERSION,
                secrets.token_urlsafe(18),
                _b64encode(device_id),
                str(issued_at + self.ttl_seconds),
            ]
        )
        signature = hmac.new(self._key(secret_material), payload.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{payload}.{signature}"

    def verify(self, secret_material: str, cookie_value: Optional[str], now: Optional[float] = None) -> Optional[WebSession]:
        """Retorna a sessao quando assinatura, validade e revogacao conferem."""

        if not cookie_value or not secret_material:
            return None
        parts = cookie_value.split(".")
        if len(parts) != 5 or parts[0] != SESSION_VERSION:
            return None
        payload = ".".join(parts[:4])
        expected = hmac.new(self._key(secret_material), payload.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, parts[4]):
            return None
        try:
            expires_at = int(parts[3])
            device_id = _b64decode(parts[2])
        except (ValueError, UnicodeDecodeError):
            return None
        current = int(now if now is not None else time.time())
        if expires_at <= current:
            return None
        with self._lock:
            if parts[1] in self._revoked:
                return None
        return WebSession(session_id=parts[1], device_id=device_id, expires_at=expires_at)

    def revoke(self, session: WebSession) -> None:
        """Revoga uma sessao ate sua expiracao natural."""

        now = int(time.time())
        with self._lock:
            self._revoked = {sid: exp for sid, exp in self._revoked.items() if exp > now}
            self._revoked[session.session_id] = session.expires_at


class AuthAttemptLimiter:
    """Janela deslizante de falhas de autenticacao por origem."""

    def __init__(self, max_failures: int = 10, window_seconds: int = 300) -> None:
        self.max_failures = max(1, int(max_failures))
        self.window_seconds = max(1, int(window_seconds))
        self._failures: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> Deque[float]:
        bucket = self._failures.setdefault(key, deque())
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        return bucket

    def is_blocked(self, key: str, now: Optional[float] = None) -> bool:
        current = now if now is not None else time.monotonic()
        with self._lock:
            return len(self._prune(key, current)) >= self.max_failures

    def register_failure(self, key: str, now: Optional[float] = None) -> None:
        current = now if now is not None else time.monotonic()
        with self._lock:
            self._prune(key, current).append(current)
            if len(self._failures) > 10_000:
                # Evita crescimento sem limite sob varredura distribuida.
                for stale_key in [k for k, v in self._failures.items() if not v][:5_000]:
                    self._failures.pop(stale_key, None)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)
