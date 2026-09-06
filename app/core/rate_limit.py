"""Small bounded in-process rate limiter for high-risk routes."""

import math
import threading
import time
from collections import deque


class FixedWindowRateLimiter:
    def __init__(self, max_keys: int = 10_000) -> None:
        self._events: dict[str, deque[float]] = {}
        self._max_keys = max_keys
        self._lock = threading.Lock()

    def check(self, key: str, *, limit: int, window_seconds: int) -> int | None:
        """Record an attempt and return retry-after seconds when limited."""
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                return max(1, math.ceil(window_seconds - (now - events[0])))

            events.append(now)
            if len(self._events) > self._max_keys:
                stale_keys = [entry_key for entry_key, values in self._events.items() if not values or values[-1] <= cutoff]
                for entry_key in stale_keys:
                    self._events.pop(entry_key, None)
        return None

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


auth_rate_limiter = FixedWindowRateLimiter()
action_rate_limiter = FixedWindowRateLimiter()
