"""A thread-safe request spacer shared across workers.

The bug this exists to prevent: giving each worker its own minimum interval. Eight workers each
honouring a 3-second floor issue 160 requests/minute against a 20 rpm limit — the API 429s
immediately. One :class:`TokenBucket` instance, shared by every worker (and every provider
instance), is the only thing that can actually keep total throughput under the real quota.
"""

from __future__ import annotations

import threading
import time


class TokenBucket:
    """Blocks each caller until at least ``60/rpm`` seconds have passed since the previous
    acquisition — across ALL threads sharing this instance, not per-thread.

    Thread-safe: a short critical section (protected by a lock) reserves the caller's slot by
    advancing ``_next_at``, then the caller sleeps outside the lock so concurrent callers don't
    block each other's bookkeeping while waiting.
    """

    def __init__(self, rpm: int) -> None:
        self._interval = 60.0 / max(1, rpm)
        self._lock = threading.Lock()
        self._next_at = 0.0

    def acquire(self) -> None:
        """Block until it is this caller's turn, then reserve the next slot."""
        with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next_at - now)
            self._next_at = max(now, self._next_at) + self._interval
        if wait:
            time.sleep(wait)
