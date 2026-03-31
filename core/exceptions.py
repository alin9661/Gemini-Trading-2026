"""Typed exception hierarchy for the trading system.

Each layer has its own exception family. This enables:
- Precise error handling (catch DataError vs ExecutionError)
- Clear error propagation across layers
- Structured logging with error context
"""

from __future__ import annotations


class TradingError(Exception):
    """Base exception for all trading system errors."""


# ---------------------------------------------------------------------------
# Data Layer
# ---------------------------------------------------------------------------


class DataError(TradingError):
    """Error in the data ingestion or normalization pipeline."""


class FeedDisconnectedError(DataError):
    """WebSocket feed lost connection."""

    def __init__(self, exchange: str, reason: str = "") -> None:
        self.exchange = exchange
        self.reason = reason
        super().__init__(f"Feed disconnected: {exchange}" + (f" ({reason})" if reason else ""))


class StaleDataError(DataError):
    """Data from an exchange is older than acceptable threshold."""

    def __init__(self, exchange: str, age_seconds: float) -> None:
        self.exchange = exchange
        self.age_seconds = age_seconds
        super().__init__(f"Stale data from {exchange}: {age_seconds:.1f}s old")


class NormalizationError(DataError):
    """Failed to normalize/validate price data across exchanges."""


# ---------------------------------------------------------------------------
# Strategy Layer
# ---------------------------------------------------------------------------


class StrategyError(TradingError):
    """Error in strategy computation."""


class RiskLimitExceededError(StrategyError):
    """A risk limit would be breached by the proposed action."""

    def __init__(self, limit_name: str, current: float, maximum: float) -> None:
        self.limit_name = limit_name
        self.current = current
        self.maximum = maximum
        super().__init__(
            f"Risk limit exceeded: {limit_name} (current={current}, max={maximum})"
        )


class SignalGenerationError(StrategyError):
    """Failed to generate a trading signal."""


# ---------------------------------------------------------------------------
# Execution Layer
# ---------------------------------------------------------------------------


class ExecutionError(TradingError):
    """Error in order execution."""


class OrderRejectedError(ExecutionError):
    """Order was rejected by the exchange/CLOB."""

    def __init__(self, order_id: str, reason: str) -> None:
        self.order_id = order_id
        self.reason = reason
        super().__init__(f"Order {order_id} rejected: {reason}")


class InsufficientBalanceError(ExecutionError):
    """Not enough funds to place the order."""

    def __init__(self, required: float, available: float) -> None:
        self.required = required
        self.available = available
        super().__init__(f"Insufficient balance: need {required}, have {available}")


class GasError(ExecutionError):
    """On-chain gas/MATIC balance issue."""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class ConfigError(TradingError):
    """Invalid or missing configuration."""
