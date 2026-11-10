import time
from collections import deque
from collections.abc import Callable
from threading import Lock


class SlidingWindowRateLimiter:
    """Allow at most `max_calls` in any rolling `period_seconds` window.

    In-process only: each server process/instance keeps its own window. That's enough
    for one small instance; several instances would need a shared store (e.g. Redis).
    """

    def __init__(
        self,
        max_calls: int,
        period_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_calls = max_calls
        self._period = period_seconds
        self._clock = clock
        self._calls: deque[float] = deque()
        self._lock = Lock()  # FastAPI runs sync routes on several threads

    def try_acquire(self) -> bool:
        """Record a call and return True, or return False if the limit is reached."""
        with self._lock:
            now = self._clock()
            while self._calls and now - self._calls[0] >= self._period:
                self._calls.popleft()
            if len(self._calls) >= self._max_calls:
                return False
            self._calls.append(now)
            return True
