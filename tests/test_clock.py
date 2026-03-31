"""Tests for clock abstraction — real and simulated."""

from __future__ import annotations

import time

import pytest

from core.clock import RealClock, SimulatedClock


class TestRealClock:
    def test_now_ns_returns_positive(self) -> None:
        clock = RealClock()
        assert clock.now_ns() > 0

    def test_now_ns_monotonic(self) -> None:
        clock = RealClock()
        t1 = clock.now_ns()
        t2 = clock.now_ns()
        assert t2 >= t1

    def test_now_dt_has_timezone(self) -> None:
        clock = RealClock()
        dt = clock.now_dt()
        assert dt.tzinfo is not None

    def test_now_ns_close_to_system_time(self) -> None:
        clock = RealClock()
        system_ns = time.time_ns()
        clock_ns = clock.now_ns()
        # Should be within 1 second of each other
        assert abs(clock_ns - system_ns) < 1_000_000_000


class TestSimulatedClock:
    def test_initial_time(self) -> None:
        clock = SimulatedClock(start_ns=1_000_000)
        assert clock.now_ns() == 1_000_000

    def test_default_start_is_zero(self) -> None:
        clock = SimulatedClock()
        assert clock.now_ns() == 0

    def test_advance(self) -> None:
        clock = SimulatedClock(start_ns=1_000)
        clock.advance(500)
        assert clock.now_ns() == 1_500

    def test_advance_multiple_times(self) -> None:
        clock = SimulatedClock(start_ns=0)
        clock.advance(100)
        clock.advance(200)
        clock.advance(300)
        assert clock.now_ns() == 600

    def test_advance_negative_raises(self) -> None:
        clock = SimulatedClock(start_ns=1_000)
        with pytest.raises(ValueError, match="negative"):
            clock.advance(-1)

    def test_set(self) -> None:
        clock = SimulatedClock(start_ns=0)
        clock.set(5_000_000_000)
        assert clock.now_ns() == 5_000_000_000

    def test_now_dt_converts_correctly(self) -> None:
        # 1_700_000_000 seconds = 2023-11-14T22:13:20 UTC
        clock = SimulatedClock(start_ns=1_700_000_000_000_000_000)
        dt = clock.now_dt()
        assert dt.year == 2023
        assert dt.month == 11
        assert dt.tzinfo is not None

    def test_satisfies_clock_protocol(self) -> None:
        """SimulatedClock is structurally compatible with Clock protocol."""
        from core.clock import Clock

        def use_clock(c: Clock) -> int:
            return c.now_ns()

        clock = SimulatedClock(start_ns=42)
        assert use_clock(clock) == 42
