"""
Trade handler — auto-logs trades when a signal fires in AUTO mode.
Monitors open trades for T1/T2/SL hits.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


async def handle_new_signal(signal: dict, users: list):
    """
    AUTO mode: Trade logged immediately — no confirmation.
    MANUAL mode: Signal broadcast to WebSocket — user fills in price/qty.
    """
    from bot.position_calculator import calculate_position
    from bot.telegram_sender import send_signal_message, send_auto_trade_opened
    from db.connection import AsyncSessionLocal
    from db.models import Trade, User
    from websocket.live_feed import manager

    for user in users:
        if not getattr(user, "is_active", True):
            continue

        underlying = signal.get("underlying", "NIFTY50")
        signal_data = {
            "ltp": signal.get("ltp_at_signal", 0),
            "stop_loss": signal.get("stop_loss", 0),
            "target1": signal.get("target1", 0),
            "target2": signal.get("target2", 0),
            "signal_type": signal.get("signal_type", "BUY_CALL"),
        }

        try:
            position = calculate_position(user.capital, signal_data, underlying=underlying)
        except ValueError:
            continue

        if user.trade_mode == "auto":
            # Slippage guard: check current market price before opening the trade.
            # If the premium has moved > 3% while Claude was processing, the R:R
            # ratio may have deteriorated. Abort if it falls below the 2.0 minimum.
            signal_ltp = signal.get("ltp_at_signal", 0)
            current_ltp = await _get_current_premium(
                signal.get("strike"), signal.get("option_type"), signal.get("expiry"),
                underlying=underlying,
            )
            if current_ltp is not None and signal_ltp > 0:
                slippage_pct = abs(current_ltp - signal_ltp) / signal_ltp
                if slippage_pct > 0.03:
                    # Recalculate R:R with the actual market price
                    slipped_signal = {**signal_data, "ltp": current_ltp}
                    try:
                        slipped_position = calculate_position(user.capital, slipped_signal, underlying=underlying)
                        if slipped_position["rr_ratio"] < 2.0:
                            logger.warning(
                                f"AUTO trade aborted for user {user.id}: "
                                f"slippage {slippage_pct:.1%} degraded R:R to "
                                f"{slipped_position['rr_ratio']:.2f} (min 2.0). "
                                f"Signal LTP ₹{signal_ltp}, market now ₹{current_ltp:.1f}"
                            )
                            continue
                        # R:R still ok — update to actual execution price
                        position = slipped_position
                        signal_ltp = current_ltp
                        logger.info(
                            f"AUTO trade: slippage {slippage_pct:.1%} but R:R {slipped_position['rr_ratio']:.2f} still acceptable. "
                            f"Entry adjusted to ₹{current_ltp:.1f}"
                        )
                    except ValueError:
                        logger.warning(
                            f"AUTO trade aborted for user {user.id}: slippage {slippage_pct:.1%} made R:R invalid"
                        )
                        continue

            async with AsyncSessionLocal() as session:
                trade = Trade(
                    signal_id=signal.get("id"),
                    user_id=user.id,
                    trade_mode="auto",
                    capital_at_entry=user.capital,
                    lots=position["recommended"]["lots"],
                    entry_premium=signal_ltp,
                    entry_time=datetime.now(timezone.utc),
                    rr_at_entry=position["rr_ratio"],
                    premium_total=position["recommended"]["premium"],
                    max_loss_calculated=position["recommended"]["max_loss"],
                    max_loss_pct=position["recommended"]["max_loss_pct"],
                    target1_profit_calculated=position["recommended"]["profit_t1"],
                    target2_profit_calculated=position["recommended"]["profit_t2"],
                    partial_t1_lots=position["partial_exit_plan"]["exit_at_t1_lots"],
                    partial_t2_lots=position["partial_exit_plan"]["hold_to_t2_lots"],
                    trailing_sl_after_t1=position["partial_exit_plan"]["trailing_sl_after_t1"],
                    status="OPEN",
                )
                session.add(trade)
                await session.commit()
                await session.refresh(trade)

            # Notify user
            msg = (
                f"⚡ AUTO TRADE OPENED\n"
                f"{signal.get('strike')} {signal.get('option_type')} · "
                f"₹{signal_ltp} · {trade.lots} lots\n"
                f"T1: ₹{signal['target1']} | T2: ₹{signal['target2']} | "
                f"SL: ₹{signal['stop_loss']}\n"
                f"Max loss: ₹{trade.max_loss_calculated:,.0f} "
                f"({trade.max_loss_pct:.2f}% of capital)\n"
                f"Bot is monitoring every 30 seconds."
            )
            await manager.send_trade_event(str(user.id), "TRADE_OPENED", {"trade_id": trade.id, "message": msg})

            # Start monitoring this trade
            asyncio.create_task(monitor_trade(trade.id))

        else:
            # MANUAL mode — broadcast signal for user to fill in
            await manager.send_trade_event(str(user.id), "SIGNAL_AWAITING_MANUAL_ENTRY", {
                "signal": signal
            })


async def monitor_trade(trade_id: int):
    """
    Monitor an open trade every 30 seconds.
    Checks T1, T2, SL, trailing SL, and exit conditions.
    """
    from db.connection import AsyncSessionLocal
    from db.models import Trade, Signal

    while True:
        await asyncio.sleep(30)
        try:
            async with AsyncSessionLocal() as session:
                from sqlalchemy import select
                trade_result = await session.execute(select(Trade).where(Trade.id == trade_id))
                trade = trade_result.scalar_one_or_none()

                if not trade or trade.status not in ("OPEN", "PARTIAL"):
                    return  # Trade closed

                signal_result = await session.execute(
                    select(Signal).where(Signal.id == trade.signal_id)
                )
                signal = signal_result.scalar_one_or_none()
                if not signal:
                    return

                current_premium = await _get_current_premium(signal.strike, signal.option_type, signal.expiry)
                if current_premium is None:
                    continue

                await _check_and_update_trade(session, trade, signal, current_premium)
        except Exception as exc:
            logger.error(f"Trade monitor error (trade_id={trade_id}): {exc}", exc_info=True)


async def _get_current_premium(
    strike: int, option_type: str, expiry, underlying: str = "NIFTY50"
) -> float | None:
    """
    Fetch current LTP for a specific option contract from AngelOne.

    1. Check WebSocket cache (instant — token already subscribed from prior lookup)
    2. REST lookup via AngelOne searchScrip → subscribe → wait for first tick
    """
    from bot.angel_feed import (
        is_active, get_option_ltp, lookup_and_subscribe_option, _option_token_cache,
    )

    if not is_active():
        logger.warning("AngelOne feed not connected — cannot fetch option LTP")
        return None

    expiry_str = str(expiry) if expiry else ""
    underlying_symbol = "BANKNIFTY" if underlying == "BANKNIFTY" else "NIFTY"
    symbol_key = f"{underlying_symbol}{expiry_str}{strike}{option_type.upper()}"

    # 1. Instant cache hit if we already subscribed this token before
    token = _option_token_cache.get(symbol_key)
    if token:
        ltp = get_option_ltp(token)
        if ltp is not None and ltp > 0:
            return ltp

    # 2. Look up token via AngelOne REST, subscribe it, then wait for first tick
    try:
        token = await lookup_and_subscribe_option(
            strike=strike,
            option_type=option_type.upper(),
            expiry=expiry_str,
            underlying=underlying_symbol,
        )
        if token:
            await asyncio.sleep(0.5)  # allow first WebSocket tick to arrive
            ltp = get_option_ltp(token)
            if ltp is not None and ltp > 0:
                return ltp
    except Exception as exc:
        logger.debug(f"AngelOne option LTP lookup failed: {exc}")

    return None


async def _check_and_update_trade(session, trade, signal, current_premium: float):
    from bot.telegram_sender import send_message
    from websocket.live_feed import manager

    lot_size = 25

    # T1 hit
    if current_premium >= signal.target1 and not trade.t1_exit_done:
        profit = (current_premium - trade.entry_premium) * trade.partial_t1_lots * lot_size
        trade.t1_exit_done = True
        trade.t1_exit_premium = current_premium
        trade.t1_exit_time = datetime.now(timezone.utc)
        trade.t1_exit_profit = round(profit, 2)
        trade.status = "PARTIAL"
        await session.commit()

        msg = (
            f"🎯 TARGET 1 HIT! | {datetime.now(timezone.utc).strftime('%H:%M')}\n"
            f"{signal.strike} {signal.option_type} reached ₹{current_premium:.1f}\n"
            f"{trade.partial_t1_lots} lots: +₹{profit:,.0f} locked\n"
            f"Remaining {trade.partial_t2_lots} lots riding to T2 (₹{signal.target2})\n"
            f"Trailing SL now: ₹{trade.trailing_sl_after_t1}"
        )
        await manager.send_trade_event(str(trade.user_id), "TRADE_ALERT_T1", {"message": msg, "trade_id": trade.id})

    # T2 hit (on remaining lots after T1)
    elif current_premium >= signal.target2 and trade.t1_exit_done:
        remaining_lots = trade.partial_t2_lots or 0
        profit = (current_premium - trade.entry_premium) * remaining_lots * lot_size
        trade.exit_premium = current_premium
        trade.exit_time = datetime.now(timezone.utc)
        trade.exit_reason = "TARGET2"
        total_profit = (trade.t1_exit_profit or 0) + profit
        trade.gross_pnl = round(total_profit, 2)
        trade.net_pnl = round(total_profit - _estimate_charges(trade.lots, trade.entry_premium, lot_size), 2)
        trade.net_pnl_pct = round(trade.net_pnl / trade.capital_at_entry * 100, 2)
        trade.status = "CLOSED"
        await session.commit()

        await manager.send_trade_event(str(trade.user_id), "TRADE_ALERT_T2", {
            "message": f"🎯🎯 TARGET 2 HIT! Full trade closed. Net P&L: ₹{trade.net_pnl:,.0f}",
            "trade_id": trade.id,
        })

    # SL hit
    elif current_premium <= signal.stop_loss:
        loss = (current_premium - trade.entry_premium) * trade.lots * lot_size
        trade.exit_premium = current_premium
        trade.exit_time = datetime.now(timezone.utc)
        trade.exit_reason = "STOP_LOSS"
        trade.gross_pnl = round(loss, 2)
        trade.net_pnl = round(loss - _estimate_charges(trade.lots, trade.entry_premium, lot_size), 2)
        trade.net_pnl_pct = round(trade.net_pnl / trade.capital_at_entry * 100, 2)
        trade.status = "CLOSED"
        await session.commit()

        # Trigger loss analysis
        signal.status = "HIT_SL"
        signal.outcome_time = datetime.now(timezone.utc)
        signal.outcome_premium = current_premium
        await session.commit()

        await manager.send_trade_event(str(trade.user_id), "TRADE_ALERT_SL", {
            "message": f"🛑 STOP LOSS HIT\nLoss: ₹{trade.net_pnl:,.0f} ({trade.net_pnl_pct:.1f}%)\nLearning engine running analysis...",
            "trade_id": trade.id,
        })

        # Run learning engine in background
        import asyncio
        asyncio.create_task(_run_loss_learning(trade.id))

    # Trailing SL hit
    elif trade.t1_exit_done and trade.trailing_sl_after_t1 and current_premium <= trade.trailing_sl_after_t1:
        remaining_lots = trade.partial_t2_lots or 0
        pnl = (current_premium - trade.entry_premium) * remaining_lots * lot_size + (trade.t1_exit_profit or 0)
        trade.exit_premium = current_premium
        trade.exit_time = datetime.now(timezone.utc)
        trade.exit_reason = "PARTIAL"
        trade.gross_pnl = round(pnl, 2)
        trade.net_pnl = round(pnl - _estimate_charges(trade.lots, trade.entry_premium, lot_size), 2)
        trade.net_pnl_pct = round(trade.net_pnl / trade.capital_at_entry * 100, 2)
        trade.status = "CLOSED"
        await session.commit()

    # Broadcast unrealised P&L
    unrealised = (current_premium - trade.entry_premium) * trade.lots * lot_size
    await manager.send_trade_event(str(trade.user_id), "PNL_UPDATE", {
        "trade_id": trade.id,
        "current_premium": current_premium,
        "unrealised_pnl": round(unrealised, 2),
    })


async def _run_loss_learning(trade_id: int):
    """Run Claude loss analysis after a SL hit."""
    try:
        from bot.learning_engine import process_losing_trade
        await process_losing_trade(trade_id)
    except Exception as exc:
        logger.error(f"Loss learning failed for trade {trade_id}: {exc}")


def _estimate_charges(lots: int, premium: float, lot_size: int) -> float:
    turnover = premium * lots * lot_size
    return round(turnover * 0.0015, 2)
