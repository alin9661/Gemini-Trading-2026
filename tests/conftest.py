"""Shared test fixtures for the trading system."""

from __future__ import annotations

import pytest

from core.clock import SimulatedClock
from core.events import EventBus


@pytest.fixture
def clock() -> SimulatedClock:
    """A simulated clock starting at a known timestamp."""
    return SimulatedClock(start_ns=1_700_000_000_000_000_000)  # ~2023-11-14


@pytest.fixture
def event_bus() -> EventBus:
    """A fresh event bus instance."""
    return EventBus()
