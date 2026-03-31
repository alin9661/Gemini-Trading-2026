"""Core domain types for the trading system.

All prices are Decimal (never float). All timestamps are int nanoseconds (Unix epoch).
Dataclasses use __slots__ for memory efficiency and attribute access speed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum, auto
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Side(Enum):
    BUY = auto()
    SELL = auto()


class Direction(Enum):
    LONG = auto()
    SHORT = auto()
    NEUTRAL = auto()


class OrderType(Enum):
    LIMIT = auto()
    MARKET = auto()


class OrderStatus(Enum):
    """Order lifecycle state machine.

    PENDING → SENT → PARTIAL → FILLED
                  → CANCELLED
                  → REJECTED
    """

    PENDING = auto()
    SENT = auto()
    PARTIAL = auto()
    FILLED = auto()
    CANCELLED = auto()
    REJECTED = auto()


# ---------------------------------------------------------------------------
# Domain Types
# ---------------------------------------------------------------------------


@dataclass(slots=True, frozen=True)
class Tick:
    """Raw price update from a single exchange."""

    exchange: str
    symbol: str
    bid: Decimal
    ask: Decimal
    mid: Decimal
    bid_size: Decimal
    ask_size: Decimal
    timestamp_ns: int

    def __post_init__(self) -> None:
        if self.bid < 0 or self.ask < 0:
            raise ValueError(f"Negative price: bid={self.bid}, ask={self.ask}")
        if self.ask < self.bid:
            raise ValueError(f"Crossed book: bid={self.bid} > ask={self.ask}")
        if self.timestamp_ns <= 0:
            raise ValueError(f"Invalid timestamp: {self.timestamp_ns}")


@dataclass(slots=True, frozen=True)
class NormalizedPrice:
    """Cross-validated price from multiple exchanges."""

    symbol: str
    price: Decimal
    source: str  # 'median', 'vwap', etc.
    confidence: Decimal  # 0-1, how many sources agree
    timestamp_ns: int
    n_sources: int = 0


@dataclass(slots=True, frozen=True)
class Signal:
    """Alpha model output — a directional prediction."""

    market_id: str
    direction: Direction
    strength: Decimal  # 0-1, conviction level
    probability: Decimal  # estimated probability of outcome
    features: dict[str, Any]
    timestamp_ns: int

    def __post_init__(self) -> None:
        if not (Decimal("0") <= self.strength <= Decimal("1")):
            raise ValueError(f"Strength must be 0-1, got {self.strength}")
        if not (Decimal("0") <= self.probability <= Decimal("1")):
            raise ValueError(f"Probability must be 0-1, got {self.probability}")


@dataclass(slots=True)
class Order:
    """Trade intent — tracks full lifecycle from creation to fill/cancel."""

    id: uuid.UUID
    market_id: str
    token_id: str
    side: Side
    price: Decimal
    size: Decimal
    order_type: OrderType
    status: OrderStatus = OrderStatus.PENDING
    clob_order_id: str | None = None
    created_at: int = 0  # timestamp_ns
    updated_at: int = 0  # timestamp_ns

    @staticmethod
    def create(
        market_id: str,
        token_id: str,
        side: Side,
        price: Decimal,
        size: Decimal,
        order_type: OrderType,
        timestamp_ns: int,
    ) -> Order:
        """Factory for creating new orders with auto-generated ID."""
        return Order(
            id=uuid.uuid4(),
            market_id=market_id,
            token_id=token_id,
            side=side,
            price=price,
            size=size,
            order_type=order_type,
            created_at=timestamp_ns,
            updated_at=timestamp_ns,
        )


@dataclass(slots=True, frozen=True)
class Fill:
    """Execution confirmation — a trade that actually happened."""

    order_id: uuid.UUID
    price: Decimal
    size: Decimal
    fee: Decimal
    timestamp_ns: int


@dataclass(slots=True)
class Position:
    """Current holding in a specific market."""

    market_id: str
    token_id: str
    side: Side
    size: Decimal
    avg_entry: Decimal
    unrealized_pnl: Decimal = field(default_factory=lambda: Decimal("0"))

    @property
    def notional(self) -> Decimal:
        return self.size * self.avg_entry
