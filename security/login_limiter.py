"""Limite global por processo; nao registra enderecos IP nem senhas."""
from collections import deque
from threading import Lock
from time import monotonic
from typing import Callable


class LoginLimiter:
    def __init__(self, capacity: int = 10, window_seconds: int = 60,
                 clock: Callable[[], float] = monotonic):
        if capacity <= 0 or window_seconds <= 0:
            raise ValueError("Limites de login invalidos")
        self._capacity = capacity
        self._window = window_seconds
        self._clock = clock
        self._attempts = deque()
        self._lock = Lock()

    def reserve(self) -> bool:
        with self._lock:
            now = self._clock()
            while self._attempts and self._attempts[0] <= now - self._window:
                self._attempts.popleft()
            if len(self._attempts) >= self._capacity:
                return False
            self._attempts.append(now)
            return True
