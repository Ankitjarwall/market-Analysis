"""
Learning engine — analyzes losses, updates signal rules, and runs weekly/monthly reviews.
"""

import logging
from datetime import date, datetime, timedelta, timezone

logger = logging.getLogger(__name__)


async def process_losing_trade(trade_id: int):
    """Analyze a losing trade and propose rule adjustments."""
    from bot.analyzer import analyze_loss
    from db.connection import AsyncSessionLocal
    from db.models import Signal, SignalRule, Trade, TradeLearning
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        trade_result = await session.execute(select(Trade).where(Trade.id == trade_id))
        trade = trade_result.scalar_one_or_none()
        if not trade:
            return

        signal_result = await session.execute(
            select(Signal).where(Signal.id == trade.signal_id)
        )
        signal = signal_result.scalar_one_or_none()
        if not signal:
            return

        # Prepare context dicts
        trade_data = {
            "entry_premium": trade.entry_premium,
            "exit_premium": trade.exit_premium,
            "entry_time": str(trade.entry_time),
            "exit_time": str(trade.exit_time),
            "net_pnl": trade.net_pnl,
            "net_pnl_pct": trade.net_pnl_pct,
            "trade_mode": trade.trade_mode,
        }
        signal_data = {
            "signal_type": signal.signal_type,
            "strike": signal.strike,
            "stop_loss": signal.stop_loss,
            "target1": signal.target1,
        }

    try:
        analysis = await analyze_loss(
            trade_data, signal_data,
            conditions_at_entry=signal.market_conditions or {},
            conditions_at_exit={},
        )
    except Exception as exc:
        logger.error(f"Loss analysis failed: {exc}")
        return

    # Save learning record
    async with AsyncSessionLocal() as session:
        learning = TradeLearning(
            trade_id=trade_id,
            signal_id=trade.signal_id,
            trade_date=trade.entry_time.date() if trade.entry_time else date.today(),
            loss_amount=abs(trade.net_pnl or 0),
            loss_pct=abs(trade.net_pnl_pct or 0),
            miss_category=analysis.get("miss_category", "UNKNOWN"),
            root_cause=analysis.get("root_cause"),
            sl_was_correct=analysis.get("sl_was_correct"),
            sl_recommendation=analysis.get("sl_recommendation"),
            signal_adjustment=analysis.get("signal_adjustment"),
            rule_change_proposed=analysis.get("rule_to_update"),
        )
        session.add(learning)

        # Auto-apply rule changes only after the same rule has been proposed ≥3 times
        # in the last 7 days. A single losing trade is statistically meaningless;
        # requiring 3 independent proposals prevents overfitting to market noise.
        if (
            analysis.get("confidence_in_analysis", 0) >= 75
            and analysis.get("miss_category") != "CORRECT_SETUP_BAD_LUCK"
            and analysis.get("rule_to_update")
        ):
            rule_name = analysis["rule_to_update"]
            new_value = analysis.get("new_rule_value")
            if new_value:
                # Count how many times this same rule has been proposed in the last 7 days
                from sqlalchemy import func
                week_ago = datetime.now(timezone.utc) - timedelta(days=7)
                proposal_count_result = await session.execute(
                    select(func.count(TradeLearning.id))
                    .where(TradeLearning.rule_change_proposed == rule_name)
                    .where(TradeLearning.created_at >= week_ago)
                )
                proposal_count = proposal_count_result.scalar() or 0

                if proposal_count >= 3:
                    existing = await session.execute(
                        select(SignalRule).where(SignalRule.rule_name == rule_name)
                    )
                    rule = existing.scalar_one_or_none()
                    if rule:
                        rule.previous_value = rule.rule_value
                        rule.rule_value = {"value": new_value}
                        rule.changed_by = "AI"
                        rule.change_reason = f"Auto-applied after {proposal_count} proposals in 7 days: {analysis.get('expected_improvement')}"
                        rule.updated_at = datetime.now(timezone.utc)
                    else:
                        rule = SignalRule(
                            rule_name=rule_name,
                            rule_value={"value": new_value},
                            changed_by="AI",
                            change_reason=f"Auto-applied after {proposal_count} proposals in 7 days: {analysis.get('expected_improvement')}",
                        )
                        session.add(rule)

                    learning.rule_change_applied = True
                    learning.rule_change_date = date.today()
                    logger.info(f"Rule '{rule_name}' auto-applied after {proposal_count} proposals")
                else:
                    logger.info(
                        f"Rule '{rule_name}' proposed ({proposal_count}/3 this week) — "
                        f"not yet applied. Need ≥3 proposals to auto-change."
                    )

        await session.commit()

    logger.info(f"Learning recorded for trade {trade_id}: {analysis.get('miss_category')}")


async def run_weekly_prediction_review():
    """Weekly review of prediction accuracy — update signal rules based on patterns."""
    from db.connection import AsyncSessionLocal
    from db.models import Prediction, PredictionMistake
    from sqlalchemy import select

    since = date.today() - timedelta(days=7)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Prediction)
            .where(Prediction.date >= since)
            .where(Prediction.was_correct.isnot(None))
        )
        predictions = result.scalars().all()

    if not predictions:
        return

    total = len(predictions)
    correct = sum(1 for p in predictions if p.was_correct)
    accuracy = correct / total * 100

    logger.info(f"Weekly prediction accuracy: {accuracy:.1f}% ({correct}/{total})")

    # Broadcast weekly review activity
    from websocket.live_feed import manager
    await manager.broadcast_bot_activity(
        f"Weekly review: {accuracy:.1f}% prediction accuracy ({correct}/{total} correct)"
    )


async def run_weekly_options_review():
    """Weekly review of signal performance."""
    from db.connection import AsyncSessionLocal
    from db.models import Signal, Trade, SignalPerformance
    from sqlalchemy import select
    from datetime import date

    since = date.today() - timedelta(days=7)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Trade)
            .where(Trade.status == "CLOSED")
            .where(Trade.entry_time >= datetime.combine(since, datetime.min.time()).replace(tzinfo=timezone.utc))
        )
        trades = result.scalars().all()

    if not trades:
        return

    total = len(trades)
    winners = [t for t in trades if (t.net_pnl or 0) > 0]
    losers = [t for t in trades if (t.net_pnl or 0) <= 0]

    win_rate = len(winners) / total * 100
    avg_win = sum(t.net_pnl_pct or 0 for t in winners) / max(len(winners), 1)
    avg_loss = sum(abs(t.net_pnl_pct or 0) for t in losers) / max(len(losers), 1)
    expectancy = (win_rate / 100 * avg_win) - ((1 - win_rate / 100) * avg_loss)

    logger.info(
        f"Weekly options: win_rate={win_rate:.1f}%, "
        f"avg_win={avg_win:.1f}%, avg_loss={avg_loss:.1f}%, "
        f"expectancy={expectancy:.2f}"
    )


async def run_monthly_calibration():
    """Monthly model calibration based on accumulated mistakes."""
    logger.info("Running monthly calibration...")
    await run_weekly_prediction_review()
    await run_weekly_options_review()


async def run_quarterly_review():
    """Quarterly deep review of all signal rules."""
    logger.info("Running quarterly review...")
    from db.connection import AsyncSessionLocal
    from db.models import SignalRule, TradeLearning
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(TradeLearning)
            .order_by(TradeLearning.created_at.desc())
            .limit(100)
        )
        learnings = result.scalars().all()
        logger.info(f"Quarterly: {len(learnings)} learnings in DB")
