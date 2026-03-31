"""Tests for core domain types — Decimal enforcement, validation, enum behavior."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from core.types import (
    Direction,
    Fill,
    Order,
    OrderStatus,
    OrderType,
    Position,
    Side,
    Signal,
    Tick,
)


class TestTick:
    def test_valid_tick(self) -> None:
        tick = Tick(
            exchange="coinbase",
            symbol="BTC-USD",
            bid=Decimal("67800.50"),
            ask=Decimal("67801.00"),
            mid=Decimal("67800.75"),
            bid_size=Decimal("1.5"),
            ask_size=Decimal("2.0"),
            timestamp_ns=1_700_000_000_000_000_000,
        )
        assert tick.exchange == "coinbase"
        assert isinstance(tick.bid, Decimal)

    def test_negative_price_rejected(self) -> None:
        with pytest.raises(ValueError, match="Negative price"):
            Tick(
                exchange="test",
                symbol="BTC-USD",
                bid=Decimal("-1"),
                ask=Decimal("100"),
                mid=Decimal("50"),
                bid_size=Decimal("1"),
                ask_size=Decimal("1"),
                timestamp_ns=1_700_000_000_000_000_000,
            )

    def test_crossed_book_rejected(self) -> None:
        with pytest.raises(ValueError, match="Crossed book"):
            Tick(
                exchange="test",
                symbol="BTC-USD",
                bid=Decimal("100"),
                ask=Decimal("99"),
                mid=Decimal("99.5"),
                bid_size=Decimal("1"),
                ask_size=Decimal("1"),
                timestamp_ns=1_700_000_000_000_000_000,
            )

    def test_zero_timestamp_rejected(self) -> None:
        with pytest.raises(ValueError, match="Invalid timestamp"):
            Tick(
                exchange="test",
                symbol="BTC-USD",
                bid=Decimal("100"),
                ask=Decimal("101"),
                mid=Decimal("100.5"),
                bid_size=Decimal("1"),
                ask_size=Decimal("1"),
                timestamp_ns=0,
            )

    def test_tick_is_frozen(self) -> None:
        tick = Tick(
            exchange="test",
            symbol="BTC-USD",
            bid=Decimal("100"),
            ask=Decimal("101"),
            mid=Decimal("100.5"),
            bid_size=Decimal("1"),
            ask_size=Decimal("1"),
            timestamp_ns=1_700_000_000_000_000_000,
        )
        with pytest.raises(AttributeError):
            tick.bid = Decimal("200")  # type: ignore[misc]


class TestSignal:
    def test_valid_signal(self) -> None:
        signal = Signal(
            market_id="btc-15m-up",
            direction=Direction.LONG,
            strength=Decimal("0.75"),
            probability=Decimal("0.62"),
            features={"momentum": 0.5},
            timestamp_ns=1_700_000_000_000_000_000,
        )
        assert signal.direction == Direction.LONG

    def test_strength_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="Strength must be 0-1"):
            Signal(
                market_id="test",
                direction=Direction.LONG,
                strength=Decimal("1.5"),
                probability=Decimal("0.5"),
                features={},
                timestamp_ns=1_700_000_000_000_000_000,
            )

    def test_probability_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="Probability must be 0-1"):
            Signal(
                market_id="test",
                direction=Direction.LONG,
                strength=Decimal("0.5"),
                probability=Decimal("-0.1"),
                features={},
                timestamp_ns=1_700_000_000_000_000_000,
            )


class TestOrder:
    def test_create_factory(self) -> None:
        order = Order.create(
            market_id="btc-15m",
            token_id="0xabc",
            side=Side.BUY,
            price=Decimal("0.58"),
            size=Decimal("50"),
            order_type=OrderType.LIMIT,
            timestamp_ns=1_700_000_000_000_000_000,
        )
        assert order.status == OrderStatus.PENDING
        assert isinstance(order.id, uuid.UUID)
        assert order.created_at == 1_700_000_000_000_000_000

    def test_order_status_mutable(self) -> None:
        order = Order.create(
            market_id="test",
            token_id="0x1",
            side=Side.SELL,
            price=Decimal("0.45"),
            size=Decimal("10"),
            order_type=OrderType.MARKET,
            timestamp_ns=1_700_000_000_000_000_000,
        )
        order.status = OrderStatus.SENT
        assert order.status == OrderStatus.SENT


class TestFill:
    def test_fill_creation(self) -> None:
        oid = uuid.uuid4()
        fill = Fill(
            order_id=oid,
            price=Decimal("0.58"),
            size=Decimal("50"),
            fee=Decimal("0.01"),
            timestamp_ns=1_700_000_000_000_000_000,
        )
        assert fill.order_id == oid
        assert isinstance(fill.fee, Decimal)


class TestPosition:
    def test_notional_calculation(self) -> None:
        pos = Position(
            market_id="test",
            token_id="0x1",
            side=Side.BUY,
            size=Decimal("100"),
            avg_entry=Decimal("0.55"),
        )
        assert pos.notional == Decimal("55.00")

    def test_default_unrealized_pnl(self) -> None:
        pos = Position(
            market_id="test",
            token_id="0x1",
            side=Side.BUY,
            size=Decimal("10"),
            avg_entry=Decimal("0.50"),
        )
        assert pos.unrealized_pnl == Decimal("0")


class TestEnums:
    def test_side_values(self) -> None:
        assert Side.BUY != Side.SELL

    def test_order_status_lifecycle(self) -> None:
        # Verify all expected statuses exist
        statuses = [s.name for s in OrderStatus]
        assert "PENDING" in statuses
        assert "SENT" in statuses
        assert "PARTIAL" in statuses
        assert "FILLED" in statuses
        assert "CANCELLED" in statuses
        assert "REJECTED" in statuses
