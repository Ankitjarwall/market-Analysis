"""
Application configuration — reads all settings from environment variables.
"""

from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ──
    database_url: str = "postgresql://market_user:market_pass@localhost/market_platform"
    redis_url: str = "redis://localhost:6379/0"

    # ── Auth ──
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # ── Anthropic ──
    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-4-6"

    # ── Telegram ──
    telegram_bot_token: str = ""
    telegram_chat_ids: str = ""  # comma-separated

    # ── News ──
    news_api_key: str = ""

    # ── App ──
    environment: str = "development"
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"

    # ── Trading Parameters ──
    default_capital: float = 200_000
    max_risk_pct: float = 2.0
    max_deploy_pct: float = 20.0
    min_rr_ratio: float = 2.0
    nifty_lot_size: int = 25
    banknifty_lot_size: int = 15
    min_fresh_signals: int = 40
    min_confidence: int = 55
    max_daily_signals: int = 2
    signal_cooldown_after_sl: int = 60  # minutes
    min_vix_for_put: float = 15.0
    min_fii_consecutive_days: int = 1

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def telegram_chat_id_list(self) -> list[int]:
        if not self.telegram_chat_ids:
            return []
        return [int(x.strip()) for x in self.telegram_chat_ids.split(",") if x.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
