"""Pydantic Settings — all configuration from environment variables.

Nothing is hardcoded. Every value comes from env vars or has a safe default.
Paper trading mode is True by default — live trading requires explicit opt-in.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    url: str = "postgresql://trader:trader@localhost:5432/trading"
    pool_size: int = 10


class RedisConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="REDIS_")

    host: str = "localhost"
    port: int = 6379
    db: int = 0

    @property
    def dsn(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


class CoinbaseConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COINBASE_")

    ws_url: str = "wss://ws-feed.exchange.coinbase.com"
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""


class BinanceConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BINANCE_")

    ws_url: str = "wss://stream.binance.com:9443/ws"
    api_key: str = ""
    api_secret: str = ""


class KrakenConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="KRAKEN_")

    ws_url: str = "wss://ws.kraken.com"
    api_key: str = ""
    api_secret: str = ""


class PolymarketConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="POLYMARKET_")

    clob_url: str = "https://clob.polymarket.com"
    chain_id: int = 137
    private_key: str = ""
    signature_type: int = 0  # 0=EOA, 1=Magic, 2=Browser proxy
    funder_address: str = ""
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""


class StrategyConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    kelly_fraction: Decimal = Decimal("0.5")
    max_position_pct: Decimal = Decimal("0.10")
    max_drawdown_pct: Decimal = Decimal("0.10")
    min_trade_interval_seconds: int = 60


class RiskConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    kill_switch_enabled: bool = True
    max_daily_loss: Decimal = Decimal("1000.0")


class ExecutionConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="")

    paper_trading_mode: bool = True  # SAFE DEFAULT: always paper trade unless explicit
    slippage_bps: int = 10
    max_retries: int = 3


class LoggingConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOG_")

    level: str = "INFO"
    format: str = "json"  # 'json' or 'console'


class Settings(BaseSettings):
    """Root configuration — aggregates all subsystem configs."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    coinbase: CoinbaseConfig = Field(default_factory=CoinbaseConfig)
    binance: BinanceConfig = Field(default_factory=BinanceConfig)
    kraken: KrakenConfig = Field(default_factory=KrakenConfig)
    polymarket: PolymarketConfig = Field(default_factory=PolymarketConfig)
    strategy: StrategyConfig = Field(default_factory=StrategyConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
