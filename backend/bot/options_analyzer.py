"""
Options signal engine — checks all gates and generates BUY_PUT / BUY_CALL signals.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from config import settings

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


# ── Gate configurations ──────────────────────────────────────────────────────

# Nifty 50 gates
SIGNAL_GATES = {
    "data_quality": {
        "min_fresh_signals": settings.min_fresh_signals,
        "max_data_age_minutes": 5,
    },
    "timing": {
        "not_before_minutes_after_open": 30,
        "not_after_minutes_before_close": 60,
        "cooldown_after_sl_minutes": settings.signal_cooldown_after_sl,
    },
    "min_quality": {
        "min_confidence": settings.min_confidence,
        "min_rr_ratio": settings.min_rr_ratio,
        "max_daily_signals": settings.max_daily_signals,
    },
    "put_specific": {
        "nifty_must_be_below_vwap": True,
        "min_vix": settings.min_vix_for_put,
        "fii_direction": "SELL",
        "min_fii_consecutive_sell_days": settings.min_fii_consecutive_days,
        # Block only at extreme panic (crowded short). PCR > 1.30 = late to PUT.
        "pcr_max": 1.30,
    },
    "call_specific": {
        "nifty_must_be_above_vwap": True,
        "max_vix": 28.0,
        "fii_direction": "BUY",
        "min_fii_consecutive_buy_days": settings.min_fii_consecutive_days,
        # Block only at extreme euphoria (crowded long). PCR < 0.50 = late to CALL.
        "pcr_min": 0.50,
    },
}

# Bank Nifty gates — wider VIX bands because BN moves 2-3x Nifty per session.
# Everything else mirrors Nifty logic.
BANKNIFTY_GATES = {
    "data_quality": {
        "min_fresh_signals": settings.min_fresh_signals,
        "max_data_age_minutes": 5,
    },
    "timing": {
        "not_before_minutes_after_open": 30,
        "not_after_minutes_before_close": 60,
        "cooldown_after_sl_minutes": settings.signal_cooldown_after_sl,
    },
    "min_quality": {
        "min_confidence": settings.min_confidence,
        "min_rr_ratio": settings.min_rr_ratio,
        "max_daily_signals": settings.max_daily_signals,
    },
    "put_specific": {
        "must_be_below_vwap": True,
        # BN needs higher VIX for PUT — enough volatility for a real move
        "min_vix": 17.0,
        "fii_direction": "SELL",
        "min_fii_consecutive_sell_days": settings.min_fii_consecutive_days,
        "pcr_max": 1.30,
    },
    "call_specific": {
        "must_be_above_vwap": True,
        # BN tolerates higher VIX for CALL — normal for banking sector
        "max_vix": 35.0,
        "fii_direction": "BUY",
        "min_fii_consecutive_buy_days": settings.min_fii_consecutive_days,
        "pcr_min": 0.50,
    },
}


class GateCheckResult:
    def __init__(self):
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.blocked_reason: str | None = None

    @property
    def all_passed(self) -> bool:
        return len(self.failed) == 0

    def fail(self, gate: str, reason: str):
        self.failed.append(gate)
        if not self.blocked_reason:
            self.blocked_reason = reason


def check_timing_gates(now: datetime) -> GateCheckResult:
    result = GateCheckResult()
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)

    minutes_since_open = (now - market_open).total_seconds() / 60
    minutes_to_close = (market_close - now).total_seconds() / 60

    if minutes_since_open < 30:
        result.fail("timing_open", f"Too early — {30 - minutes_since_open:.0f}min before 9:45 AM")
    else:
        result.passed.append("timing_open")

    if minutes_to_close < 60:
        result.fail("timing_close", f"Too late — only {minutes_to_close:.0f}min to close")
    else:
        result.passed.append("timing_close")

    return result


async def check_daily_signal_count(session) -> int:
    """Return number of signals already generated today."""
    from db.models import Signal
    from sqlalchemy import func, select
    today = date.today()
    result = await session.execute(
        select(func.count(Signal.id))
        .where(Signal.timestamp >= datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc))
        .where(Signal.status != "CANCELLED")
    )
    return result.scalar() or 0


async def check_sl_cooldown(session) -> bool:
    """Return True if we're in cooldown after a SL hit."""
    from db.models import Signal
    from sqlalchemy import select
    cooldown_cutoff = datetime.now(timezone.utc) - timedelta(minutes=settings.signal_cooldown_after_sl)
    result = await session.execute(
        select(Signal)
        .where(Signal.status == "HIT_SL")
        .where(Signal.outcome_time >= cooldown_cutoff)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def check_put_gates_bn(data: dict) -> GateCheckResult:
    """Bank Nifty PUT gate checks — uses banknifty spot vs banknifty VWAP."""
    result = GateCheckResult()
    gates = BANKNIFTY_GATES["put_specific"]

    vix = data.get("india_vix")
    if vix is None or vix < gates["min_vix"]:
        result.fail("vix", f"VIX {vix} below minimum {gates['min_vix']} for BN PUT")
    else:
        result.passed.append("vix")

    bn = data.get("banknifty")
    vwap = data.get("banknifty_vwap")
    if bn and vwap and bn >= vwap:
        result.fail("vwap", f"BankNifty {bn} >= VWAP {vwap} — PUT requires below VWAP")
    elif bn and vwap:
        result.passed.append("vwap")

    fii_net = data.get("fii_net", 0) or 0
    if fii_net >= 0:
        result.fail("fii", f"FII net {fii_net:,.0f} is not selling — PUT needs FII sell days")
    else:
        result.passed.append("fii")

    pcr = data.get("put_call_ratio")
    if pcr and pcr > gates["pcr_max"]:
        result.fail("pcr", f"PCR {pcr:.2f} > {gates['pcr_max']} — extreme panic/crowded short, late for BN PUT")
    elif pcr:
        result.passed.append("pcr")

    return result


def check_call_gates_bn(data: dict) -> GateCheckResult:
    """Bank Nifty CALL gate checks — uses banknifty spot vs banknifty VWAP."""
    result = GateCheckResult()
    gates = BANKNIFTY_GATES["call_specific"]

    vix = data.get("india_vix")
    if vix is None:
        result.fail("vix", "VIX data unavailable — BN CALL blocked")
    elif vix > gates["max_vix"]:
        result.fail("vix", f"VIX {vix} > {gates['max_vix']} — too volatile for BN CALL")
    else:
        result.passed.append("vix")

    bn = data.get("banknifty")
    vwap = data.get("banknifty_vwap")
    if bn and vwap and bn <= vwap:
        result.fail("vwap", f"BankNifty {bn} <= VWAP {vwap} — CALL requires above VWAP")
    elif bn and vwap:
        result.passed.append("vwap")

    fii_net = data.get("fii_net", 0) or 0
    if fii_net <= 0:
        result.fail("fii", f"FII net {fii_net:,.0f} is not buying — CALL needs FII buy days")
    else:
        result.passed.append("fii")

    pcr = data.get("put_call_ratio")
    if pcr and pcr < gates["pcr_min"]:
        result.fail("pcr", f"PCR {pcr:.2f} < {gates['pcr_min']} — extreme euphoria/crowded long, late for BN CALL")
    elif pcr:
        result.passed.append("pcr")

    return result


def check_put_gates(data: dict) -> GateCheckResult:
    result = GateCheckResult()
    gates = SIGNAL_GATES["put_specific"]

    # VIX check
    vix = data.get("india_vix")
    if vix is None or vix < gates["min_vix"]:
        result.fail("vix", f"VIX {vix} below minimum {gates['min_vix']} for PUT")
    else:
        result.passed.append("vix")

    # VWAP check
    nifty = data.get("nifty")
    vwap = data.get("vwap")
    if nifty and vwap and nifty >= vwap:
        result.fail("vwap", f"Nifty {nifty} >= VWAP {vwap} — PUT requires below VWAP")
    elif nifty and vwap:
        result.passed.append("vwap")

    # FII check
    fii_net = data.get("fii_net", 0) or 0
    if fii_net >= 0:
        result.fail("fii", f"FII net {fii_net:,.0f} is not selling — PUT needs FII sell days")
    else:
        result.passed.append("fii")

    # PCR check
    pcr = data.get("put_call_ratio")
    if pcr and pcr > gates["pcr_max"]:
        result.fail("pcr", f"PCR {pcr:.2f} > {gates['pcr_max']} — extreme panic/crowded short, late for PUT")
    elif pcr:
        result.passed.append("pcr")

    return result


def check_call_gates(data: dict) -> GateCheckResult:
    result = GateCheckResult()
    gates = SIGNAL_GATES["call_specific"]

    # VIX check — fail if unavailable (consistent with check_put_gates)
    vix = data.get("india_vix")
    if vix is None:
        result.fail("vix", "VIX data unavailable — CALL blocked")
    elif vix > gates["max_vix"]:
        result.fail("vix", f"VIX {vix} > {gates['max_vix']} — too volatile for CALL")
    else:
        result.passed.append("vix")

    # VWAP check
    nifty = data.get("nifty")
    vwap = data.get("vwap")
    if nifty and vwap and nifty <= vwap:
        result.fail("vwap", f"Nifty {nifty} <= VWAP {vwap} — CALL requires above VWAP")
    elif nifty and vwap:
        result.passed.append("vwap")

    # FII check
    fii_net = data.get("fii_net", 0) or 0
    if fii_net <= 0:
        result.fail("fii", f"FII net {fii_net:,.0f} is not buying — CALL needs FII buy days")
    else:
        result.passed.append("fii")

    # PCR check
    pcr = data.get("put_call_ratio")
    if pcr and pcr < gates["pcr_min"]:
        result.fail("pcr", f"PCR {pcr:.2f} < {gates['pcr_min']} — extreme euphoria/crowded long, late for CALL")
    elif pcr:
        result.passed.append("pcr")

    return result


async def check_and_generate_signal(underlying: str = "NIFTY50"):
    """
    Main entry point — check all gates and generate signal if warranted.

    underlying: "NIFTY50" (default) or "BANKNIFTY"
    """
    is_bn = underlying == "BANKNIFTY"

    from bot.analyzer import _call_claude_json, OPTIONS_SIGNAL_PROMPT, BANKNIFTY_SIGNAL_PROMPT
    from bot.collector import collect_all_signals, calculate_vwap
    from bot.intraday import get_intraday_technicals, get_options_chain_summary
    from bot.position_calculator import calculate_position
    from db.connection import AsyncSessionLocal
    from db.models import Signal, SignalRule, User
    from sqlalchemy import select
    from ws.live_feed import manager

    now = datetime.now(tz=IST)

    # Timing gates (same for both underlyings)
    timing = check_timing_gates(now)
    if not timing.all_passed:
        logger.debug(f"[{underlying}] Signal blocked: {timing.blocked_reason}")
        return

    async with AsyncSessionLocal() as session:
        daily_count = await check_daily_signal_count(session)
        if daily_count >= settings.max_daily_signals:
            logger.debug(f"[{underlying}] Daily signal limit reached: {daily_count}")
            return

        in_cooldown = await check_sl_cooldown(session)
        if in_cooldown:
            logger.debug(f"[{underlying}] In SL cooldown period")
            return

    # Collect live data
    data = await collect_all_signals()

    # VWAP comes directly from AngelOne feed cache — no symbol arg needed
    if is_bn:
        from bot.angel_feed import get_live_price
        bn_vwap = get_live_price("banknifty_vwap")
        if bn_vwap:
            data["banknifty_vwap"] = bn_vwap
    else:
        vwap = await calculate_vwap()
        if vwap:
            data["vwap"] = vwap

    # Data quality check
    fresh = data.get("fresh_signals_count", 0)
    if fresh < settings.min_fresh_signals:
        logger.warning(f"[{underlying}] Insufficient data: {fresh}/{settings.min_fresh_signals} signals")
        return

    # Intraday technicals and options chain for the correct underlying
    angel_symbol = "BANKNIFTY" if is_bn else "NIFTY"
    spot_price = data.get("banknifty", 0) if is_bn else data.get("nifty", 0)

    technicals = await get_intraday_technicals(symbol=angel_symbol)
    chain = await get_options_chain_summary(symbol=angel_symbol, spot_price=spot_price)

    # Gate checks — Bank Nifty uses its own wider-band gates
    if is_bn:
        put_gates = check_put_gates_bn(data)
        call_gates = check_call_gates_bn(data)
    else:
        put_gates = check_put_gates(data)
        call_gates = check_call_gates(data)

    signal_direction = None
    gates_summary = {}

    if put_gates.all_passed and len(put_gates.passed) >= 3:
        signal_direction = "PUT"
        gates_summary = {"put": put_gates.passed, "timing": timing.passed}
    elif call_gates.all_passed and len(call_gates.passed) >= 3:
        signal_direction = "CALL"
        gates_summary = {"call": call_gates.passed, "timing": timing.passed}
    else:
        logger.debug(
            f"[{underlying}] Gates not met. "
            f"PUT passed={put_gates.passed} failed={put_gates.failed}. "
            f"CALL passed={call_gates.passed} failed={call_gates.failed}"
        )
        return

    # Get active signal rules for prompt context
    async with AsyncSessionLocal() as session:
        rules_result = await session.execute(
            select(SignalRule).where(SignalRule.is_active == True).limit(10)
        )
        rules = rules_result.scalars().all()
        rules_text = "\n".join(f"- {r.rule_name}: {r.rule_value}" for r in rules)

    from bot.analyzer import _load_claude_memories
    claude_memories = await _load_claude_memories(categories=["loss_patterns", "market_regime", "prediction_performance"])

    fii_net = data.get("fii_net") or 0
    fii_direction = "SELL" if fii_net < 0 else "BUY"

    # Compute actual FII consecutive days from recent DB snapshots
    async with AsyncSessionLocal() as session:
        from db.models import DailyMarketSnapshot
        from sqlalchemy import select as sa_select
        snap_result = await session.execute(
            sa_select(DailyMarketSnapshot.fii_net, DailyMarketSnapshot.date)
            .where(DailyMarketSnapshot.time_of_day == "close")
            .where(DailyMarketSnapshot.fii_net.isnot(None))
            .order_by(DailyMarketSnapshot.date.desc())
            .limit(10)
        )
        rows = snap_result.all()
    fii_consecutive = 0
    if rows:
        target_sign = -1 if fii_net < 0 else 1
        for row in rows:
            if (row.fii_net < 0 and target_sign == -1) or (row.fii_net >= 0 and target_sign == 1):
                fii_consecutive += 1
            else:
                break
    fii_consecutive = max(1, fii_consecutive)  # at least 1 (today)

    # Guard: block if VWAP is None (market just opened, VWAP not yet computed)
    spot_vwap = data.get("banknifty_vwap") if is_bn else data.get("vwap")
    if spot_vwap is None:
        logger.debug(f"[{underlying}] Signal blocked: VWAP not yet available from AngelOne feed")
        return

    # Build prompt for the correct underlying
    if is_bn:
        bn_price = spot_price
        bn_vwap = spot_vwap
        bn_vs_vwap = ((bn_price - bn_vwap) / bn_vwap * 100) if bn_vwap else 0
        prompt = BANKNIFTY_SIGNAL_PROMPT.format(
            time=now.strftime("%H:%M IST"),
            banknifty_price=bn_price,
            vwap=bn_vwap,
            bn_vs_vwap=bn_vs_vwap,
            vix=data.get("india_vix") or "N/A",
            pcr=data.get("put_call_ratio") or "N/A",
            fii_net=fii_net,
            fii_direction=fii_direction,
            fii_consecutive=fii_consecutive,
            vix_trend="RISING" if (data.get("india_vix") or 0) > 18 else "STABLE",
            nifty_price=data.get("nifty", "N/A"),
            us_10y=data.get("us_10y") or "N/A",
            crude=data.get("crude_brent") or "N/A",
            usd_inr=data.get("usd_inr") or "N/A",
            rsi_5m=technicals.get("rsi_14") or "N/A",
            ema9=technicals.get("ema9") or "N/A",
            ema21=technicals.get("ema21") or "N/A",
            volume_ratio=technicals.get("volume_ratio") or 1.0,
            options_chain_relevant_strikes=str(chain.get("chain_around_atm", []))[:2000],
            signal_rules=rules_text or "Default rules active",
            claude_memories=claude_memories,
            vwap_gate="PASS" if (put_gates if signal_direction == "PUT" else call_gates).all_passed else "FAIL",
            vix_gate="PASS",
            fii_gate="PASS",
            pcr_gate="PASS",
            time_check="PASS" if timing.all_passed else "FAIL",
            time_check_close="PASS",
            data_quality=f"{fresh}/47 fresh",
            cooldown_ok="PASS",
        )
    else:
        nifty_price = spot_price
        vwap_val = spot_vwap
        nifty_vs_vwap = ((nifty_price - vwap_val) / vwap_val * 100) if vwap_val else 0
        prompt = OPTIONS_SIGNAL_PROMPT.format(
            time=now.strftime("%H:%M IST"),
            nifty_price=nifty_price,
            vwap=vwap_val,
            nifty_vs_vwap=nifty_vs_vwap,
            vix=data.get("india_vix") or "N/A",
            pcr=data.get("put_call_ratio") or "N/A",
            fii_net=fii_net,
            fii_direction=fii_direction,
            fii_consecutive=fii_consecutive,
            vix_trend="RISING" if (data.get("india_vix") or 0) > 18 else "STABLE",
            rsi_5m=technicals.get("rsi_14") or "N/A",
            ema9=technicals.get("ema9") or "N/A",
            ema21=technicals.get("ema21") or "N/A",
            volume_ratio=technicals.get("volume_ratio") or 1.0,
            options_chain_relevant_strikes=str(chain.get("chain_around_atm", []))[:2000],
            signal_rules=rules_text or "Default rules active",
            claude_memories=claude_memories,
            min_vix_put=settings.min_vix_for_put,
            min_fii_days=settings.min_fii_consecutive_days,
            time_check="PASS" if timing.all_passed else "FAIL",
            time_check_close="PASS",
            data_quality=f"{fresh}/47 fresh",
            cooldown_ok="PASS",
        )

    try:
        result = await _call_claude_json(prompt)
    except Exception as exc:
        logger.error(f"[{underlying}] Claude signal generation failed: {exc}")
        return

    if result.get("signal_type") == "NONE":
        logger.info(f"[{underlying}] Claude said NONE: {result.get('reason_if_none')}")
        return

    # Validate R:R before saving
    from bot.position_calculator import calculate_position as calc_pos
    # Claude returns "approximate_ltp" — normalise to "ltp" for position_calculator
    entry_ltp = result.get("approximate_ltp") or result.get("ltp", 0)
    signal_data = {
        "ltp": entry_ltp,
        "stop_loss": result.get("stop_loss", 0),
        "target1": result.get("target1", 0),
        "target2": result.get("target2", 0),
        "signal_type": result.get("signal_type"),
    }

    try:
        position = calc_pos(200_000, signal_data, underlying=underlying)
    except ValueError as exc:
        logger.warning(f"[{underlying}] Signal blocked by position calc: {exc}")
        return

    # Parse expiry
    import datetime as dt
    try:
        expiry = dt.datetime.strptime(result.get("suggested_expiry", ""), "%d-%b-%Y").date()
    except (ValueError, TypeError):
        expiry = date.today() + timedelta(days=7)

    valid_until = datetime.now(timezone.utc) + timedelta(minutes=90)

    async with AsyncSessionLocal() as session:
        signal = Signal(
            timestamp=datetime.now(timezone.utc),
            signal_type=result["signal_type"],
            underlying=underlying,
            expiry=expiry,
            strike=result["strike"],
            option_type=result["option_type"],
            ltp_at_signal=result["approximate_ltp"],
            target1=result["target1"],
            target2=result["target2"],
            stop_loss=result["stop_loss"],
            exit_condition=result.get("exit_condition"),
            rr_ratio=result.get("rr_ratio", position["rr_ratio"]),
            confidence=result["confidence"],
            valid_until=valid_until,
            signal_basis=result.get("signal_basis", []),
            market_conditions=data,
            gates_passed=result.get("gates_passed", {}),
            status="OPEN",
        )
        session.add(signal)
        await session.commit()
        await session.refresh(signal)

        users_result = await session.execute(
            select(User).where(User.is_active == True)
        )
        users = users_result.scalars().all()

    from bot.trade_handler import handle_new_signal
    await handle_new_signal(signal.__dict__.copy(), users)

    await manager.broadcast_signal(result)
    logger.info(f"[{underlying}] Signal generated: {result['signal_type']} {result['strike']} {result['option_type']}")
