"""Tests for the async event bus — pub/sub, multi-handler, error isolation."""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from core.events import (
    EventBus,
    EventType,
    HeartbeatEvent,
    TickEvent,
)
from core.types import Tick


def _make_tick(exchange: str = "test") -> Tick:
    return Tick(
        exchange=exchange,
        symbol="BTC-USD",
        bid=Decimal("67800"),
        ask=Decimal("67801"),
        mid=Decimal("67800.50"),
        bid_size=Decimal("1"),
        ask_size=Decimal("1"),
        timestamp_ns=1_700_000_000_000_000_000,
    )


class TestEventBus:
    async def test_publish_subscribe(self) -> None:
        """Events reach their registered handlers."""
        bus = EventBus()
        received: list[TickEvent] = []

        async def handler(event: TickEvent) -> None:
            received.append(event)

        bus.subscribe(EventType.TICK, handler)
        await bus.start()

        tick = _make_tick()
        await bus.publish(TickEvent(tick=tick))

        # Give consumer task time to process
        await asyncio.sleep(0.05)
        await bus.stop()

        assert len(received) == 1
        assert received[0].tick == tick

    async def test_multiple_handlers(self) -> None:
        """Multiple handlers for the same event type all get called."""
        bus = EventBus()
        results_a: list[TickEvent] = []
        results_b: list[TickEvent] = []

        async def handler_a(event: TickEvent) -> None:
            results_a.append(event)

        async def handler_b(event: TickEvent) -> None:
            results_b.append(event)

        bus.subscribe(EventType.TICK, handler_a)
        bus.subscribe(EventType.TICK, handler_b)
        await bus.start()

        await bus.publish(TickEvent(tick=_make_tick()))
        await asyncio.sleep(0.05)
        await bus.stop()

        assert len(results_a) == 1
        assert len(results_b) == 1

    async def test_error_isolation(self) -> None:
        """A failing handler doesn't prevent other handlers from running."""
        bus = EventBus()
        received: list[TickEvent] = []

        async def bad_handler(event: TickEvent) -> None:
            raise RuntimeError("handler crash")

        async def good_handler(event: TickEvent) -> None:
            received.append(event)

        bus.subscribe(EventType.TICK, bad_handler)
        bus.subscribe(EventType.TICK, good_handler)
        await bus.start()

        await bus.publish(TickEvent(tick=_make_tick()))
        await asyncio.sleep(0.05)
        await bus.stop()

        # Good handler still received the event despite bad handler crashing
        assert len(received) == 1

    async def test_different_event_types_isolated(self) -> None:
        """Handlers only receive events of their subscribed type."""
        bus = EventBus()
        tick_events: list = []
        heartbeat_events: list = []

        async def tick_handler(event: TickEvent) -> None:
            tick_events.append(event)

        async def heartbeat_handler(event: HeartbeatEvent) -> None:
            heartbeat_events.append(event)

        bus.subscribe(EventType.TICK, tick_handler)
        bus.subscribe(EventType.HEARTBEAT, heartbeat_handler)
        await bus.start()

        await bus.publish(TickEvent(tick=_make_tick()))
        await bus.publish(
            HeartbeatEvent(component="test", timestamp_ns=1_700_000_000_000_000_000)
        )
        await asyncio.sleep(0.05)
        await bus.stop()

        assert len(tick_events) == 1
        assert len(heartbeat_events) == 1

    async def test_publish_before_start_raises(self) -> None:
        """Publishing to a stopped bus raises RuntimeError."""
        bus = EventBus()
        bus.subscribe(EventType.TICK, lambda e: None)

        with pytest.raises(RuntimeError, match="not running"):
            await bus.publish(TickEvent(tick=_make_tick()))

    async def test_subscriber_count(self) -> None:
        bus = EventBus()

        async def noop(event) -> None:
            pass

        bus.subscribe(EventType.TICK, noop)
        bus.subscribe(EventType.TICK, noop)
        bus.subscribe(EventType.ALERT, noop)

        counts = bus.subscriber_count
        assert counts[EventType.TICK] == 2
        assert counts[EventType.ALERT] == 1

    async def test_start_stop_lifecycle(self) -> None:
        bus = EventBus()

        async def noop(event) -> None:
            pass

        bus.subscribe(EventType.TICK, noop)

        assert not bus.is_running
        await bus.start()
        assert bus.is_running
        await bus.stop()
        assert not bus.is_running

    async def test_multiple_events_ordering(self) -> None:
        """Events are processed in FIFO order."""
        bus = EventBus()
        received_exchanges: list[str] = []

        async def handler(event: TickEvent) -> None:
            assert event.tick is not None
            received_exchanges.append(event.tick.exchange)

        bus.subscribe(EventType.TICK, handler)
        await bus.start()

        for name in ["first", "second", "third"]:
            await bus.publish(TickEvent(tick=_make_tick(exchange=name)))

        await asyncio.sleep(0.1)
        await bus.stop()

        assert received_exchanges == ["first", "second", "third"]
