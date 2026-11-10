from app.core.rate_limit import SlidingWindowRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_limit_then_blocks() -> None:
    limiter = SlidingWindowRateLimiter(max_calls=3, period_seconds=60, clock=FakeClock())

    assert [limiter.try_acquire() for _ in range(4)] == [True, True, True, False]


def test_window_slides() -> None:
    clock = FakeClock()
    limiter = SlidingWindowRateLimiter(max_calls=2, period_seconds=60, clock=clock)
    limiter.try_acquire()  # t=1000
    clock.now += 30
    limiter.try_acquire()  # t=1030
    assert limiter.try_acquire() is False

    clock.now += 30  # t=1060: the t=1000 call has left the window
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False
