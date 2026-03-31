"""Async event bus — the nervous system of the trading system.

All components communicate through typed events. No direct imports between layers.
This makes the system testable, backtestable, and eventually portable to Rust.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, auto
from typing import Any

from core.types import Direction, Fill, NormalizedPrice, Order, OrderStatus, Side, Tick

logger = logging.getLogger(__name__)

# Type alias for async event handlers
EventHandler = Callable[["Event"], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# Event Types
# ---------------------------------------------------------------------------


class EventType(Enum):
    TICK = auto()
    PRICE_UPDATE = auto()
    SIGNAL = auto()
    ORDER_REQUEST = auto()
    ORDER_STATUS = auto()
    FILL = auto()
    ALERT = auto()
    HEARTBEAT = auto()


@dataclass(slots=True, frozen=True)
class Event:
    """Base event. All events carry a type, timestamp, and correlation ID."""

    event_type: EventType
    timestamp_ns: int
    correlation_id: uuid.UUID = field(default_factory=uuid.uuid4)


@dataclass(slots=True, frozen=True)
class TickEvent(Event):
    """Raw price update from an exchange."""

    tick: Tick | None = None

    def __init__(self, tick: Tick, correlation_id: uuid.UUID | None = None) -> None:
        object.__setattr__(self, "event_type", EventType.TICK)
        object.__setattr__(self, "timestamp_ns", tick.timestamp_ns)
        object.__setattr__(self, "correlation_id", correlation_id or uuid.uuid4())
        object.__setattr__(self, "tick", tick)


@dataclass(slots=True, frozen=True)
class PriceUpdateEvent(Event):
    """Normalized, cross-validated price update."""

    price: NormalizedPrice | None = None

    def __init__(
        self, price: NormalizedPrice, correlation_id: uuid.UUID | None = None
    ) -> None:
        object.__setattr__(self, "event_type", EventType.PRICE_UPDATE)
        object.__setattr__(self, "timestamp_ns", price.timestamp_ns)
        object.__setattr__(self, "correlation_id", correlation_id or uuid.uuid4())
        object.__setattr__(self, "price", price)


@dataclass(slots=True, frozen=True)
class SignalEvent(Event):
    """Alpha model output — a trading signal."""

    market_id: str = ""
    direction: Direction = Direction.NEUTRAL
    strength: Decimal = Decimal("0")
    probability: Decimal = Decimal("0")
    features: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        market_id: str,
        direction: Direction,
        strength: Decimal,
        probability: Decimal,
        features: dict[str, Any],
        timestamp_ns: int,
        correlation_id: uuid.UUID | None = None,
    ) -> None:
        object.__setattr__(self, "event_type", EventType.SIGNAL)
        object.__setattr__(self, "timestamp_ns", timestamp_ns)
        object.__setattr__(self, "correlation_id", correlation_id or uuid.uuid4())
        object.__setattr__(self, "market_id", market_id)
        object.__setattr__(self, "direction", direction)
        object.__setattr__(self, "strength", strength)
        object.__setattr__(self, "probability", probability)
        object.__setattr__(self, "features", features)


@dataclass(slots=True, frozen=True)
class OrderRequestEvent(Event):
    """Strategy wants to place a trade."""

    market_id: str = ""
    token_id: str = ""
    side: Side = Side.BUY
    price: Decimal = Decimal("0")
    size: Decimal = Decimal("0")

    def __init__(
        self,
        market_id: str,
        token_id: str,
        side: Side,
        price: Decimal,
        size: Decimal,
        timestamp_ns: int,
        correlation_id: uuid.UUID | None = None,
    ) -> None:
        object.__setattr__(self, "event_type", EventType.ORDER_REQUEST)
        object.__setattr__(self, "timestamp_ns", timestamp_ns)
        object.__setattr__(self, "correlation_id", correlation_id or uuid.uuid4())
        object.__setattr__(self, "market_id", market_id)
        object.__setattr__(self, "token_id", token_id)
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "price", price)
        object.__setattr__(self, "size", size)


@dataclass(slots=True, frozen=True)
class OrderStatusEvent(Event):
    """Order lifecycle update."""

    order: Order | None = None
    previous_status: OrderStatus = OrderStatus.PENDING

    def __init__(
        self,
        order: Order,
        previous_status: OrderStatus,
        correlation_id: uuid.UUID | None = None,
    ) -> None:
        object.__setattr__(self, "event_type", EventType.ORDER_STATUS)
        object.__setattr__(self, "timestamp_ns", order.updated_at)
        object.__setattr__(self, "correlation_id", correlation_id or uuid.uuid4())
        object.__setattr__(self, "order", order)
        object.__setattr__(self, "previous_status", previous_status)


@dataclass(slots=True, frozen=True)
class FillEvent(Event):
    """Execution confirmed — trade happened."""

    fill: Fill | None = None

    def __init__(self, fill: Fill, correlation_id: uuid.UUID | None = None) -> None:
        object.__setattr__(self, "event_type", EventType.FILL)
        object.__setattr__(self, "timestamp_ns", fill.timestamp_ns)
        object.__setattr__(self, "correlation_id", correlation_id or uuid.uuid4())
        object.__setattr__(self, "fill", fill)


@dataclass(slots=True, frozen=True)
class AlertEvent(Event):
    """Something needs human attention."""

    severity: str = "INFO"  # INFO, WARNING, CRITICAL
    source: str = ""
    message: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def __init__(
        self,
        severity: str,
        source: str,
        message: str,
        timestamp_ns: int,
        details: dict[str, Any] | None = None,
        correlation_id: uuid.UUID | None = None,
    ) -> None:
        object.__setattr__(self, "event_type", EventType.ALERT)
        object.__setattr__(self, "timestamp_ns", timestamp_ns)
        object.__setattr__(self, "correlation_id", correlation_id or uuid.uuid4())
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "details", details or {})


@dataclass(slots=True, frozen=True)
class HeartbeatEvent(Event):
    """Component liveness signal."""

    component: str = ""

    def __init__(
        self, component: str, timestamp_ns: int, correlation_id: uuid.UUID | None = None
    ) -> None:
        object.__setattr__(self, "event_type", EventType.HEARTBEAT)
        object.__setattr__(self, "timestamp_ns", timestamp_ns)
        object.__setattr__(self, "correlation_id", correlation_id or uuid.uuid4())
        object.__setattr__(self, "component", component)


# ---------------------------------------------------------------------------
# Event Bus
# ---------------------------------------------------------------------------


class EventBus:
    """Async event bus with per-type queues and error isolation.

    Usage:
        bus = EventBus()
        bus.subscribe(EventType.TICK, my_handler)
        await bus.start()
        await bus.publish(TickEvent(tick=my_tick))
        await bus.stop()
    """

    def __init__(self, max_queue_size: int = 10_000) -> None:
        self._subscribers: dict[EventType, list[EventHandler]] = {}
        self._queues: dict[EventType, asyncio.Queue[Event]] = {}
        self._tasks: list[asyncio.Task[None]] = []
        self._running = False
        self._max_queue_size = max_queue_size

    def subscribe(self, event_type: EventType, handler: EventHandler) -> None:
        """Register an async handler for an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    async def publish(self, event: Event) -> None:
        """Dispatch an event to all subscribers of its type."""
        if not self._running:
            raise RuntimeError("EventBus is not running. Call start() first.")

        queue = self._queues.get(event.event_type)
        if queue is not None:
            await queue.put(event)

    async def start(self) -> None:
        """Start consumer tasks for each subscribed event type."""
        if self._running:
            return

        self._running = True

        for event_type, handlers in self._subscribers.items():
            queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._max_queue_size)
            self._queues[event_type] = queue
            task = asyncio.create_task(
                self._consume(event_type, queue, handlers),
                name=f"event-bus-{event_type.name}",
            )
            self._tasks.append(task)

    async def stop(self) -> None:
        """Gracefully shut down all consumer tasks."""
        if not self._running:
            return

        self._running = False

        # Signal consumers to stop by putting None sentinel
        for queue in self._queues.values():
            await queue.put(None)  # type: ignore[arg-type]

        # Wait for all consumers to finish processing
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks.clear()
        self._queues.clear()

    async def _consume(
        self,
        event_type: EventType,
        queue: asyncio.Queue[Event],
        handlers: list[EventHandler],
    ) -> None:
        """Consumer loop: drain queue and invoke handlers with error isolation."""
        while self._running:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
            except TimeoutError:
                continue

            if event is None:  # Shutdown sentinel
                break

            for handler in handlers:
                try:
                    await handler(event)
                except Exception:
                    logger.exception(
                        "Handler %s failed for %s event",
                        handler.__qualname__,
                        event_type.name,
                        extra={"correlation_id": str(event.correlation_id)},
                    )

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def subscriber_count(self) -> dict[EventType, int]:
        return {et: len(hs) for et, hs in self._subscribers.items()}
