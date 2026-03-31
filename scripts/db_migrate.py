"""TimescaleDB schema migration — idempotent, safe to re-run.

Creates hypertables for time-series data (ticks, prices, signals, P&L snapshots)
and regular tables for application state (orders, fills).

Usage:
    uv run python -m scripts.db_migrate
    # or: make migrate
"""

from __future__ import annotations

import asyncio
import logging
import sys

import asyncpg

from config.settings import Settings

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
-- ==========================================================================
-- Hypertable: raw ticks from all exchanges
-- ==========================================================================
CREATE TABLE IF NOT EXISTS ticks (
    timestamp_ns BIGINT NOT NULL,
    exchange     TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    bid          NUMERIC(20, 8) NOT NULL,
    ask          NUMERIC(20, 8) NOT NULL,
    mid          NUMERIC(20, 8) NOT NULL,
    bid_size     NUMERIC(20, 8),
    ask_size     NUMERIC(20, 8)
);

-- create_hypertable is not idempotent, so we check first
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'ticks'
    ) THEN
        PERFORM create_hypertable('ticks', by_range('timestamp_ns'));
    END IF;
END $$;

-- Compress chunks older than 1 day (86400 seconds * 1e9 nanoseconds)
ALTER TABLE ticks SET (timescaledb.compress);
SELECT add_compression_policy('ticks', BIGINT '86400000000000', if_not_exists => true);

-- ==========================================================================
-- Hypertable: normalized prices
-- ==========================================================================
CREATE TABLE IF NOT EXISTS prices (
    timestamp_ns BIGINT NOT NULL,
    symbol       TEXT NOT NULL,
    price        NUMERIC(20, 8) NOT NULL,
    source       TEXT NOT NULL,
    n_sources    INTEGER NOT NULL
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'prices'
    ) THEN
        PERFORM create_hypertable('prices', by_range('timestamp_ns'));
    END IF;
END $$;

ALTER TABLE prices SET (timescaledb.compress);
SELECT add_compression_policy('prices', BIGINT '86400000000000', if_not_exists => true);

-- ==========================================================================
-- Regular table: orders (queried by ID, not time range)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS orders (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id     TEXT NOT NULL,
    token_id      TEXT NOT NULL,
    side          TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    price         NUMERIC(10, 4) NOT NULL,
    size          NUMERIC(20, 8) NOT NULL,
    order_type    TEXT NOT NULL,
    status        TEXT NOT NULL DEFAULT 'PENDING',
    clob_order_id TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ==========================================================================
-- Regular table: fills
-- ==========================================================================
CREATE TABLE IF NOT EXISTS fills (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id     UUID REFERENCES orders(id),
    price        NUMERIC(10, 4) NOT NULL,
    size         NUMERIC(20, 8) NOT NULL,
    fee          NUMERIC(20, 8) DEFAULT 0,
    timestamp_ns BIGINT NOT NULL
);

-- ==========================================================================
-- Hypertable: signals (decision audit trail)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS signals (
    timestamp_ns BIGINT NOT NULL,
    market_id    TEXT NOT NULL,
    direction    TEXT NOT NULL,
    strength     NUMERIC(10, 6) NOT NULL,
    probability  NUMERIC(10, 6) NOT NULL,
    features     JSONB NOT NULL,
    order_id     UUID REFERENCES orders(id)
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'signals'
    ) THEN
        PERFORM create_hypertable('signals', by_range('timestamp_ns'));
    END IF;
END $$;

-- ==========================================================================
-- Hypertable: P&L snapshots
-- ==========================================================================
CREATE TABLE IF NOT EXISTS pnl_snapshots (
    timestamp_ns   BIGINT NOT NULL,
    market_id      TEXT NOT NULL,
    unrealized_pnl NUMERIC(20, 8) NOT NULL,
    realized_pnl   NUMERIC(20, 8) NOT NULL,
    position_size  NUMERIC(20, 8) NOT NULL,
    mark_price     NUMERIC(10, 4) NOT NULL
);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables
        WHERE hypertable_name = 'pnl_snapshots'
    ) THEN
        PERFORM create_hypertable('pnl_snapshots', by_range('timestamp_ns'));
    END IF;
END $$;

ALTER TABLE pnl_snapshots SET (timescaledb.compress);
SELECT add_compression_policy('pnl_snapshots', BIGINT '86400000000000', if_not_exists => true);

-- ==========================================================================
-- Indexes
-- ==========================================================================
CREATE INDEX IF NOT EXISTS idx_ticks_exchange_symbol ON ticks (exchange, symbol, timestamp_ns DESC);
CREATE INDEX IF NOT EXISTS idx_prices_symbol ON prices (symbol, timestamp_ns DESC);
CREATE INDEX IF NOT EXISTS idx_orders_market ON orders (market_id, status);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);
CREATE INDEX IF NOT EXISTS idx_fills_order ON fills (order_id);
CREATE INDEX IF NOT EXISTS idx_signals_market ON signals (market_id, timestamp_ns DESC);
"""


async def run_migration(database_url: str) -> None:
    """Execute the schema migration against the given database."""
    conn = await asyncpg.connect(database_url)
    try:
        logger.info("Running database migration...")
        await conn.execute(SCHEMA_SQL)
        logger.info("Migration completed successfully.")

        # Verify tables exist
        tables = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
        table_names = [t["tablename"] for t in tables]
        logger.info("Tables: %s", ", ".join(table_names))
    finally:
        await conn.close()


async def main() -> None:
    settings = Settings()
    await run_migration(settings.database.url)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    asyncio.run(main())
