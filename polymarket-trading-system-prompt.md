# Claude Code Prompt: Polymarket Quantitative Trading System — Boilerplate Infrastructure

## Who You Are

You are a senior systems architect with deep experience building low-latency trading infrastructure at firms like Jane Street, Citadel Securities, and Hudson River Trading. You understand that trading systems die from plumbing failures, not model failures. Your job is to build production-grade boilerplate infrastructure for a quantitative trading system targeting Polymarket prediction markets, starting with BTC 15-minute price direction markets.

This is a **research-phase build** — Python for fast iteration, but architected so the execution layer can be ported to Rust later without touching the data or strategy layers. Every design decision should reflect that this system will eventually handle real capital.

---

## System Overview

Build a modular, event-driven Python trading system with the following architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                      DATA LAYER                             │
│                                                             │
│  Coinbase WS ─┐                                            │
│  Binance WS  ─┼─→ Normalizer ─→ Internal API ─→ TimescaleDB│
│  Kraken WS   ─┘       │              │                     │
│                        │              ├─→ Redis (pub/sub)   │
│  Polymarket REST ──────┤              │                     │
│  Polymarket WS ────────┘              └─→ Feature Store     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                    STRATEGY LAYER                           │
│                                                             │
│  Signal Generator ─→ Alpha Model ─→ Risk Manager ─→ Sizer  │
│       │                    │              │            │     │
│       └── Feature Store    └── Model Registry         │     │
│                                                       │     │
├───────────────────────────────────────────────────────┼─────┤
│                   EXECUTION LAYER                     │     │
│                                                       ▼     │
│  Order Manager ─→ Polymarket CLOB ─→ Fill Tracker           │
│       │              (py-clob-client)       │                │
│       └── Paper Trading Mode               └── P&L Engine  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│                 OBSERVABILITY LAYER                          │
│                                                             │
│  Structured Logging ─→ Metrics (Prometheus) ─→ Alerting     │
│  Decision Audit Log ─→ Grafana Dashboards                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
polymarket-trading/
├── pyproject.toml                    # uv/poetry project config
├── .env.example                      # Template for secrets
├── docker-compose.yml                # Local dev: TimescaleDB, Redis, Prometheus, Grafana
├── Makefile                          # Common commands
│
├── config/
│   ├── settings.py                   # Pydantic Settings — all config from env vars
│   ├── markets.py                    # Market definitions, token IDs, tick sizes
│   └── logging.py                    # Structured logging config (structlog)
│
├── core/
│   ├── events.py                     # Event bus — asyncio pub/sub backbone
│   ├── types.py                      # Domain types: Price, Order, Fill, Position, Signal
│   ├── clock.py                      # System clock abstraction (real + simulated for backtests)
│   └── exceptions.py                 # Typed exception hierarchy
│
├── data/
│   ├── base.py                       # Abstract base: DataFeed protocol
│   ├── websocket_manager.py          # Reconnecting WS with exponential backoff, heartbeat
│   ├── feeds/
│   │   ├── coinbase.py               # Coinbase Pro WS feed → normalized ticks
│   │   ├── binance.py                # Binance WS feed → normalized ticks
│   │   ├── kraken.py                 # Kraken WS feed → normalized ticks
│   │   └── polymarket.py             # Polymarket WS (market channel) + REST client
│   ├── normalizer.py                 # Cross-exchange price normalization, VWAP, mid-price
│   ├── store.py                      # TimescaleDB writer — async batch inserts
│   └── cache.py                      # Redis interface — latest prices, pub/sub for signals
│
├── features/
│   ├── base.py                       # Abstract Feature protocol
│   ├── registry.py                   # Feature registration, dependency resolution
│   ├── price_features.py             # Returns, volatility, momentum, microstructure
│   ├── orderbook_features.py         # Spread, depth imbalance, book pressure
│   └── cross_market_features.py      # Polymarket vs. spot divergence, implied vol skew
│
├── strategy/
│   ├── base.py                       # Abstract Strategy protocol
│   ├── alpha_model.py                # Probability estimation → signal generation
│   ├── risk_manager.py               # Position limits, drawdown circuit breakers, exposure caps
│   ├── sizing.py                     # Kelly Criterion with fractional Kelly (half-Kelly default)
│   └── arbitrage/
│       ├── intra_market.py           # YES + NO deviation monitoring (|p_yes + p_no - 1| > threshold)
│       └── cross_market.py           # Dependency graph + Bregman projection stub
│
├── execution/
│   ├── base.py                       # Abstract Executor protocol
│   ├── polymarket_executor.py        # py-clob-client wrapper — order creation, signing, posting
│   ├── paper_trader.py               # Simulated fills against snapshot order book
│   ├── order_manager.py              # Order lifecycle: pending → sent → partial → filled/cancelled
│   ├── fill_tracker.py               # Fill reconciliation, execution quality analytics
│   └── gas_manager.py                # MATIC balance monitoring, auto-top-up alerts
│
├── portfolio/
│   ├── position_manager.py           # Real-time position tracking per market
│   ├── pnl_engine.py                 # Mark-to-market, realized/unrealized P&L, Sharpe, drawdown
│   └── reconciliation.py             # Cross-check internal state vs. on-chain/API positions
│
├── observability/
│   ├── metrics.py                    # Prometheus metrics: latency histograms, fill rates, P&L gauges
│   ├── alerts.py                     # Alert rules: WS disconnect, drawdown breach, model drift
│   ├── decision_log.py               # Every signal/order decision logged with full context (audit trail)
│   └── health.py                     # HTTP health endpoint for external monitoring
│
├── backtest/
│   ├── engine.py                     # Event-driven backtester using same strategy/execution interfaces
│   ├── data_loader.py                # Load historical data from TimescaleDB
│   └── report.py                     # Backtest analytics: equity curve, drawdown, trade log
│
├── scripts/
│   ├── run_data_collector.py         # Entry: connect feeds, write to DB
│   ├── run_strategy.py               # Entry: consume signals, generate orders
│   ├── run_paper_trader.py           # Entry: full pipeline in paper mode
│   └── db_migrate.py                 # TimescaleDB schema setup
│
└── tests/
    ├── conftest.py                   # Shared fixtures: mock feeds, test DB, fake clock
    ├── test_normalizer.py
    ├── test_sizing.py                # Kelly sizing edge cases, estimation error scenarios
    ├── test_order_manager.py
    └── test_event_bus.py
```

---

## Detailed Implementation Requirements

### 1. Core Domain Types (`core/types.py`)

Use `dataclasses` with `__slots__` for performance. All prices as `Decimal` — never float for money. Timestamps as `int` nanoseconds (Unix epoch).

```python
# Key types to define:
# - Tick(exchange, symbol, bid, ask, mid, bid_size, ask_size, timestamp_ns)
# - NormalizedPrice(symbol, price, source, confidence, timestamp_ns)
# - Signal(market_id, direction, strength, probability, features, timestamp_ns)
# - Order(id, market_id, token_id, side, price, size, order_type, status, created_at)
# - Fill(order_id, price, size, fee, timestamp_ns)
# - Position(market_id, token_id, side, size, avg_entry, unrealized_pnl)
```

### 2. Event Bus (`core/events.py`)

Async event bus using `asyncio.Queue`. This is the nervous system of the entire application. All components communicate through typed events, never direct function calls between layers.

Events to define:
- `TickEvent` — raw price update from any exchange
- `PriceUpdateEvent` — normalized, cross-validated price
- `SignalEvent` — alpha model output
- `OrderRequestEvent` — strategy wants to trade
- `OrderStatusEvent` — order accepted/rejected/filled/cancelled
- `FillEvent` — execution confirmed
- `AlertEvent` — something needs human attention
- `HeartbeatEvent` — component liveness

### 3. WebSocket Manager (`data/websocket_manager.py`)

This is the most failure-prone component. Build it like it's going to run for months unattended:

- Automatic reconnection with exponential backoff (initial 1s, max 60s, jitter)
- Heartbeat monitoring — if no message received in N seconds, force reconnect
- Message sequence tracking — detect gaps
- Per-connection metrics: messages/sec, reconnect count, last message timestamp
- Graceful shutdown with drain
- Connection state machine: CONNECTING → CONNECTED → SUBSCRIBING → ACTIVE → RECONNECTING → CLOSED

### 4. Exchange Feed Implementations (`data/feeds/`)

Each feed normalizes to `Tick` objects. Critical implementation details:

**Coinbase (`coinbase.py`)**:
- WebSocket URL: `wss://ws-feed.exchange.coinbase.com`
- Subscribe to `ticker` channel for BTC-USD
- Message format includes `best_bid`, `best_ask`, `price`, `time`

**Binance (`binance.py`)**:
- WebSocket URL: `wss://stream.binance.com:9443/ws/btcusdt@bookTicker`
- `bookTicker` stream for best bid/ask updates (fastest)
- Also subscribe to `@trade` for last trade price

**Kraken (`kraken.py`)**:
- WebSocket URL: `wss://ws.kraken.com`
- Subscribe to `ticker` for XBT/USD
- Their message format uses arrays, not JSON objects — handle carefully

**Polymarket (`polymarket.py`)**:
- Market WebSocket: `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- Subscribe with asset IDs for BTC prediction markets
- REST endpoints (no auth needed): `GET /price`, `GET /book`, `GET /midpoint` at `https://clob.polymarket.com`
- For authenticated trading: `py-clob-client` SDK with L1/L2 auth flow
- Track `tick_size`, `minimum_order_size`, and `accepting_orders` per market

### 5. Price Normalizer (`data/normalizer.py`)

Cross-validate BTC prices across exchanges. Reject outliers. Compute:
- Median price across exchanges (robust to single-exchange glitches)
- Volume-weighted mid-price when depth data is available
- Staleness detection — if an exchange hasn't updated in >5s, exclude it
- Cross-exchange spread as a liquidity/stress indicator

### 6. Internal API / Cache Layer (`data/cache.py`)

Redis-backed, serves as the real-time state bus:
- `SET price:btc:latest` — most recent normalized price (JSON, TTL 30s)
- `PUBLISH channel:prices` — every normalized price update
- `PUBLISH channel:signals` — strategy signals for execution layer
- `SET book:polymarket:{token_id}` — latest order book snapshot
- `SET position:{market_id}` — current position state
- Use Redis Streams (`XADD`/`XREAD`) for durable event replay

### 7. TimescaleDB Schema (`scripts/db_migrate.py`)

```sql
-- Hypertable for raw ticks
CREATE TABLE ticks (
    timestamp_ns BIGINT NOT NULL,
    exchange     TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    bid          NUMERIC(20, 8) NOT NULL,
    ask          NUMERIC(20, 8) NOT NULL,
    mid          NUMERIC(20, 8) NOT NULL,
    bid_size     NUMERIC(20, 8),
    ask_size     NUMERIC(20, 8)
);
SELECT create_hypertable('ticks', by_range('timestamp_ns'));
-- Compress chunks older than 1 day
ALTER TABLE ticks SET (timescaledb.compress);
SELECT add_compression_policy('ticks', BIGINT '86400000000000'); -- 1 day in ns

-- Normalized prices
CREATE TABLE prices (
    timestamp_ns BIGINT NOT NULL,
    symbol       TEXT NOT NULL,
    price        NUMERIC(20, 8) NOT NULL,
    source       TEXT NOT NULL, -- 'median', 'vwap', etc.
    n_sources    INTEGER NOT NULL
);
SELECT create_hypertable('prices', by_range('timestamp_ns'));

-- Orders (application state — regular Postgres table)
CREATE TABLE orders (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market_id    TEXT NOT NULL,
    token_id     TEXT NOT NULL,
    side         TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    price        NUMERIC(10, 4) NOT NULL,
    size         NUMERIC(20, 8) NOT NULL,
    order_type   TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'PENDING',
    clob_order_id TEXT,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Fills
CREATE TABLE fills (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id     UUID REFERENCES orders(id),
    price        NUMERIC(10, 4) NOT NULL,
    size         NUMERIC(20, 8) NOT NULL,
    fee          NUMERIC(20, 8) DEFAULT 0,
    timestamp_ns BIGINT NOT NULL
);

-- Signals (decision audit trail)
CREATE TABLE signals (
    timestamp_ns BIGINT NOT NULL,
    market_id    TEXT NOT NULL,
    direction    TEXT NOT NULL,
    strength     NUMERIC(10, 6) NOT NULL,
    probability  NUMERIC(10, 6) NOT NULL,
    features     JSONB NOT NULL,
    order_id     UUID REFERENCES orders(id)
);
SELECT create_hypertable('signals', by_range('timestamp_ns'));

-- P&L snapshots
CREATE TABLE pnl_snapshots (
    timestamp_ns      BIGINT NOT NULL,
    market_id         TEXT NOT NULL,
    unrealized_pnl    NUMERIC(20, 8) NOT NULL,
    realized_pnl      NUMERIC(20, 8) NOT NULL,
    position_size     NUMERIC(20, 8) NOT NULL,
    mark_price        NUMERIC(10, 4) NOT NULL
);
SELECT create_hypertable('pnl_snapshots', by_range('timestamp_ns'));
```

### 8. Kelly Criterion Sizing (`strategy/sizing.py`)

Implement with estimation error awareness. This is NOT textbook Kelly:

```python
# Core sizing logic:
# 1. Compute raw Kelly: f* = (p * b - q) / b
#    where p = estimated probability, q = 1-p, b = decimal odds
# 2. Apply fractional Kelly (default: half-Kelly, configurable)
# 3. Apply hard position limits from risk manager
# 4. Apply bankroll percentage caps (never more than X% of capital on one trade)
# 5. Log the full sizing decision: raw kelly, adjusted kelly, final size, reason for adjustment
#
# CRITICAL: When probability estimation confidence is low,
# reduce Kelly fraction further. Naive full Kelly is a path to ruin
# when your p-hat has high variance.
```

### 9. Risk Manager (`strategy/risk_manager.py`)

Non-negotiable hard limits:
- Maximum position size per market (absolute and as % of bankroll)
- Maximum total exposure across all markets
- Maximum drawdown circuit breaker (e.g., 10% daily drawdown → halt all trading)
- Maximum loss per trade
- Minimum time between trades (prevent rapid-fire errors)
- Kill switch: one function call halts all trading and cancels open orders

### 10. Paper Trader (`execution/paper_trader.py`)

Simulates execution against real order book snapshots:
- Uses the same `Executor` protocol as live trading
- Simulates fills with realistic slippage model (walk the book based on order size vs. depth)
- Simulates latency (configurable delay between signal and fill)
- Tracks all the same metrics as live: fill rate, slippage, P&L
- Can replay historical data through the same pipeline

### 11. Polymarket Executor (`execution/polymarket_executor.py`)

Wraps `py-clob-client`:
- Initialize with L1 auth → derive L2 API credentials
- Support signature types: EOA (0), Magic/email (1), Browser proxy (2)
- Order creation: limit (GTC) and market (FOK) orders
- Order cancellation
- Batch order support (up to 15 orders per batch)
- Heartbeat to keep connection alive (prevents open order auto-cancellation)
- Check `accepting_orders` and `tick_size` before submission
- Retry logic for transient failures (not for rejections)
- NEVER retry on insufficient balance or invalid price

### 12. Observability (`observability/`)

Prometheus metrics (expose on `:9090/metrics`):
- `ws_messages_total{exchange}` — counter
- `ws_reconnects_total{exchange}` — counter
- `ws_last_message_seconds{exchange}` — gauge
- `price_spread_ratio{exchange}` — histogram
- `signal_latency_seconds` — histogram (time from tick to signal)
- `order_latency_seconds` — histogram (time from signal to order sent)
- `fill_latency_seconds` — histogram (time from order sent to fill)
- `position_size{market}` — gauge
- `unrealized_pnl{market}` — gauge
- `daily_pnl` — gauge
- `drawdown_pct` — gauge

Decision audit log (every order decision, append-only):
```json
{
  "timestamp_ns": 1711800000000000000,
  "event": "ORDER_DECISION",
  "signal": {"direction": "BUY", "strength": 0.62, "probability": 0.58},
  "sizing": {"raw_kelly": 0.16, "half_kelly": 0.08, "final_size": 50.0},
  "risk_check": {"passed": true, "max_position": 500, "current_exposure": 200},
  "order": {"market_id": "...", "side": "BUY", "price": 0.58, "size": 50.0},
  "context": {"btc_price": 67842.50, "spread": 0.02, "book_depth": 1200}
}
```

### 13. Docker Compose (`docker-compose.yml`)

Local development stack:
- TimescaleDB (PostgreSQL 16 + TimescaleDB extension)
- Redis 7
- Prometheus (scrape the app metrics endpoint)
- Grafana (pre-configured dashboards for trading metrics)

### 14. Configuration (`config/settings.py`)

Pydantic `BaseSettings` — everything from environment variables, nothing hardcoded:

```python
# Groups:
# - ExchangeConfig: WS URLs, API keys per exchange
# - PolymarketConfig: CLOB endpoint, chain_id (137), private key ref, signature type, funder address
# - DatabaseConfig: TimescaleDB connection string, pool size
# - RedisConfig: host, port, db number
# - StrategyConfig: kelly_fraction, max_position_pct, max_drawdown_pct, min_trade_interval_seconds
# - RiskConfig: circuit breaker thresholds, kill switch enabled
# - ExecutionConfig: paper_trading_mode (bool, default True), slippage_model, retry settings
```

---

## Implementation Constraints

1. **Python 3.12+**. Use `asyncio` throughout — this is an async-first system.
2. **Type hints everywhere**. Use `Protocol` for interfaces, not ABC where possible.
3. **No float for money**. `decimal.Decimal` or `int` cents/satoshis.
4. **Structured logging only** — `structlog` with JSON output. Every log line must include a correlation ID.
5. **Every external call has a timeout**. No unbounded waits.
6. **Paper trading mode is the default**. Live trading requires explicit configuration AND a confirmation flag.
7. **Secrets via environment variables only**. The `.env.example` has placeholder keys. The actual `.env` is in `.gitignore`.
8. **Tests for every module**. Use `pytest-asyncio` for async tests. Mock external services.

---

## What NOT To Build Yet

- No ML models — the alpha model has a clean interface but the initial implementation is a stub that returns neutral signals. The infrastructure must work before the models matter.
- No Rust execution layer — design the `Executor` protocol so it can be swapped, but Python only for now.
- No cross-platform arbitrage (Kalshi, etc.) — but the data normalizer's `DataFeed` protocol should make adding new sources trivial.
- No frontend dashboard — the Grafana dashboards are the UI for now.
- No on-chain data ingestion — block times make it useless for 15-minute windows. Exchange WebSocket feeds are the right layer.

---

## Build Order

Execute in this sequence. Each phase should be independently testable before moving on.

**Phase 1: Foundation**
1. Project setup: `pyproject.toml`, directory structure, `.env.example`, `Makefile`
2. `core/types.py`, `core/events.py`, `core/clock.py`, `core/exceptions.py`
3. `config/settings.py` with Pydantic Settings
4. `docker-compose.yml` with TimescaleDB + Redis
5. `scripts/db_migrate.py` — run and verify schema

**Phase 2: Data Layer**
6. `data/websocket_manager.py` — the reconnecting WS base class
7. `data/feeds/coinbase.py` — first real feed, prove the pattern works
8. `data/feeds/binance.py`, `data/feeds/kraken.py` — replicate pattern
9. `data/normalizer.py` — cross-exchange price validation
10. `data/store.py` — async batch writes to TimescaleDB
11. `data/cache.py` — Redis pub/sub integration
12. `data/feeds/polymarket.py` — market data + REST client
13. `scripts/run_data_collector.py` — end-to-end: feeds → normalize → store → cache

**Phase 3: Strategy Skeleton**
14. `features/base.py`, `features/registry.py`, `features/price_features.py`
15. `strategy/base.py`, `strategy/alpha_model.py` (stub)
16. `strategy/sizing.py` — Kelly with fractional sizing
17. `strategy/risk_manager.py` — hard limits and circuit breakers
18. `strategy/arbitrage/intra_market.py` — YES+NO deviation monitoring

**Phase 4: Execution**
19. `execution/base.py` — Executor protocol
20. `execution/paper_trader.py` — simulated fills
21. `execution/order_manager.py` — order lifecycle state machine
22. `execution/polymarket_executor.py` — py-clob-client wrapper
23. `execution/fill_tracker.py` — execution quality analytics
24. `portfolio/position_manager.py`, `portfolio/pnl_engine.py`
25. `scripts/run_paper_trader.py` — full pipeline in paper mode

**Phase 5: Observability**
26. `observability/metrics.py` — Prometheus exposition
27. `observability/decision_log.py` — structured audit trail
28. `observability/alerts.py` — alert rule definitions
29. `observability/health.py` — health check endpoint
30. Grafana dashboard provisioning (JSON model for docker-compose)

**Phase 6: Backtest**
31. `backtest/engine.py` — event-driven replay using same interfaces
32. `backtest/data_loader.py` — TimescaleDB historical data reader
33. `backtest/report.py` — equity curves, drawdown analysis, trade log export

---

## Key Design Principles

1. **The event bus is sacred.** Components don't import each other. They publish and subscribe to typed events. This is what makes the system testable, backtestable, and eventually portable to Rust on the execution side.

2. **Every decision is logged.** When something goes wrong at 3 AM, you need to reconstruct exactly what the system saw, what it decided, and why. The decision audit log is not optional.

3. **Paper trading uses the same code path as live.** The only difference is which `Executor` implementation is injected. If paper trading works, live trading works. If they diverge, you have a bug.

4. **Fail loud, fail safe.** Unknown errors halt trading. Known errors (WS disconnect, transient API failure) are retried with backoff. The system should never silently continue in a degraded state.

5. **The data layer is the foundation.** You can't build models on bad data. Cross-exchange validation, staleness detection, and outlier rejection are not nice-to-haves — they're requirements before any signal generation happens.
