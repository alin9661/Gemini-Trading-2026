"""Clock abstraction for real-time and simulated (backtest) operation.

All components receive a Clock instance via dependency injection. This allows
the same code to run in production (RealClock) and backtests (SimulatedClock).
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Protocol for system clock. Implementations must provide nanosecond time."""

    def now_ns(self) -> int: ...
    def now_dt(self) -> datetime: ...


class RealClock:
    """Production clock backed by time.time_ns()."""

    def now_ns(self) -> int:
        return time.time_ns()

    def now_dt(self) -> datetime:
        return datetime.now(tz=UTC)


class SimulatedClock:
    """Manually-controlled clock for backtesting and tests.

    Usage:
        clock = SimulatedClock(start_ns=1_700_000_000_000_000_000)
        clock.advance(1_000_000_000)  # advance 1 second
        clock.set(1_700_000_001_000_000_000)  # jump to specific time
    """

    def __init__(self, start_ns: int = 0) -> None:
        self._current_ns = start_ns

    def now_ns(self) -> int:
        return self._current_ns

    def now_dt(self) -> datetime:
        seconds = self._current_ns / 1_000_000_000
        return datetime.fromtimestamp(seconds, tz=UTC)

    def advance(self, nanoseconds: int) -> None:
        """Move clock forward by the given number of nanoseconds."""
        if nanoseconds < 0:
            raise ValueError(f"Cannot advance by negative amount: {nanoseconds}")
        self._current_ns += nanoseconds

    def set(self, timestamp_ns: int) -> None:
        """Set clock to a specific nanosecond timestamp."""
        self._current_ns = timestamp_ns
