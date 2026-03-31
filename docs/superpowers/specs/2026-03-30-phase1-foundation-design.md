# Phase 1: Foundation — Design Spec

## Context

Building the foundation layer for a Polymarket quantitative trading system. The system targets BTC 15-minute price direction prediction markets. This is a research-phase build in Python, architected so the execution layer can be ported to Rust later.

Phase 1 establishes the core domain types, event bus, configuration, infrastructure, and database schema that every subsequent phase depends on.

## Scope

Phase 1 covers steps 1-5 from the master spec:

1. Project setup (`pyproject.toml`, directory structure, `.env.example`, `Makefile`)
2. Core domain (`core/types.py`, `core/events.py`, `core/clock.py`, `core/exceptions.py`)
3. Configuration (`config/settings.py` with Pydantic Settings)
4. Docker Compose (TimescaleDB, Redis, Prometheus, Grafana)
5. Database migration (`scripts/db_migrate.py`)

## Architecture Decisions

### Protocol-First Interfaces

All layer boundaries use `typing.Protocol` for structural typing (not ABC). This enables:
- Duck-typed interfaces without inheritance coupling
- Easy mocking in tests
- Clear contracts for future Rust port boundaries

### Event Bus as Sole Communication Channel

Components communicate exclusively through typed events on an asyncio-based pub/sub bus. No direct imports between layers. This makes the system:
- Testable (inject mock events)
- Backtestable (replay events from history)
- Portable (swap implementations without rewiring)

### Decimal Prices, Nanosecond Timestamps

- All monetary values: `decimal.Decimal` (never float)
- All timestamps: `int` nanoseconds since Unix epoch
- These are enforced at the type level with `__post_init__` validation

## Component Design

### 1. Project Scaffold

```
polymarket-trading/
├── pyproject.toml          # uv project, Python 3.12+
├── .env.example            # Template with all required env vars
├── .gitignore              # Python + Docker + IDE ignores
├── Makefile                # dev, test, docker-up, docker-down, migrate, lint
├── docker-compose.yml      # TimescaleDB, Redis, Prometheus, Grafana
├── config/
│   ├── __init__.py
│   ├── settings.py         # Pydantic BaseSettings
│   ├── markets.py          # Market definitions, token IDs
│   └── logging.py          # structlog JSON config
├── core/
│   ├── __init__.py
│   ├── types.py            # Domain types (Tick, Order, Fill, etc.)
│   ├── events.py           # Event bus + typed events
│   ├── clock.py            # Real + simulated clock
│   └── exceptions.py       # Typed exception hierarchy
├── data/                   # Empty __init__.py (Phase 2)
├── features/               # Empty __init__.py (Phase 3)
├── strategy/               # Empty __init__.py (Phase 3)
├── execution/              # Empty __init__.py (Phase 4)
├── portfolio/              # Empty __init__.py (Phase 4)
├── observability/          # Empty __init__.py (Phase 5)
├── backtest/               # Empty __init__.py (Phase 6)
├── scripts/
│   └── db_migrate.py       # TimescaleDB schema setup
└── tests/
    ├── conftest.py         # Shared fixtures
    ├── test_types.py       # Domain type validation
    ├── test_event_bus.py   # Event pub/sub tests
    └── test_clock.py       # Clock abstraction tests
```

### 2. Core Types (`core/types.py`)

Dataclasses with `__slots__` for performance. Key types:

- **`Tick`** — Raw exchange data: `exchange`, `symbol`, `bid`, `ask`, `mid`, `bid_size`, `ask_size`, `timestamp_ns`
- **`NormalizedPrice`** — Cross-validated price: `symbol`, `price`, `source`, `confidence`, `timestamp_ns`
- **`Signal`** — Alpha output: `market_id`, `direction` (enum: LONG/SHORT/NEUTRAL), `strength`, `probability`, `features` (dict), `timestamp_ns`
- **`Order`** — Trade intent: `id` (UUID), `market_id`, `token_id`, `side` (BUY/SELL), `price`, `size`, `order_type` (LIMIT/MARKET), `status` (enum state machine), `created_at`
- **`Fill`** — Execution confirmation: `order_id`, `price`, `size`, `fee`, `timestamp_ns`
- **`Position`** — Current holdings: `market_id`, `token_id`, `side`, `size`, `avg_entry`, `unrealized_pnl`

Enums:
- **`Side`** — BUY, SELL
- **`Direction`** — LONG, SHORT, NEUTRAL
- **`OrderType`** — LIMIT, MARKET
- **`OrderStatus`** — PENDING, SENT, PARTIAL, FILLED, CANCELLED, REJECTED

### 3. Event Bus (`core/events.py`)

Async pub/sub using `asyncio.Queue`:

- **`Event`** base dataclass with `event_type`, `timestamp_ns`, `correlation_id` (UUID)
- Typed event subclasses: `TickEvent`, `PriceUpdateEvent`, `SignalEvent`, `OrderRequestEvent`, `OrderStatusEvent`, `FillEvent`, `AlertEvent`, `HeartbeatEvent`
- **`EventBus`** class:
  - `subscribe(event_type, handler)` — register async callback
  - `publish(event)` — dispatch to all subscribers of that event type
  - `start()` / `stop()` — lifecycle management
  - Internal: `asyncio.Queue` per event type, consumer tasks drain queues and invoke handlers
  - Error isolation: one handler failure doesn't crash others (logged + AlertEvent emitted)

### 4. Clock (`core/clock.py`)

Protocol-based clock abstraction:

- **`Clock` Protocol**: `now_ns() -> int`, `now_dt() -> datetime`
- **`RealClock`** — `time.time_ns()` for production
- **`SimulatedClock`** — manual `advance(ns)` / `set(ns)` for backtests
- All components receive a `Clock` instance via dependency injection

### 5. Exceptions (`core/exceptions.py`)

Typed hierarchy:

```
TradingError (base)
├── DataError
│   ├── FeedDisconnectedError
│   ├── StaleDataError
│   └── NormalizationError
├── StrategyError
│   ├── RiskLimitExceededError
│   └── SignalGenerationError
├── ExecutionError
│   ├── OrderRejectedError
│   ├── InsufficientBalanceError
│   └── GasError
└── ConfigError
```

### 6. Configuration (`config/settings.py`)

Pydantic `BaseSettings` groups, all from environment variables:

- **`ExchangeConfig`** — WS URLs per exchange, API keys
- **`PolymarketConfig`** — CLOB endpoint, chain_id (137), private key ref, signature type
- **`DatabaseConfig`** — TimescaleDB DSN, pool size
- **`RedisConfig`** — host, port, db number
- **`StrategyConfig`** — kelly_fraction (default 0.5), max_position_pct, max_drawdown_pct
- **`RiskConfig`** — circuit breaker thresholds, kill switch enabled
- **`ExecutionConfig`** — paper_trading_mode (default `True`), slippage model, retry config
- **`Settings`** — root config aggregating all sub-configs

Market definitions (`config/markets.py`): dataclass for market metadata (condition_id, token_ids for YES/NO, tick_size, min_order_size).

Structured logging (`config/logging.py`): structlog with JSON output, correlation ID processor.

### 7. Docker Compose

Services:
- **timescaledb**: `timescale/timescaledb:latest-pg16`, port 5432, persistent volume
- **redis**: `redis:7-alpine`, port 6379, persistent volume
- **prometheus**: `prom/prometheus:latest`, port 9090, mounted config
- **grafana**: `grafana/grafana:latest`, port 3000, auto-provisioned dashboards

### 8. Database Migration (`scripts/db_migrate.py`)

Async script using `asyncpg`:
- Creates hypertables: `ticks`, `prices`, `signals`, `pnl_snapshots`
- Creates regular tables: `orders`, `fills`
- Sets up compression policies on hypertables
- Idempotent (safe to re-run)

## Testing Strategy

- **`test_types.py`**: Verify Decimal enforcement, timestamp validation, enum correctness, serialization
- **`test_event_bus.py`**: Publish/subscribe, multi-handler, error isolation, ordering guarantees
- **`test_clock.py`**: RealClock monotonicity, SimulatedClock advance/set behavior
- **`conftest.py`**: Shared fixtures — fake clock, test event bus, test database connection

## Verification

1. `make docker-up` — TimescaleDB + Redis + Prometheus + Grafana start cleanly
2. `make migrate` — Schema created in TimescaleDB, verify with `\dt` in psql
3. `make test` — All tests pass
4. `make lint` — Clean ruff/mypy output
5. Import check: `python -c "from core.types import Tick, Order; from core.events import EventBus; print('OK')"`
