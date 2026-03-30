"""initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ──────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.String(20),
            sa.CheckConstraint("role IN ('super_admin','admin','analyst','viewer')"),
            nullable=False,
        ),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("capital", sa.Float, server_default="200000"),
        sa.Column(
            "trade_mode",
            sa.String(10),
            sa.CheckConstraint("trade_mode IN ('auto','manual')"),
            server_default="auto",
        ),
        sa.Column("telegram_chat_id", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("failed_login_attempts", sa.Integer, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── sessions ───────────────────────────────────────────
    op.create_table(
        "sessions",
        sa.Column("token", sa.Text, primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── user_audit_log ─────────────────────────────────────
    op.create_table(
        "user_audit_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("target_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── daily_market_snapshots ─────────────────────────────
    op.create_table(
        "daily_market_snapshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column(
            "time_of_day",
            sa.String(10),
            sa.CheckConstraint("time_of_day IN ('open','mid','close')"),
            nullable=False,
        ),
        sa.Column("nifty_open", sa.Float, nullable=True),
        sa.Column("nifty_high", sa.Float, nullable=True),
        sa.Column("nifty_low", sa.Float, nullable=True),
        sa.Column("nifty_close", sa.Float, nullable=True),
        sa.Column("nifty_volume", sa.BigInteger, nullable=True),
        sa.Column("banknifty_close", sa.Float, nullable=True),
        sa.Column("sp500_close", sa.Float, nullable=True),
        sa.Column("nasdaq_close", sa.Float, nullable=True),
        sa.Column("nikkei_close", sa.Float, nullable=True),
        sa.Column("hangseng_close", sa.Float, nullable=True),
        sa.Column("shanghai_close", sa.Float, nullable=True),
        sa.Column("ftse_close", sa.Float, nullable=True),
        sa.Column("dax_close", sa.Float, nullable=True),
        sa.Column("gift_nifty", sa.Float, nullable=True),
        sa.Column("crude_brent", sa.Float, nullable=True),
        sa.Column("crude_wti", sa.Float, nullable=True),
        sa.Column("gold", sa.Float, nullable=True),
        sa.Column("silver", sa.Float, nullable=True),
        sa.Column("natural_gas", sa.Float, nullable=True),
        sa.Column("copper", sa.Float, nullable=True),
        sa.Column("usd_inr", sa.Float, nullable=True),
        sa.Column("dxy", sa.Float, nullable=True),
        sa.Column("usd_jpy", sa.Float, nullable=True),
        sa.Column("us_10y_yield", sa.Float, nullable=True),
        sa.Column("india_10y_yield", sa.Float, nullable=True),
        sa.Column("india_vix", sa.Float, nullable=True),
        sa.Column("us_vix", sa.Float, nullable=True),
        sa.Column("fii_net", sa.Float, nullable=True),
        sa.Column("dii_net", sa.Float, nullable=True),
        sa.Column("nifty_pe", sa.Float, nullable=True),
        sa.Column("nifty_pb", sa.Float, nullable=True),
        sa.Column("nifty_dividend_yield", sa.Float, nullable=True),
        sa.Column("advance_decline_ratio", sa.Float, nullable=True),
        sa.Column("put_call_ratio", sa.Float, nullable=True),
        sa.Column("nifty_vs_200dma", sa.Float, nullable=True),
        sa.Column("vwap", sa.Float, nullable=True),
        sa.Column("fresh_signals_count", sa.Integer, nullable=True),
        sa.Column("all_data", postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("date", "time_of_day"),
    )

    # ── predictions ────────────────────────────────────────
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("time_of_day", sa.String(10), nullable=False),
        sa.Column(
            "direction",
            sa.String(5),
            sa.CheckConstraint("direction IN ('UP','DOWN','FLAT')"),
            nullable=False,
        ),
        sa.Column("magnitude_low", sa.Float, nullable=True),
        sa.Column("magnitude_high", sa.Float, nullable=True),
        sa.Column(
            "confidence",
            sa.Integer,
            sa.CheckConstraint("confidence BETWEEN 0 AND 100"),
            nullable=True,
        ),
        sa.Column("confidence_reason", sa.Text, nullable=True),
        sa.Column("bull_case", sa.Text, nullable=True),
        sa.Column("bear_case", sa.Text, nullable=True),
        sa.Column("key_trigger", sa.Text, nullable=True),
        sa.Column(
            "data_quality",
            sa.String(10),
            sa.CheckConstraint("data_quality IN ('HIGH','MEDIUM','LOW')"),
            nullable=True,
        ),
        sa.Column("similar_days_found", sa.Integer, nullable=True),
        sa.Column("prediction_basis", postgresql.JSONB, nullable=True),
        sa.Column("market_conditions_at_time", postgresql.JSONB, nullable=True),
        sa.Column("actual_direction", sa.String(5), nullable=True),
        sa.Column("actual_magnitude", sa.Float, nullable=True),
        sa.Column("was_correct", sa.Boolean, nullable=True),
        sa.Column("error_size", sa.Float, nullable=True),
        sa.Column("miss_category", sa.Text, nullable=True),
        sa.Column("post_mortem", sa.Text, nullable=True),
        sa.Column("telegram_sent", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("date", "time_of_day"),
    )

    # ── signals ────────────────────────────────────────────
    op.create_table(
        "signals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "signal_type",
            sa.String(10),
            sa.CheckConstraint("signal_type IN ('BUY_CALL','BUY_PUT')"),
            nullable=False,
        ),
        sa.Column("underlying", sa.String(20), server_default="NIFTY50"),
        sa.Column("expiry", sa.Date, nullable=False),
        sa.Column("strike", sa.Integer, nullable=False),
        sa.Column(
            "option_type",
            sa.String(2),
            sa.CheckConstraint("option_type IN ('CE','PE')"),
            nullable=False,
        ),
        sa.Column("ltp_at_signal", sa.Float, nullable=False),
        sa.Column("target1", sa.Float, nullable=False),
        sa.Column("target2", sa.Float, nullable=False),
        sa.Column("stop_loss", sa.Float, nullable=False),
        sa.Column("exit_condition", sa.Text, nullable=True),
        sa.Column("rr_ratio", sa.Float, nullable=False),
        sa.Column("confidence", sa.Integer, nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("signal_basis", postgresql.JSONB, nullable=False),
        sa.Column("market_conditions", postgresql.JSONB, nullable=False),
        sa.Column("gates_passed", postgresql.JSONB, nullable=True),
        sa.Column(
            "status",
            sa.String(12),
            sa.CheckConstraint(
                "status IN ('OPEN','HIT_T1','HIT_T2','HIT_SL','EXPIRED','CANCELLED')"
            ),
            server_default="OPEN",
        ),
        sa.Column("outcome_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("outcome_premium", sa.Float, nullable=True),
        sa.Column("blocked_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── trades ─────────────────────────────────────────────
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id"), nullable=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column(
            "trade_mode",
            sa.String(10),
            sa.CheckConstraint("trade_mode IN ('auto','manual')"),
            nullable=False,
        ),
        sa.Column("capital_at_entry", sa.Float, nullable=False),
        sa.Column("lots", sa.Integer, nullable=False),
        sa.Column("entry_premium", sa.Float, nullable=False),
        sa.Column("entry_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entry_nifty_level", sa.Float, nullable=True),
        sa.Column("manual_entry_deviation_pct", sa.Float, nullable=True),
        sa.Column("rr_at_entry", sa.Float, nullable=False),
        sa.Column("rr_warning_acknowledged", sa.Boolean, server_default="false"),
        sa.Column("premium_total", sa.Float, nullable=False),
        sa.Column("max_loss_calculated", sa.Float, nullable=False),
        sa.Column("max_loss_pct", sa.Float, nullable=False),
        sa.Column("target1_profit_calculated", sa.Float, nullable=False),
        sa.Column("target2_profit_calculated", sa.Float, nullable=False),
        sa.Column("partial_t1_lots", sa.Integer, nullable=True),
        sa.Column("partial_t2_lots", sa.Integer, nullable=True),
        sa.Column("t1_exit_done", sa.Boolean, server_default="false"),
        sa.Column("t1_exit_premium", sa.Float, nullable=True),
        sa.Column("t1_exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("t1_exit_profit", sa.Float, nullable=True),
        sa.Column("trailing_sl_after_t1", sa.Float, nullable=True),
        sa.Column("exit_premium", sa.Float, nullable=True),
        sa.Column("exit_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_nifty_level", sa.Float, nullable=True),
        sa.Column(
            "exit_reason",
            sa.String(10),
            sa.CheckConstraint(
                "exit_reason IN ('TARGET1','TARGET2','STOP_LOSS','MANUAL','EXPIRED','PARTIAL')"
            ),
            nullable=True,
        ),
        sa.Column("gross_pnl", sa.Float, nullable=True),
        sa.Column("charges", sa.Float, nullable=True),
        sa.Column("net_pnl", sa.Float, nullable=True),
        sa.Column("net_pnl_pct", sa.Float, nullable=True),
        sa.Column(
            "status",
            sa.String(8),
            sa.CheckConstraint("status IN ('OPEN','CLOSED','PARTIAL')"),
            server_default="OPEN",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── trade_learnings ────────────────────────────────────
    op.create_table(
        "trade_learnings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("trade_id", sa.Integer, sa.ForeignKey("trades.id"), nullable=True),
        sa.Column("signal_id", sa.Integer, sa.ForeignKey("signals.id"), nullable=True),
        sa.Column("trade_date", sa.Date, nullable=False),
        sa.Column("loss_amount", sa.Float, nullable=False),
        sa.Column("loss_pct", sa.Float, nullable=False),
        sa.Column("miss_category", sa.Text, nullable=False),
        sa.Column("what_signal_said", sa.Text, nullable=True),
        sa.Column("what_actually_happened", sa.Text, nullable=True),
        sa.Column("root_cause", sa.Text, nullable=True),
        sa.Column("signal_conditions_at_time", postgresql.JSONB, nullable=True),
        sa.Column("news_between_entry_exit", sa.Text, nullable=True),
        sa.Column("sl_was_correct", sa.Boolean, nullable=True),
        sa.Column(
            "sl_recommendation",
            sa.String(10),
            sa.CheckConstraint("sl_recommendation IN ('TIGHTER','WIDER','SAME')"),
            nullable=True,
        ),
        sa.Column("signal_adjustment", sa.Text, nullable=True),
        sa.Column("rule_change_proposed", sa.Text, nullable=True),
        sa.Column("rule_change_applied", sa.Boolean, server_default="false"),
        sa.Column("rule_change_date", sa.Date, nullable=True),
        sa.Column("improvement_result", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── signal_rules ───────────────────────────────────────
    op.create_table(
        "signal_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rule_name", sa.String(100), unique=True, nullable=False),
        sa.Column("rule_value", postgresql.JSONB, nullable=False),
        sa.Column("previous_value", postgresql.JSONB, nullable=True),
        sa.Column(
            "changed_by",
            sa.String(10),
            sa.CheckConstraint("changed_by IN ('AI','ADMIN','SYSTEM')"),
            nullable=True,
        ),
        sa.Column("change_reason", sa.Text, nullable=True),
        sa.Column("trades_since_change", sa.Integer, server_default="0"),
        sa.Column("win_rate_before", sa.Float, nullable=True),
        sa.Column("win_rate_after", sa.Float, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── signal_performance ─────────────────────────────────
    op.create_table(
        "signal_performance",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("signal_type", sa.String(10), nullable=False),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("total_signals", sa.Integer, server_default="0"),
        sa.Column("winning_signals", sa.Integer, server_default="0"),
        sa.Column("losing_signals", sa.Integer, server_default="0"),
        sa.Column("win_rate", sa.Float, nullable=True),
        sa.Column("avg_win_pct", sa.Float, nullable=True),
        sa.Column("avg_loss_pct", sa.Float, nullable=True),
        sa.Column("expectancy", sa.Float, nullable=True),
        sa.Column("best_conditions", postgresql.JSONB, nullable=True),
        sa.Column("worst_conditions", postgresql.JSONB, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── errors ─────────────────────────────────────────────
    op.create_table(
        "errors",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("service", sa.String(50), nullable=False),
        sa.Column("error_type", sa.String(100), nullable=False),
        sa.Column(
            "severity",
            sa.Integer,
            sa.CheckConstraint("severity BETWEEN 1 AND 4"),
            nullable=False,
        ),
        sa.Column("traceback", sa.Text, nullable=True),
        sa.Column("log_context", sa.Text, nullable=True),
        sa.Column("system_state", postgresql.JSONB, nullable=True),
        sa.Column("fix_attempted", sa.Boolean, server_default="false"),
        sa.Column(
            "fix_source",
            sa.String(20),
            sa.CheckConstraint(
                "fix_source IN ('AUTO_RESTART','CLAUDE','HUMAN','SIMILAR_PAST')"
            ),
            nullable=True,
        ),
        sa.Column("fix_code", sa.Text, nullable=True),
        sa.Column("fix_explanation", sa.Text, nullable=True),
        sa.Column("fix_test_cases", sa.Text, nullable=True),
        sa.Column("fix_test_results", sa.Text, nullable=True),
        sa.Column("fix_worked", sa.Boolean, nullable=True),
        sa.Column("fix_timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fix_approved_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("similar_error_ids", postgresql.ARRAY(sa.Integer), nullable=True),
        sa.Column("root_cause", sa.Text, nullable=True),
        sa.Column("prevention_note", sa.Text, nullable=True),
        sa.Column("git_commit_hash", sa.String(50), nullable=True),
    )

    # ── system_health_log ──────────────────────────────────
    op.create_table(
        "system_health_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("service", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.String(10),
            sa.CheckConstraint("status IN ('OK','WARNING','ERROR','CRASHED')"),
            nullable=False,
        ),
        sa.Column("response_time_ms", sa.Integer, nullable=True),
        sa.Column("memory_mb", sa.Float, nullable=True),
        sa.Column("cpu_pct", sa.Float, nullable=True),
        sa.Column("details", postgresql.JSONB, nullable=True),
    )

    # ── prediction_mistakes ────────────────────────────────
    op.create_table(
        "prediction_mistakes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "prediction_id", sa.Integer, sa.ForeignKey("predictions.id"), nullable=True
        ),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("prediction_direction", sa.String(5), nullable=False),
        sa.Column("actual_direction", sa.String(5), nullable=False),
        sa.Column("error_size", sa.Float, nullable=False),
        sa.Column("market_conditions", postgresql.JSONB, nullable=False),
        sa.Column("miss_category", sa.Text, nullable=False),
        sa.Column("what_was_missed", sa.Text, nullable=True),
        sa.Column("lesson_extracted", sa.Text, nullable=True),
        sa.Column("similar_past_miss_ids", postgresql.ARRAY(sa.Integer), nullable=True),
        sa.Column("confidence_given", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── indexes ────────────────────────────────────────────
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.create_index("ix_daily_market_snapshots_date", "daily_market_snapshots", ["date"])
    op.create_index("ix_predictions_date", "predictions", ["date"])
    op.create_index("ix_signals_timestamp", "signals", ["timestamp"])
    op.create_index("ix_signals_status", "signals", ["status"])
    op.create_index("ix_trades_user_id", "trades", ["user_id"])
    op.create_index("ix_trades_status", "trades", ["status"])
    op.create_index("ix_trades_entry_time", "trades", ["entry_time"])
    op.create_index("ix_errors_service", "errors", ["service"])
    op.create_index("ix_errors_severity", "errors", ["severity"])
    op.create_index("ix_system_health_log_service", "system_health_log", ["service"])
    op.create_index("ix_system_health_log_timestamp", "system_health_log", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_system_health_log_timestamp", "system_health_log")
    op.drop_index("ix_system_health_log_service", "system_health_log")
    op.drop_index("ix_errors_severity", "errors")
    op.drop_index("ix_errors_service", "errors")
    op.drop_index("ix_trades_entry_time", "trades")
    op.drop_index("ix_trades_status", "trades")
    op.drop_index("ix_trades_user_id", "trades")
    op.drop_index("ix_signals_status", "signals")
    op.drop_index("ix_signals_timestamp", "signals")
    op.drop_index("ix_predictions_date", "predictions")
    op.drop_index("ix_daily_market_snapshots_date", "daily_market_snapshots")
    op.drop_index("ix_sessions_expires_at", "sessions")
    op.drop_index("ix_sessions_user_id", "sessions")

    op.drop_table("prediction_mistakes")
    op.drop_table("system_health_log")
    op.drop_table("errors")
    op.drop_table("signal_performance")
    op.drop_table("signal_rules")
    op.drop_table("trade_learnings")
    op.drop_table("trades")
    op.drop_table("signals")
    op.drop_table("predictions")
    op.drop_table("daily_market_snapshots")
    op.drop_table("user_audit_log")
    op.drop_table("sessions")
    op.drop_table("users")
