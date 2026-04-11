"""
Trade handler - opens paper trades for AUTO users when a signal passes user settings,
and broadcasts MANUAL alerts otherwise.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from config import settings
from trading.auto_settings import get_user_auto_settings

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
_monitor_tasks: dict[int, asyncio.Task] = {}


def _is_monitor_owner() -> bool:
    return settings.app_role in ("all", "execution_worker")


def _forget_monitor_task(trade_id: int):
    task = _monitor_tasks.get(trade_id)
    if task is None or task.done():
        _monitor_tasks.pop(trade_id, None)


def ensure_trade_monitor(trade_id: int) -> bool:
    if not _is_monitor_owner():
        return False

    task = _monitor_tasks.get(trade_id)
    if task and not task.done():
        return False

    monitor_task = asyncio.create_task(monitor_trade(trade_id), name=f"trade-monitor-{trade_id}")
    _monitor_tasks[trade_id] = monitor_task
    monitor_task.add_done_callback(lambda _: _forget_monitor_task(trade_id))
    return True


async def reconcile_open_trade_monitors() -> int:
    if not _is_monitor_owner():
        return 0

    from sqlalchemy import select

    from db.connection import AsyncSessionLocal
    from db.models import Trade

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Trade.id).where(Trade.status.in_(["OPEN", "PARTIAL"]))
        )
        open_trade_ids = [row[0] for row in result.all()]

    for trade_id in open_trade_ids:
        ensure_trade_monitor(trade_id)

    stale = [trade_id for trade_id in _monitor_tasks if trade_id not in open_trade_ids]
    for trade_id in stale:
        _forget_monitor_task(trade_id)

    return len(open_trade_ids)


async def _get_today_auto_stats(user_id) -> dict:
    from sqlalchemy import func, select

    from db.connection import AsyncSessionLocal
    from db.models import Trade

    now_ist = datetime.now(IST)
    today_start = datetime(now_ist.year, now_ist.month, now_ist.day, 0, 0, 0, tzinfo=IST)

    async with AsyncSessionLocal() as session:
        pnl_q = await session.execute(
            select(func.coalesce(func.sum(Trade.net_pnl), 0))
            .where(Trade.user_id == user_id)
            .where(Trade.trade_mode == "auto")
            .where(Trade.status == "CLOSED")
            .where(Trade.entry_time >= today_start)
        )
        daily_pnl = float(pnl_q.scalar() or 0)

        loss_q = await session.execute(
            select(func.count(Trade.id))
            .where(Trade.user_id == user_id)
            .where(Trade.trade_mode == "auto")
            .where(Trade.status == "CLOSED")
            .where(Trade.net_pnl < 0)
            .where(Trade.entry_time >= today_start)
        )
        loss_count = int(loss_q.scalar() or 0)

        entry_q = await session.execute(
            select(func.count(Trade.id))
            .where(Trade.user_id == user_id)
            .where(Trade.trade_mode == "auto")
            .where(Trade.entry_time >= today_start)
        )
        entry_count = int(entry_q.scalar() or 0)

        open_q = await session.execute(
            select(func.count(Trade.id))
            .where(Trade.user_id == user_id)
            .where(Trade.status.in_(["OPEN", "PARTIAL"]))
        )
        open_count = int(open_q.scalar() or 0)

    return {
        "daily_pnl": daily_pnl,
        "loss_count": loss_count,
        "entry_count": entry_count,
        "open_count": open_count,
    }


async def _load_user_auto_settings(user_id):
    from sqlalchemy import select

    from db.connection import AsyncSessionLocal
    from db.models import User

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
    return get_user_auto_settings(user)


async def _get_recent_stop_loss(user_id, cooldown_minutes: int):
    from sqlalchemy import select

    from db.connection import AsyncSessionLocal
    from db.models import Trade

    if cooldown_minutes <= 0:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=cooldown_minutes)
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Trade.exit_time)
            .where(Trade.user_id == user_id)
            .where(Trade.trade_mode == "auto")
            .where(Trade.exit_reason == "STOP_LOSS")
            .where(Trade.exit_time.is_not(None))
            .where(Trade.exit_time >= cutoff)
            .order_by(Trade.exit_time.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


async def _broadcast_auto_status(user_id, waiting_reason: str | None = None):
    from ws.live_feed import manager

    stats = await _get_today_auto_stats(user_id)
    user_settings = await _load_user_auto_settings(user_id)

    daily_pnl = stats["daily_pnl"]
    loss_count = stats["loss_count"]
    open_count = stats["open_count"]
    daily_target = float(user_settings["daily_profit_target"])
    max_losses = int(user_settings["max_daily_losses"])

    if loss_count >= max_losses:
        status = "HALTED"
        reason = f"{max_losses} losses today - auto halted for the day to protect capital"
    elif daily_pnl >= daily_target:
        status = "TARGET_MET"
        reason = f"Daily target Rs{daily_target:,.0f} achieved"
    elif open_count > 0:
        status = "ACTIVE"
        reason = waiting_reason or "Trade open - monitoring for T1 / T2 / SL"
    else:
        status = "ACTIVE"
        reason = waiting_reason or "Scanning for entry signals - monitoring market conditions..."

    await manager.send_trade_event(
        str(user_id),
        "AUTO_STATUS_UPDATE",
        {
            "status": status,
            "execution_mode": settings.execution_mode,
            "daily_pnl": daily_pnl,
            "daily_target": daily_target,
            "loss_count": loss_count,
            "max_losses": max_losses,
            "waiting_reason": reason,
        },
    )


def _get_signal_time_ist(signal_timestamp) -> datetime:
    if isinstance(signal_timestamp, datetime):
        return signal_timestamp.astimezone(IST)
    return datetime.now(IST)


async def _get_fii_consecutive_days(current_fii_net: float | None) -> int:
    if current_fii_net is None:
        return 0

    from sqlalchemy import select

    from db.connection import AsyncSessionLocal
    from db.models import DailyMarketSnapshot

    target_sign = -1 if current_fii_net < 0 else 1
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DailyMarketSnapshot.fii_net, DailyMarketSnapshot.date)
            .where(DailyMarketSnapshot.time_of_day == "close")
            .where(DailyMarketSnapshot.fii_net.isnot(None))
            .order_by(DailyMarketSnapshot.date.desc())
            .limit(10)
        )
        rows = result.all()

    consecutive = 0
    for row in rows:
        if (row.fii_net < 0 and target_sign == -1) or (row.fii_net >= 0 and target_sign == 1):
            consecutive += 1
        else:
            break
    return max(1, consecutive) if rows else 0


async def _get_signal_auto_block_reason(signal: dict, user_settings: dict) -> str | None:
    underlying = signal.get("underlying", "NIFTY50")
    signal_type = signal.get("signal_type", "BUY_CALL")
    market = signal.get("market_conditions") or {}
    timestamp_ist = _get_signal_time_ist(signal.get("timestamp"))

    if underlying == "BANKNIFTY" and not user_settings["enable_banknifty_auto"]:
        return "BANKNIFTY auto is disabled in your settings"
    if underlying != "BANKNIFTY" and not user_settings["enable_nifty_auto"]:
        return "NIFTY auto is disabled in your settings"

    market_open = timestamp_ist.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = timestamp_ist.replace(hour=15, minute=30, second=0, microsecond=0)
    minutes_since_open = (timestamp_ist - market_open).total_seconds() / 60
    minutes_to_close = (market_close - timestamp_ist).total_seconds() / 60

    if minutes_since_open < user_settings["entry_start_minutes_after_open"]:
        return (
            f"signal came {user_settings['entry_start_minutes_after_open'] - minutes_since_open:.0f} min before your auto start window"
        )
    if minutes_to_close < user_settings["entry_stop_minutes_before_close"]:
        return (
            f"signal came with only {minutes_to_close:.0f} min left before close, inside your stop window"
        )

    confidence = signal.get("confidence")
    if confidence is None or confidence < user_settings["min_confidence"]:
        return f"confidence {confidence or 0:.0f} below your minimum {user_settings['min_confidence']}"

    fresh = market.get("fresh_signals_count")
    if fresh is None or fresh < user_settings["min_fresh_signals"]:
        return f"fresh signal count {fresh or 0} below your minimum {user_settings['min_fresh_signals']}"

    fii_net = market.get("fii_net")
    if fii_net is None:
        return "FII data unavailable"

    fii_consecutive = await _get_fii_consecutive_days(float(fii_net))
    if fii_consecutive < user_settings["min_fii_consecutive_days"]:
        return (
            f"FII directional streak {fii_consecutive} below your minimum {user_settings['min_fii_consecutive_days']}"
        )

    if underlying == "BANKNIFTY":
        price = market.get("banknifty")
        vwap = market.get("banknifty_vwap")
        put_min_vix = user_settings["banknifty_put_min_vix"]
        call_max_vix = user_settings["banknifty_call_max_vix"]
        put_pcr_max = user_settings["banknifty_put_pcr_max"]
        call_pcr_min = user_settings["banknifty_call_pcr_min"]
    else:
        price = market.get("nifty")
        vwap = market.get("vwap")
        put_min_vix = user_settings["nifty_put_min_vix"]
        call_max_vix = user_settings["nifty_call_max_vix"]
        put_pcr_max = user_settings["nifty_put_pcr_max"]
        call_pcr_min = user_settings["nifty_call_pcr_min"]

    vix = market.get("india_vix")
    pcr = market.get("put_call_ratio")

    if price is None or vwap is None:
        return "VWAP alignment data unavailable"
    if vix is None:
        return "VIX unavailable"
    # PCR is a soft gate — only block if explicitly out of range (mirrors options_analyzer behaviour).
    # A signal can be generated when PCR is unavailable, so we must not hard-block here.

    if signal_type == "BUY_CALL":
        if vix > call_max_vix:
            return f"VIX {vix:.2f} above your CALL limit {call_max_vix:.2f}"
        if price <= vwap:
            return f"price {price:.0f} is not above VWAP {vwap:.0f}"
        if fii_net <= 0:
            return f"FII net {fii_net:,.0f} is not buying"
        if pcr is not None and pcr < call_pcr_min:
            return f"PCR {pcr:.2f} below your CALL floor {call_pcr_min:.2f}"
    else:
        if vix < put_min_vix:
            return f"VIX {vix:.2f} below your PUT minimum {put_min_vix:.2f}"
        if price >= vwap:
            return f"price {price:.0f} is not below VWAP {vwap:.0f}"
        if fii_net >= 0:
            return f"FII net {fii_net:,.0f} is not selling"
        if pcr is not None and pcr > put_pcr_max:
            return f"PCR {pcr:.2f} above your PUT ceiling {put_pcr_max:.2f}"

    return None


async def handle_new_signal(signal: dict, users: list):
    from bot.position_calculator import calculate_position
    from db.connection import AsyncSessionLocal
    from db.models import Trade
    from ws.live_feed import manager

    for user in users:
        if not getattr(user, "is_active", True):
            continue

        user_settings = get_user_auto_settings(user)
        underlying = signal.get("underlying", "NIFTY50")
        signal_data = {
            "ltp": signal.get("ltp_at_signal", 0),
            "stop_loss": signal.get("stop_loss", 0),
            "target1": signal.get("target1", 0),
            "target2": signal.get("target2", 0),
            "signal_type": signal.get("signal_type", "BUY_CALL"),
        }

        try:
            position = calculate_position(
                user.capital,
                signal_data,
                underlying=underlying,
                max_risk_pct=float(user_settings["max_risk_pct"]),
                max_deploy_pct=float(user_settings["max_deploy_pct"]),
                min_rr_ratio=float(user_settings["min_rr_ratio"]),
            )
        except ValueError as exc:
            if user.trade_mode == "auto":
                await _broadcast_auto_status(user.id, waiting_reason=f"Signal blocked: {exc}")
            continue

        if user.trade_mode == "auto":
            block_reason = await _get_signal_auto_block_reason(signal, user_settings)
            if block_reason:
                await _broadcast_auto_status(user.id, waiting_reason=f"Signal blocked: {block_reason}")
                continue

            stats = await _get_today_auto_stats(user.id)
            max_losses = int(user_settings["max_daily_losses"])
            daily_target = float(user_settings["daily_profit_target"])
            max_daily_entries = int(user_settings["max_daily_entries"])
            max_risk_pct = float(user_settings["max_risk_pct"])
            max_deploy_pct = float(user_settings["max_deploy_pct"])
            max_slippage_pct = float(user_settings["max_slippage_pct"])
            min_rr_ratio = float(user_settings["min_rr_ratio"])

            recent_stop_loss_at = await _get_recent_stop_loss(
                user.id,
                int(user_settings["cooldown_after_sl_minutes"]),
            )
            if recent_stop_loss_at is not None:
                elapsed_minutes = (datetime.now(timezone.utc) - recent_stop_loss_at).total_seconds() / 60
                remaining_minutes = max(0, int(round(user_settings["cooldown_after_sl_minutes"] - elapsed_minutes)))
                await _broadcast_auto_status(
                    user.id,
                    waiting_reason=(
                        f"Auto cooldown active: {remaining_minutes} min left after your last stop loss"
                    ),
                )
                continue

            if stats["entry_count"] >= max_daily_entries:
                logger.info("AUTO skipped for user %s: max daily entries reached (%s)", user.id, max_daily_entries)
                await _broadcast_auto_status(
                    user.id,
                    waiting_reason=f"Auto paused: max daily entries {max_daily_entries} reached",
                )
                continue

            if stats["loss_count"] >= max_losses:
                logger.info("AUTO skipped for user %s: halted after %s losses", user.id, max_losses)
                await _broadcast_auto_status(user.id)
                continue

            if stats["daily_pnl"] >= daily_target:
                logger.info(
                    "AUTO skipped for user %s: daily target already reached (net today: Rs%s)",
                    user.id,
                    f"{stats['daily_pnl']:,.0f}",
                )
                await _broadcast_auto_status(user.id)
                continue

            if position["minimum"]["max_loss_pct"] > max_risk_pct:
                await _broadcast_auto_status(
                    user.id,
                    waiting_reason=(
                        f"Signal blocked: even 1 lot risks {position['minimum']['max_loss_pct']:.2f}% "
                        f"above your {max_risk_pct:.2f}% cap"
                    ),
                )
                continue

            if position["minimum"]["capital_deployed_pct"] > max_deploy_pct:
                await _broadcast_auto_status(
                    user.id,
                    waiting_reason=(
                        f"Signal blocked: even 1 lot deploys {position['minimum']['capital_deployed_pct']:.2f}% "
                        f"above your {max_deploy_pct:.2f}% cap"
                    ),
                )
                continue

            signal_ltp = signal.get("ltp_at_signal", 0)
            current_ltp = await _get_current_premium(
                signal.get("strike"),
                signal.get("option_type"),
                signal.get("expiry"),
                underlying=underlying,
            )
            if current_ltp is not None and signal_ltp > 0:
                slippage_pct = abs(current_ltp - signal_ltp) / signal_ltp
                if slippage_pct > (max_slippage_pct / 100):
                    slipped_signal = {**signal_data, "ltp": current_ltp}
                    try:
                        slipped_position = calculate_position(
                            user.capital,
                            slipped_signal,
                            underlying=underlying,
                            max_risk_pct=max_risk_pct,
                            max_deploy_pct=max_deploy_pct,
                            min_rr_ratio=min_rr_ratio,
                        )
                        if slipped_position["minimum"]["max_loss_pct"] > max_risk_pct:
                            await _broadcast_auto_status(
                                user.id,
                                waiting_reason=(
                                    f"Signal blocked: slippage {slippage_pct:.1%} pushed minimum risk to "
                                    f"{slipped_position['minimum']['max_loss_pct']:.2f}%"
                                ),
                            )
                            continue
                        if slipped_position["minimum"]["capital_deployed_pct"] > max_deploy_pct:
                            await _broadcast_auto_status(
                                user.id,
                                waiting_reason=(
                                    f"Signal blocked: slippage {slippage_pct:.1%} pushed minimum deployment to "
                                    f"{slipped_position['minimum']['capital_deployed_pct']:.2f}%"
                                ),
                            )
                            continue
                        position = slipped_position
                        signal_ltp = current_ltp
                    except ValueError:
                        logger.warning(
                            "AUTO trade aborted for user %s: slippage %.1f%% degraded sizing or R:R",
                            user.id,
                            slippage_pct * 100,
                        )
                        await _broadcast_auto_status(
                            user.id,
                            waiting_reason=(
                                f"Signal blocked: premium slippage {slippage_pct:.1%} broke your R:R or sizing rules"
                            ),
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

            msg = (
                "PAPER AUTO TRADE OPENED\n"
                f"{signal.get('strike')} {signal.get('option_type')} @ Rs{signal_ltp} x {trade.lots} lots\n"
                f"T1: Rs{signal['target1']} | T2: Rs{signal['target2']} | SL: Rs{signal['stop_loss']}\n"
                f"Max loss: Rs{trade.max_loss_calculated:,.0f} ({trade.max_loss_pct:.2f}% of capital)\n"
                "Execution mode: paper simulation"
            )
            await manager.send_trade_event(
                str(user.id),
                "TRADE_OPENED",
                {
                    "trade_id": trade.id,
                    "message": msg,
                    "execution_mode": settings.execution_mode,
                },
            )

            await _broadcast_auto_status(user.id)
            ensure_trade_monitor(trade.id)
        else:
            await manager.send_trade_event(
                str(user.id),
                "SIGNAL_AWAITING_MANUAL_ENTRY",
                {
                    "signal": signal,
                    "execution_mode": settings.execution_mode,
                },
            )


async def monitor_trade(trade_id: int):
    """
    Event-driven trade monitor.

    When AngelOne is connected and the option token is known:
      - Registers a per-token price-change callback on angel_feed.
      - Each incoming tick fires asyncio.Event immediately — no fixed sleep.
      - Falls back to a 30-second timer if no tick arrives (keeps monitoring
        even if AngelOne is spotty).

    When AngelOne is NOT connected:
      - Falls back to polling _get_current_premium() every 30 seconds.
    """
    from sqlalchemy import select

    from bot.angel_feed import (
        _option_token_cache,
        is_active,
        lookup_and_subscribe_option,
        register_option_price_callback,
        unregister_option_price_callback,
    )
    from db.connection import AsyncSessionLocal
    from db.models import Signal, Trade

    # ── 1. Resolve option token once ────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        t_result = await session.execute(select(Trade).where(Trade.id == trade_id))
        trade_row = t_result.scalar_one_or_none()
        if not trade_row or not trade_row.signal_id:
            return
        s_result = await session.execute(select(Signal).where(Signal.id == trade_row.signal_id))
        signal_row = s_result.scalar_one_or_none()

    if not signal_row:
        return

    underlying_sym = "BANKNIFTY" if (signal_row.underlying or "").upper() == "BANKNIFTY" else "NIFTY"
    expiry_str = str(signal_row.expiry) if signal_row.expiry else ""
    symbol_key = f"{underlying_sym}{expiry_str}{signal_row.strike}{signal_row.option_type.upper()}"

    # ── 2. Set up event-driven tick watcher ─────────────────────────────────
    _price_event: asyncio.Event = asyncio.Event()
    _latest_ltp: dict[str, float] = {}          # mutable container shared with callback

    async def _on_price_tick(token: str, ltp: float) -> None:
        _latest_ltp["v"] = ltp
        _price_event.set()

    option_token: str | None = _option_token_cache.get(symbol_key)
    _callback_registered = False

    async def _ensure_subscribed() -> str | None:
        nonlocal option_token, _callback_registered
        if not is_active():
            return None
        if not option_token:
            option_token = await lookup_and_subscribe_option(
                strike=signal_row.strike,
                option_type=signal_row.option_type.upper(),
                expiry=expiry_str,
                underlying=underlying_sym,
            )
        if option_token and not _callback_registered:
            register_option_price_callback(option_token, _on_price_tick)
            _callback_registered = True
            logger.info(
                "Trade %s: event-driven monitor registered for token %s",
                trade_id, option_token,
            )
        return option_token

    # ── 3. Monitor loop ──────────────────────────────────────────────────────
    FALLBACK_POLL_SECONDS = 30  # used when no tick fires within this window
    try:
        while True:
            # Try to get on the event-driven path
            tok = await _ensure_subscribed()

            if tok and is_active():
                # Wait for the next price tick OR the fallback timeout
                try:
                    await asyncio.wait_for(
                        _price_event.wait(),
                        timeout=FALLBACK_POLL_SECONDS,
                    )
                    _price_event.clear()
                    current_premium = _latest_ltp.get("v")
                except asyncio.TimeoutError:
                    # No tick arrived — fall through to REST / cache lookup
                    current_premium = None
            else:
                # AngelOne not available — classic 30-second poll
                await asyncio.sleep(FALLBACK_POLL_SECONDS)
                current_premium = None

            # If event-driven price was not available, fall back to explicit fetch
            if current_premium is None:
                current_premium = await _get_current_premium(
                    signal_row.strike,
                    signal_row.option_type,
                    signal_row.expiry,
                    underlying=signal_row.underlying or "NIFTY50",
                )

            if current_premium is None:
                continue  # no price available yet — keep waiting

            try:
                async with AsyncSessionLocal() as session:
                    trade_result = await session.execute(select(Trade).where(Trade.id == trade_id))
                    trade = trade_result.scalar_one_or_none()

                    if not trade or trade.status not in ("OPEN", "PARTIAL"):
                        return   # trade closed externally

                    signal_result = await session.execute(
                        select(Signal).where(Signal.id == trade.signal_id)
                    )
                    signal = signal_result.scalar_one_or_none()
                    if not signal:
                        return

                    await _check_and_update_trade(session, trade, signal, current_premium)

                    # If closed by _check_and_update_trade, stop monitoring
                    if trade.status not in ("OPEN", "PARTIAL"):
                        return

            except Exception as exc:
                logger.error("Trade monitor error (trade_id=%s): %s", trade_id, exc, exc_info=True)

    finally:
        # Always de-register callback to avoid dangling references
        if _callback_registered and option_token:
            try:
                unregister_option_price_callback(option_token, _on_price_tick)
            except Exception:
                pass
        _forget_monitor_task(trade_id)


async def _get_current_premium(
    strike: int, option_type: str, expiry, underlying: str = "NIFTY50"
) -> float | None:
    from bot.angel_feed import (
        _option_token_cache,
        get_option_ltp,
        is_active,
        lookup_and_subscribe_option,
    )

    if not is_active():
        logger.warning("AngelOne feed not connected - cannot fetch option LTP")
        return None

    expiry_str = str(expiry) if expiry else ""
    underlying_symbol = "BANKNIFTY" if underlying == "BANKNIFTY" else "NIFTY"
    symbol_key = f"{underlying_symbol}{expiry_str}{strike}{option_type.upper()}"

    token = _option_token_cache.get(symbol_key)
    if token:
        ltp = get_option_ltp(token)
        if ltp is not None and ltp > 0:
            return ltp

    try:
        token = await lookup_and_subscribe_option(
            strike=strike,
            option_type=option_type.upper(),
            expiry=expiry_str,
            underlying=underlying_symbol,
        )
        if token:
            await asyncio.sleep(0.5)
            ltp = get_option_ltp(token)
            if ltp is not None and ltp > 0:
                return ltp
    except Exception as exc:
        logger.debug("AngelOne option LTP lookup failed: %s", exc)

    return None


async def _check_and_update_trade(session, trade, signal, current_premium: float):
    from ws.live_feed import manager

    lot_size = 15 if (signal.underlying or "NIFTY50") == "BANKNIFTY" else 25

    if current_premium >= signal.target1 and not trade.t1_exit_done:
        profit = (current_premium - trade.entry_premium) * trade.partial_t1_lots * lot_size
        trade.t1_exit_done = True
        trade.t1_exit_premium = current_premium
        trade.t1_exit_time = datetime.now(timezone.utc)
        trade.t1_exit_profit = round(profit, 2)
        trade.status = "PARTIAL"
        await session.commit()

        msg = (
            "TARGET 1 HIT\n"
            f"{signal.strike} {signal.option_type} reached Rs{current_premium:.1f}\n"
            f"{trade.partial_t1_lots} lots: +Rs{profit:,.0f} locked\n"
            f"Remaining {trade.partial_t2_lots} lots riding to T2 (Rs{signal.target2})\n"
            f"Trailing SL now: Rs{trade.trailing_sl_after_t1}"
        )
        await manager.send_trade_event(
            str(trade.user_id),
            "TRADE_ALERT_T1",
            {"message": msg, "trade_id": trade.id, "execution_mode": settings.execution_mode},
        )

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

        await manager.send_trade_event(
            str(trade.user_id),
            "TRADE_ALERT_T2",
            {
                "message": f"TARGET 2 HIT! Full trade closed. Net P&L: Rs{trade.net_pnl:,.0f}",
                "trade_id": trade.id,
                "execution_mode": settings.execution_mode,
            },
        )
        await _broadcast_auto_status(trade.user_id)

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

        signal.status = "HIT_SL"
        signal.outcome_time = datetime.now(timezone.utc)
        signal.outcome_premium = current_premium
        await session.commit()

        await manager.send_trade_event(
            str(trade.user_id),
            "TRADE_ALERT_SL",
            {
                "message": (
                    f"STOP LOSS HIT\nLoss: Rs{trade.net_pnl:,.0f} ({trade.net_pnl_pct:.1f}%)\n"
                    "Learning engine running analysis..."
                ),
                "trade_id": trade.id,
                "execution_mode": settings.execution_mode,
            },
        )
        await _broadcast_auto_status(trade.user_id)
        asyncio.create_task(_run_loss_learning(trade.id))

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
        await _broadcast_auto_status(trade.user_id)

    unrealised = (current_premium - trade.entry_premium) * trade.lots * lot_size
    await manager.send_trade_event(
        str(trade.user_id),
        "PNL_UPDATE",
        {
            "trade_id": trade.id,
            "current_premium": current_premium,
            "unrealised_pnl": round(unrealised, 2),
            "execution_mode": settings.execution_mode,
        },
    )


async def _run_loss_learning(trade_id: int):
    try:
        from bot.learning_engine import process_losing_trade

        await process_losing_trade(trade_id)
    except Exception as exc:
        logger.error("Loss learning failed for trade %s: %s", trade_id, exc)


def _estimate_charges(lots: int, premium: float, lot_size: int) -> float:
    turnover = premium * lots * lot_size
    return round(turnover * 0.0015, 2)