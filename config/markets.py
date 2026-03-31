"""Market definitions for Polymarket prediction markets.

Each market has a condition ID (the question being predicted) and two token IDs
(YES and NO outcomes). These IDs come from the Polymarket CLOB API.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True, frozen=True)
class MarketDefinition:
    """Metadata for a single Polymarket prediction market."""

    name: str
    condition_id: str
    token_id_yes: str
    token_id_no: str
    tick_size: Decimal
    min_order_size: Decimal
    description: str = ""

    @property
    def token_ids(self) -> tuple[str, str]:
        return (self.token_id_yes, self.token_id_no)


# ---------------------------------------------------------------------------
# Known Markets (populated at runtime from Polymarket API, these are examples)
# ---------------------------------------------------------------------------

# BTC 15-minute price direction markets are created dynamically by Polymarket.
# These placeholder IDs should be replaced with real IDs from the CLOB API.
BTC_15MIN_EXAMPLE = MarketDefinition(
    name="BTC 15min Up",
    condition_id="0x_placeholder_condition_id",
    token_id_yes="0x_placeholder_yes_token",
    token_id_no="0x_placeholder_no_token",
    tick_size=Decimal("0.01"),
    min_order_size=Decimal("5.0"),
    description="Will BTC go up in the next 15 minutes?",
)
