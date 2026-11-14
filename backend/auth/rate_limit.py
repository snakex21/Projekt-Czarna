"""Prosty limiter nieudanych logowań (w pamięci procesu, per adres IP)."""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, Optional


class LoginRateLimiter:
    """Blokuje klucz (np. IP) po ``max_attempts`` porażkach w oknie ``window_seconds``."""

    def __init__(self, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._failures: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> Deque[float]:
        q = self._failures.setdefault(key, deque())
        while q and q[0] <= now - self.window_seconds:
            q.popleft()
        return q

    def retry_after(self, key: str, now: Optional[float] = None) -> Optional[int]:
        """Sekundy do odblokowania albo ``None``, gdy próba jest dozwolona."""
        if self.max_attempts <= 0:
            return None
        now = time.monotonic() if now is None else now
        with self._lock:
            q = self._prune(key, now)
            if len(q) < self.max_attempts:
                return None
            return max(1, int(q[0] + self.window_seconds - now) + 1)

    def record_failure(self, key: str, now: Optional[float] = None) -> None:
        now = time.monotonic() if now is None else now
        with self._lock:
            self._prune(key, now).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()


_login_limiter: Optional[LoginRateLimiter] = None


def get_login_limiter() -> LoginRateLimiter:
    """Limiter skonfigurowany z ``config.LOGIN_MAX_ATTEMPTS`` / ``LOGIN_WINDOW_SECONDS``."""
    global _login_limiter
    from .. import config

    if (
        _login_limiter is None
        or _login_limiter.max_attempts != config.LOGIN_MAX_ATTEMPTS
        or _login_limiter.window_seconds != config.LOGIN_WINDOW_SECONDS
    ):
        _login_limiter = LoginRateLimiter(config.LOGIN_MAX_ATTEMPTS, config.LOGIN_WINDOW_SECONDS)
    return _login_limiter
