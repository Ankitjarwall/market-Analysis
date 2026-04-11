"""
All SQLAlchemy ORM models 窶・single source of truth for the database schema.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.connection import Base


# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武
#  AUTH
# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint("role IN ('super_admin','admin','analyst','viewer')"),
        nullable=False,
    )
    added_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    capital: Mapped[float] = mapped_column(Float, default=200_000)
    trade_mode: Mapped[str] = mapped_column(
        String(10),
        CheckConstraint("trade_mode IN ('auto','manual')"),
        default="auto",
    )
    auto_settings: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    sessions: Mapped[list["Session"]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan"
    )
    trades: Mapped[list["Trade"]] = relationship("Trade", back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    token: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped[User] = relationship("User", back_populates="sessions")


class UserAuditLog(Base):
    __tablename__ = "user_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武
#  MARKET DATA
# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武


class DailyMarketSnapshot(Base):
    __tablename__ = "daily_market_snapshots"
    __table_args__ = (UniqueConstraint("date", "time_of_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    time_of_day: Mapped[str] = mapped_column(
        String(10),
        CheckConstraint("time_of_day IN ('open','mid','close')"),
        nullable=False,
    )
    # Nifty
    nifty_open: Mapped[float | None] = mapped_column(Float)
    nifty_high: Mapped[float | None] = mapped_column(Float)
    nifty_low: Mapped[float | None] = mapped_column(Float)
    nifty_close: Mapped[float | None] = mapped_column(Float)
    nifty_volume: Mapped[int | None] = mapped_column(BigInteger)
    banknifty_close: Mapped[float | None] = mapped_column(Float)
    # Global indices
    sp500_close: Mapped[float | None] = mapped_column(Float)
    nasdaq_close: Mapped[float | None] = mapped_column(Float)
    nikkei_close: Mapped[float | None] = mapped_column(Float)
    hangseng_close: Mapped[float | None] = mapped_column(Float)
    shanghai_close: Mapped[float | None] = mapped_column(Float)
    ftse_close: Mapped[float | None] = mapped_column(Float)
    dax_close: Mapped[float | None] = mapped_column(Float)
    gift_nifty: Mapped[float | None] = mapped_column(Float)
    # Commodities
    crude_brent: Mapped[float | None] = mapped_column(Float)
    crude_wti: Mapped[float | None] = mapped_column(Float)
    gold: Mapped[float | None] = mapped_column(Float)
    silver: Mapped[float | None] = mapped_column(Float)
    natural_gas: Mapped[float | None] = mapped_column(Float)
    copper: Mapped[float | None] = mapped_column(Float)
    # Currencies
    usd_inr: Mapped[float | None] = mapped_column(Float)
    dxy: Mapped[float | None] = mapped_column(Float)
    usd_jpy: Mapped[float | None] = mapped_column(Float)
    # Bonds
    us_10y_yield: Mapped[float | None] = mapped_column(Float)
    india_10y_yield: Mapped[float | None] = mapped_column(Float)
    # India specific
    india_vix: Mapped[float | None] = mapped_column(Float)
    us_vix: Mapped[float | None] = mapped_column(Float)
    fii_net: Mapped[float | None] = mapped_column(Float)
    dii_net: Mapped[float | None] = mapped_column(Float)
    nifty_pe: Mapped[float | None] = mapped_column(Float)
    nifty_pb: Mapped[float | None] = mapped_column(Float)
    nifty_dividend_yield: Mapped[float | None] = mapped_column(Float)
    advance_decline_ratio: Mapped[float | None] = mapped_column(Float)
    put_call_ratio: Mapped[float | None] = mapped_column(Float)
    nifty_vs_200dma: Mapped[float | None] = mapped_column(Float)
    vwap: Mapped[float | None] = mapped_column(Float)
    fresh_signals_count: Mapped[int | None] = mapped_column(Integer)
    all_data: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武
#  PREDICTIONS
# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("date", "time_of_day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    time_of_day: Mapped[str] = mapped_column(String(10), nullable=False)
    direction: Mapped[str] = mapped_column(
        String(5),
        CheckConstraint("direction IN ('UP','DOWN','FLAT')"),
        nullable=False,
    )
    magnitude_low: Mapped[float | None] = mapped_column(Float)
    magnitude_high: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[int | None] = mapped_column(
        Integer, CheckConstraint("confidence BETWEEN 0 AND 100")
    )
    confidence_reason: Mapped[str | None] = mapped_column(Text)
    bull_case: Mapped[str | None] = mapped_column(Text)
    bear_case: Mapped[str | None] = mapped_column(Text)
    key_trigger: Mapped[str | None] = mapped_column(Text)
    data_quality: Mapped[str | None] = mapped_column(
        String(10), CheckConstraint("data_quality IN ('HIGH','MEDIUM','LOW')")
    )
    similar_days_found: Mapped[int | None] = mapped_column(Integer)
    prediction_basis: Mapped[dict | None] = mapped_column(JSONB)
    market_conditions_at_time: Mapped[dict | None] = mapped_column(JSONB)
    # Post-market fill
    actual_direction: Mapped[str | None] = mapped_column(String(5))
    actual_magnitude: Mapped[float | None] = mapped_column(Float)
    was_correct: Mapped[bool | None] = mapped_column(Boolean)
    error_size: Mapped[float | None] = mapped_column(Float)
    miss_category: Mapped[str | None] = mapped_column(Text)
    post_mortem: Mapped[str | None] = mapped_column(Text)
    telegram_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    mistakes: Mapped[list["PredictionMistake"]] = relationship(
        "PredictionMistake", back_populates="prediction"
    )


# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武
#  OPTIONS SIGNALS
# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signal_type: Mapped[str] = mapped_column(
        String(10),
        CheckConstraint("signal_type IN ('BUY_CALL','BUY_PUT')"),
        nullable=False,
    )
    underlying: Mapped[str] = mapped_column(String(20), default="NIFTY50")
    expiry: Mapped[date] = mapped_column(Date, nullable=False)
    strike: Mapped[int] = mapped_column(Integer, nullable=False)
    option_type: Mapped[str] = mapped_column(
        String(2), CheckConstraint("option_type IN ('CE','PE')"), nullable=False
    )
    ltp_at_signal: Mapped[float] = mapped_column(Float, nullable=False)
    target1: Mapped[float] = mapped_column(Float, nullable=False)
    target2: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float] = mapped_column(Float, nullable=False)
    exit_condition: Mapped[str | None] = mapped_column(Text)
    rr_ratio: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    signal_basis: Mapped[dict] = mapped_column(JSONB, nullable=False)
    market_conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    gates_passed: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(
        String(12),
        CheckConstraint(
            "status IN ('OPEN','HIT_T1','HIT_T2','HIT_SL','EXPIRED','CANCELLED')"
        ),
        default="OPEN",
    )
    outcome_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    outcome_premium: Mapped[float | None] = mapped_column(Float)
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    trades: Mapped[list["Trade"]] = relationship("Trade", back_populates="signal")


# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武
#  TRADES
# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("signals.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    trade_mode: Mapped[str] = mapped_column(
        String(10),
        CheckConstraint("trade_mode IN ('auto','manual')"),
        nullable=False,
    )
    # Entry
    capital_at_entry: Mapped[float] = mapped_column(Float, nullable=False)
    lots: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_premium: Mapped[float] = mapped_column(Float, nullable=False)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    entry_nifty_level: Mapped[float | None] = mapped_column(Float)
    manual_entry_deviation_pct: Mapped[float | None] = mapped_column(Float)
    rr_at_entry: Mapped[float] = mapped_column(Float, nullable=False)
    rr_warning_acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    # Position sizing
    premium_total: Mapped[float] = mapped_column(Float, nullable=False)
    max_loss_calculated: Mapped[float] = mapped_column(Float, nullable=False)
    max_loss_pct: Mapped[float] = mapped_column(Float, nullable=False)
    target1_profit_calculated: Mapped[float] = mapped_column(Float, nullable=False)
    target2_profit_calculated: Mapped[float] = mapped_column(Float, nullable=False)
    # Partial exit plan
    partial_t1_lots: Mapped[int | None] = mapped_column(Integer)
    partial_t2_lots: Mapped[int | None] = mapped_column(Integer)
    t1_exit_done: Mapped[bool] = mapped_column(Boolean, default=False)
    t1_exit_premium: Mapped[float | None] = mapped_column(Float)
    t1_exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    t1_exit_profit: Mapped[float | None] = mapped_column(Float)
    trailing_sl_after_t1: Mapped[float | None] = mapped_column(Float)
    # Final exit
    exit_premium: Mapped[float | None] = mapped_column(Float)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    exit_nifty_level: Mapped[float | None] = mapped_column(Float)
    exit_reason: Mapped[str | None] = mapped_column(
        String(10),
        CheckConstraint(
            "exit_reason IN ('TARGET1','TARGET2','STOP_LOSS','MANUAL','EXPIRED','PARTIAL')"
        ),
    )
    # P&L
    gross_pnl: Mapped[float | None] = mapped_column(Float)
    charges: Mapped[float | None] = mapped_column(Float)
    net_pnl: Mapped[float | None] = mapped_column(Float)
    net_pnl_pct: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String(8),
        CheckConstraint("status IN ('OPEN','CLOSED','PARTIAL')"),
        default="OPEN",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    signal: Mapped[Signal | None] = relationship("Signal", back_populates="trades")
    user: Mapped[User] = relationship("User", back_populates="trades")
    learnings: Mapped[list["TradeLearning"]] = relationship(
        "TradeLearning", back_populates="trade"
    )


# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武
#  LEARNING ENGINE
# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武


class TradeLearning(Base):
    __tablename__ = "trade_learnings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trade_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("trades.id"))
    signal_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("signals.id"))
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    loss_amount: Mapped[float] = mapped_column(Float, nullable=False)
    loss_pct: Mapped[float] = mapped_column(Float, nullable=False)
    miss_category: Mapped[str] = mapped_column(Text, nullable=False)
    what_signal_said: Mapped[str | None] = mapped_column(Text)
    what_actually_happened: Mapped[str | None] = mapped_column(Text)
    root_cause: Mapped[str | None] = mapped_column(Text)
    signal_conditions_at_time: Mapped[dict | None] = mapped_column(JSONB)
    news_between_entry_exit: Mapped[str | None] = mapped_column(Text)
    sl_was_correct: Mapped[bool | None] = mapped_column(Boolean)
    sl_recommendation: Mapped[str | None] = mapped_column(
        String(10), CheckConstraint("sl_recommendation IN ('TIGHTER','WIDER','SAME')")
    )
    signal_adjustment: Mapped[str | None] = mapped_column(Text)
    rule_change_proposed: Mapped[str | None] = mapped_column(Text)
    rule_change_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    rule_change_date: Mapped[date | None] = mapped_column(Date)
    improvement_result: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    trade: Mapped[Trade | None] = relationship("Trade", back_populates="learnings")


class SignalRule(Base):
    __tablename__ = "signal_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    rule_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    previous_value: Mapped[dict | None] = mapped_column(JSONB)
    changed_by: Mapped[str | None] = mapped_column(
        String(10), CheckConstraint("changed_by IN ('AI','ADMIN','SYSTEM')")
    )
    change_reason: Mapped[str | None] = mapped_column(Text)
    trades_since_change: Mapped[int] = mapped_column(Integer, default=0)
    win_rate_before: Mapped[float | None] = mapped_column(Float)
    win_rate_after: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SignalPerformance(Base):
    __tablename__ = "signal_performance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_type: Mapped[str] = mapped_column(String(10), nullable=False)
    period: Mapped[str] = mapped_column(String(20), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_signals: Mapped[int] = mapped_column(Integer, default=0)
    winning_signals: Mapped[int] = mapped_column(Integer, default=0)
    losing_signals: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float | None] = mapped_column(Float)
    avg_win_pct: Mapped[float | None] = mapped_column(Float)
    avg_loss_pct: Mapped[float | None] = mapped_column(Float)
    expectancy: Mapped[float | None] = mapped_column(Float)
    best_conditions: Mapped[dict | None] = mapped_column(JSONB)
    worst_conditions: Mapped[dict | None] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武
#  SELF-HEALING
# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武


class Error(Base):
    __tablename__ = "errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    service: Mapped[str] = mapped_column(String(50), nullable=False)
    error_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[int] = mapped_column(
        Integer, CheckConstraint("severity BETWEEN 1 AND 4"), nullable=False
    )
    traceback: Mapped[str | None] = mapped_column(Text)
    log_context: Mapped[str | None] = mapped_column(Text)
    system_state: Mapped[dict | None] = mapped_column(JSONB)
    fix_attempted: Mapped[bool] = mapped_column(Boolean, default=False)
    fix_source: Mapped[str | None] = mapped_column(
        String(20),
        CheckConstraint("fix_source IN ('AUTO_RESTART','CLAUDE','HUMAN','SIMILAR_PAST')"),
    )
    fix_code: Mapped[str | None] = mapped_column(Text)
    fix_explanation: Mapped[str | None] = mapped_column(Text)
    fix_test_cases: Mapped[str | None] = mapped_column(Text)
    fix_test_results: Mapped[str | None] = mapped_column(Text)
    fix_worked: Mapped[bool | None] = mapped_column(Boolean)
    fix_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fix_approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    similar_error_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    root_cause: Mapped[str | None] = mapped_column(Text)
    prevention_note: Mapped[str | None] = mapped_column(Text)
    git_commit_hash: Mapped[str | None] = mapped_column(String(50))


class SystemHealthLog(Base):
    __tablename__ = "system_health_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    service: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(10),
        CheckConstraint("status IN ('OK','WARNING','ERROR','CRASHED')"),
        nullable=False,
    )
    response_time_ms: Mapped[int | None] = mapped_column(Integer)
    memory_mb: Mapped[float | None] = mapped_column(Float)
    cpu_pct: Mapped[float | None] = mapped_column(Float)
    details: Mapped[dict | None] = mapped_column(JSONB)


# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武
#  PREDICTION MISTAKES
# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武


class PredictionMistake(Base):
    __tablename__ = "prediction_mistakes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("predictions.id")
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    prediction_direction: Mapped[str] = mapped_column(String(5), nullable=False)
    actual_direction: Mapped[str] = mapped_column(String(5), nullable=False)
    error_size: Mapped[float] = mapped_column(Float, nullable=False)
    market_conditions: Mapped[dict] = mapped_column(JSONB, nullable=False)
    miss_category: Mapped[str] = mapped_column(Text, nullable=False)
    what_was_missed: Mapped[str | None] = mapped_column(Text)
    lesson_extracted: Mapped[str | None] = mapped_column(Text)
    similar_past_miss_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    confidence_given: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    prediction: Mapped[Prediction | None] = relationship(
        "Prediction", back_populates="mistakes"
    )


# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武
#  CLAUDE AI MEMORY 窶・persistent context for AI predictions
# 笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武笊絶武


class ClaudeMemory(Base):
    """
    Stores key facts, patterns and rules that Claude needs across sessions.
    Each entry is a named memory slot 窶・Claude reads these before each analysis
    so it has full context without relying on conversation history.
    """
    __tablename__ = "claude_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Category: "market_pattern" | "trade_rule" | "prediction_bias" | "seasonal" | "regime"
    category: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    # Source that created this memory
    source: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint("source IN ('learning_engine','manual','weekly_review','monthly_calibration')"),
        default="learning_engine",
    )
    confidence: Mapped[int] = mapped_column(
        Integer, CheckConstraint("confidence BETWEEN 0 AND 100"), default=70
    )
    # How many times this pattern has been validated
    validation_count: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)  # None = permanent
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MarketRegime(Base):
    """
    Tracks current market regime so Claude knows the macro context.
    Updated daily by the learning engine after EOD analysis.
    """
    __tablename__ = "market_regime"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    regime: Mapped[str] = mapped_column(
        String(20),
        CheckConstraint("regime IN ('BULL','BEAR','SIDEWAYS','HIGH_VOLATILITY','LOW_VOLATILITY')"),
        nullable=False,
    )
    vix_avg_5d: Mapped[float | None] = mapped_column(Float)
    nifty_trend_5d: Mapped[float | None] = mapped_column(Float)   # % change over 5 days
    fii_net_5d: Mapped[float | None] = mapped_column(Float)        # sum of FII net over 5 days
    put_call_ratio_avg: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
