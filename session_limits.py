"""Per-user limits for starting Simran voice sessions.

In simple words:
  Every Simran session costs real money (Gemini + LiveKit minutes).
  This stops one user from starting sessions again and again.
  Default: at most 3 new sessions per user per hour.

Note for operators:
  The counters live in this process's memory. That is correct while the token server
  runs as ONE process (as it does today). If you ever run several token-server copies,
  move this to a shared store (Redis / the sts_lab database), otherwise each copy
  keeps its own count and the real limit becomes (limit x number of copies).
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable


class SessionRateLimiter:
    """Sliding-window limiter: 'max_events' per 'window_seconds' for each key (user id)."""

    def __init__(
        self,
        max_events: int,
        window_seconds: float = 3600.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        max_keys: int = 50_000,
    ) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._clock = clock
        self._max_keys = max_keys
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record one attempt. Returns False (and records nothing) if the user is over the limit."""
        if self.max_events <= 0:  # 0 or negative = limiter switched off
            return True
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._events.get(key)
            if bucket is None:
                if len(self._events) >= self._max_keys:
                    self._evict_stale(cutoff)
                bucket = self._events.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_events:
                return False
            bucket.append(now)
            return True

    def _evict_stale(self, cutoff: float) -> None:
        """Memory safety: forget users whose attempts are all older than the window."""
        for k in [k for k, b in self._events.items() if not b or b[-1] <= cutoff]:
            del self._events[k]
