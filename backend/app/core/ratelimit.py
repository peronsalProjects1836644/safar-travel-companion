"""Small in-memory sliding-window limiter.

Fine for a single worker process (our free hosting setup). If the app is ever
run with several workers, move this to a shared store.
"""

import time
from collections import deque


class RateLimiter:
    def __init__(self, max_keys: int = 20000):
        self._hits: dict[str, deque[float]] = {}
        self._max_keys = max_keys

    def allow(self, key: str, limit: int, window_s: float) -> tuple[bool, float]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        q = self._hits.setdefault(key, deque())
        cutoff = now - window_s
        while q and q[0] <= cutoff:
            q.popleft()
        if len(q) >= limit:
            return False, max(0.0, q[0] + window_s - now)
        q.append(now)
        if len(self._hits) > self._max_keys:
            self._cleanup(now, window_s)
        return True, 0.0

    def _cleanup(self, now: float, window_s: float) -> None:
        for k in [k for k, q in self._hits.items() if not q or q[-1] <= now - window_s]:
            self._hits.pop(k, None)
