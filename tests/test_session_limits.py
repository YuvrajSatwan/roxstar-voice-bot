"""Tests for the per-user session limiter (session_limits.py)."""

from __future__ import annotations

import threading

from sts_lab.session_limits import SessionRateLimiter


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_the_limit_then_blocks():
    lim = SessionRateLimiter(3, 3600, clock=FakeClock())
    assert [lim.allow("u1") for _ in range(4)] == [True, True, True, False]


def test_each_user_has_their_own_allowance():
    lim = SessionRateLimiter(1, 3600, clock=FakeClock())
    assert lim.allow("u1") is True
    assert lim.allow("u2") is True
    assert lim.allow("u1") is False


def test_allowance_comes_back_after_the_window():
    clock = FakeClock()
    lim = SessionRateLimiter(1, 3600, clock=clock)
    assert lim.allow("u1") is True
    clock.now += 3599
    assert lim.allow("u1") is False
    clock.now += 2
    assert lim.allow("u1") is True


def test_a_blocked_attempt_does_not_extend_the_block():
    clock = FakeClock()
    lim = SessionRateLimiter(1, 100, clock=clock)
    lim.allow("u1")
    clock.now += 60
    assert lim.allow("u1") is False  # blocked attempts are not recorded
    clock.now += 41  # 101 s after the first, real, attempt
    assert lim.allow("u1") is True


def test_zero_limit_means_limiter_is_off():
    lim = SessionRateLimiter(0, 3600, clock=FakeClock())
    assert all(lim.allow("u1") for _ in range(50))


def test_memory_stays_bounded_by_forgetting_old_users():
    clock = FakeClock()
    lim = SessionRateLimiter(1, 10, clock=clock, max_keys=5)
    for i in range(5):
        lim.allow(f"u{i}")
    clock.now += 11  # everyone is now stale
    assert lim.allow("newcomer") is True
    assert len(lim._events) <= 5


def test_concurrent_attempts_never_exceed_the_limit():
    lim = SessionRateLimiter(3, 3600)
    results: list[bool] = []

    def attempt() -> None:
        results.append(lim.allow("same-user"))

    threads = [threading.Thread(target=attempt) for _ in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count(True) == 3
