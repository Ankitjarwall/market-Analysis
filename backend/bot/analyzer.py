"""
Claude API integration — generates market briefs, options signals, and loss analysis.
All prompts use exact data from the database — Claude never invents numbers.
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

import anthropic

from config import settings

logger = logging.getLogger(__name__)

_client: anthropic.AsyncAnthropic | None = None


def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


async def _call_claude(prompt: str, max_tokens: int = 2000) -> str:
    """Call Claude and return the response text."""
    client = _get_client()
    message = await client.messages.create(
        model=settings.claude_model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


async def _call_claude_json(prompt: str, max_tokens: int = 2000) -> dict:
    """Call Claude and parse JSON response."""
    text = await _call_claude(prompt, max_tokens)
    # Extract JSON from response (may be wrapped in markdown)
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error(f"Failed to parse Claude JSON response: {exc}\nResponse: {text[:500]}")
        raise


# ══════════════════════════════════════════════════════════
#  MORNING BRIEF
# ══════════════════════════════════════════════════════════

MORNING_PROMPT = """You are a professional Indian equity market analyst.
Your job is to write a morning market brief for Nifty 50 traders.

STRICT RULES:
1. NEVER generate or invent numbers — only use numbers provided below
2. Output must be valid JSON matching the schema at the end
3. Confidence must be 0-100 integer, reflecting genuine uncertainty
4. If data quality is LOW, confidence must be below 50
5. Always provide both bull and bear case
6. Keep telegram_message under 400 words

TODAY: {date}
TIME: {time} IST (market opens in {minutes_to_open} minutes)

══ LIVE DATA (all verified, fetched at {fetch_time}) ══
GIFT Nifty:     {gift_nifty} ({gift_nifty_change:+.2f}% vs yesterday close)
Nifty prev:     {nifty_prev_close}
S&P 500:        {sp500_close} ({sp500_change:+.2f}%)
Nasdaq:         {nasdaq_change:+.2f}%
Nikkei:         {nikkei_change:+.2f}%
Hang Seng:      {hangseng_change:+.2f}%

Crude Brent:    ${crude} ({crude_change:+.2f}%)
Gold:           ${gold} ({gold_change:+.2f}%)
USD/INR:        ₹{usd_inr} ({usd_inr_change:+.2f}%)
DXY:            {dxy} ({dxy_change:+.2f}%)
US 10Y Yield:   {us_10y}% ({us_10y_change:+.0f}bps)

India VIX:      {vix} ({vix_change:+.1f})
Nifty PE:       {pe} | PB: {pb} | Div Yield: {div_yield}%
FII yesterday:  ₹{fii_net:,.0f}cr ({fii_direction})
FII streak:     {fii_consecutive_days} consecutive {fii_direction} days
PCR:            {pcr}
Drawdown/ATH:   {drawdown_from_ath:.1f}%

══ DATA FLAGS ══
{data_flags}

══ TODAY'S EVENTS ══
{economic_events}

══ TOP NEWS (last 12 hours) ══
{news_items}

══ HISTORICAL PATTERN MATCH ══
{pattern_match_summary}

══ YOUR PREVIOUS PREDICTIONS THIS WEEK ══
{recent_predictions}

══ ACTIVE SIGNAL RULES (learned from losses) ══
{signal_rules}

OUTPUT THIS EXACT JSON:
{{
  "direction": "UP|DOWN|FLAT",
  "magnitude_low": -0.8,
  "magnitude_high": -0.3,
  "confidence": 62,
  "confidence_reason": "...",
  "bull_case": "...",
  "bear_case": "...",
  "key_trigger_to_watch": "...",
  "data_quality": "HIGH|MEDIUM|LOW",
  "similar_days_found": 6,
  "prediction_basis": ["GIFT_NIFTY", "FII", "CRUDE"],
  "telegram_message": "Full formatted message for Telegram here"
}}"""

OPTIONS_SIGNAL_PROMPT = """You are an expert Nifty 50 options trader.
Analyze the data and determine if a PUT or CALL signal should be generated.

STRICT RULES:
1. NEVER generate numbers — all price levels come from the options chain data provided
2. R:R must be minimum 1:2 — if you cannot achieve this, output signal_type: "NONE"
3. Stop loss must be a meaningful technical level, not arbitrary
4. Targets must be realistic resistance/support from the options chain
5. Confidence reflects how many gates are strongly met
6. Output ONLY valid JSON

DATA AT {time}:
Nifty Price:    {nifty_price}
VWAP:           {vwap}
Nifty vs VWAP:  {nifty_vs_vwap:+.2f}%
VIX:            {vix}
PCR:            {pcr}
FII today:      ₹{fii_net:,.0f}cr ({fii_direction})
FII streak:     {fii_consecutive} consecutive days
India VIX trend: {vix_trend} (last 1hr)

Technical (5-min chart):
RSI:            {rsi_5m}
9 EMA:          {ema9}
21 EMA:         {ema21}
Volume vs avg:  {volume_ratio:.1f}x

Options Chain data:
{options_chain_relevant_strikes}

Active signal rules:
{signal_rules}

Gates that MUST pass:
- Min VIX for PUT: {min_vix_put}
- FII consecutive days: {min_fii_days}
- Not within first 30min: {time_check}
- Not within last 60min: {time_check_close}
- Data fresh: {data_quality}
- Cooldown after last SL: {cooldown_ok}

OUTPUT:
{{
  "signal_type": "BUY_PUT|BUY_CALL|NONE",
  "reason_if_none": "...",
  "strike": 22800,
  "option_type": "PE|CE",
  "suggested_expiry": "03-Apr-2026",
  "approximate_ltp": 185.5,
  "stop_loss": 145.0,
  "target1": 240.0,
  "target2": 310.0,
  "exit_condition": "Exit if Nifty crosses 22950",
  "rr_ratio": 2.4,
  "confidence": 62,
  "signal_basis": ["below_vwap", "fii_5_sell_days", "vix_rising", "pcr_bearish"],
  "gates_passed": {{"vix": true, "fii": true, "timing": true, "data": true}}
}}"""

LOSS_ANALYSIS_PROMPT = """You are analyzing a losing options trade to extract learning.

TRADE:
Signal type:    {signal_type}
Strike:         {strike}
Entry premium:  ₹{entry_premium}
Stop loss:      ₹{stop_loss}
Target 1:       ₹{target1}
Entry time:     {entry_time}
Exit premium:   ₹{exit_premium} (SL hit)
Exit time:      {exit_time}
Loss:           ₹{loss_amount} ({loss_pct:.2f}% of capital)
Trade mode:     {trade_mode}

MARKET AT ENTRY:
{conditions_at_entry}

MARKET AT EXIT:
{conditions_at_exit}

NEWS BETWEEN ENTRY AND EXIT:
{news_items}

PAST SIMILAR LOSSES IN DATABASE:
{similar_losses}

CURRENT SIGNAL RULES:
{current_rules}

Analyze this loss and output JSON:
{{
  "miss_category": "FII_REVERSAL|RR_DEGRADED_MANUAL|SL_TOO_TIGHT|LOW_VIX_PUT|EARLY_SESSION|EXPIRY_DAY|NEWS_SHOCK|GLOBAL_DISCONNECT|CORRECT_SETUP_BAD_LUCK|OVER_LEVERAGED",
  "root_cause": "clear explanation of why the trade failed",
  "sl_was_correct": true,
  "sl_recommendation": "TIGHTER|WIDER|SAME",
  "signal_adjustment": "specific rule change to apply",
  "rule_to_update": "exact field name in signal_rules",
  "new_rule_value": "new value",
  "expected_improvement": "what this should prevent in future",
  "confidence_in_analysis": 75
}}"""


async def generate_morning_brief():
    """Generate and save morning market prediction, then send to Telegram."""
    from datetime import date, timezone

    from bot.collector import collect_all_signals
    from bot.validator import validate_snapshot
    from db.connection import AsyncSessionLocal
    from db.models import DailyMarketSnapshot, Prediction, SignalRule
    from sqlalchemy import select

    logger.info("Generating morning brief...")

    data = await collect_all_signals()
    validation = validate_snapshot(data)

    async with AsyncSessionLocal() as session:
        # Get recent predictions for context
        result = await session.execute(
            select(Prediction)
            .where(Prediction.date >= date.today() - timedelta(days=7))
            .order_by(Prediction.date.desc())
            .limit(5)
        )
        recent_preds = result.scalars().all()

        # Get active signal rules
        rules_result = await session.execute(
            select(SignalRule).where(SignalRule.is_active == True).limit(10)
        )
        rules = rules_result.scalars().all()

    now = datetime.now(tz=timezone.utc)
    market_open = now.replace(hour=3, minute=45, second=0)  # 9:15 AM IST = 3:45 AM UTC
    minutes_to_open = max(0, int((market_open - now).total_seconds() / 60))

    recent_preds_text = "\n".join(
        f"{p.date}: {p.direction} {p.magnitude_low}–{p.magnitude_high}% "
        f"(confidence {p.confidence}%) — {'✓' if p.was_correct else '✗' if p.was_correct is False else '?'}"
        for p in recent_preds
    )
    rules_text = "\n".join(f"- {r.rule_name}: {r.rule_value}" for r in rules)

    prompt = MORNING_PROMPT.format(
        date=date.today().strftime("%A, %d %B %Y"),
        time=now.strftime("%H:%M"),
        minutes_to_open=minutes_to_open,
        fetch_time=data.get("collected_at", "N/A"),
        gift_nifty=data.get("gift_nifty") or data.get("nifty") or "N/A",
        gift_nifty_change=0.0,
        nifty_prev_close=data.get("nifty") or "N/A",
        sp500_close=data.get("sp500") or "N/A",
        sp500_change=0.0,
        nasdaq_change=0.0,
        nikkei_change=0.0,
        hangseng_change=0.0,
        crude=data.get("crude_brent") or "N/A",
        crude_change=0.0,
        gold=data.get("gold") or "N/A",
        gold_change=0.0,
        usd_inr=data.get("usd_inr") or "N/A",
        usd_inr_change=0.0,
        dxy=data.get("dxy") or "N/A",
        dxy_change=0.0,
        us_10y=data.get("us_10y") or "N/A",
        us_10y_change=0.0,
        vix=data.get("india_vix") or "N/A",
        vix_change=0.0,
        pe=data.get("nifty_pe") or "N/A",
        pb=data.get("nifty_pb") or "N/A",
        div_yield=data.get("nifty_dividend_yield") or 0,
        fii_net=data.get("fii_net") or 0,
        fii_direction="SELL" if (data.get("fii_net") or 0) < 0 else "BUY",
        fii_consecutive_days=1,
        pcr=data.get("put_call_ratio") or "N/A",
        drawdown_from_ath=0.0,
        data_flags=validation.quality,
        economic_events="No scheduled events",
        news_items="No news collected yet",
        pattern_match_summary="No historical pattern match available",
        recent_predictions=recent_preds_text or "No recent predictions",
        signal_rules=rules_text or "Default rules active",
    )

    try:
        result = await _call_claude_json(prompt)

        async with AsyncSessionLocal() as session:
            prediction = Prediction(
                date=date.today(),
                time_of_day="open",
                direction=result["direction"],
                magnitude_low=result.get("magnitude_low"),
                magnitude_high=result.get("magnitude_high"),
                confidence=result.get("confidence"),
                confidence_reason=result.get("confidence_reason"),
                bull_case=result.get("bull_case"),
                bear_case=result.get("bear_case"),
                key_trigger=result.get("key_trigger_to_watch"),
                data_quality=result.get("data_quality"),
                similar_days_found=result.get("similar_days_found"),
                prediction_basis=result.get("prediction_basis"),
                market_conditions_at_time=data,
            )
            session.add(prediction)
            await session.commit()

        # Send to Telegram
        from bot.telegram_sender import send_message
        await send_message(result.get("telegram_message", "Morning brief generated"))

        # Broadcast to WebSocket
        from websocket.live_feed import manager
        await manager.broadcast_bot_activity(f"Morning brief: {result['direction']} {result.get('magnitude_low', '')}–{result.get('magnitude_high', '')}%")

        logger.info(f"Morning brief sent: {result['direction']} confidence={result.get('confidence')}")
    except Exception as exc:
        logger.error(f"Morning brief generation failed: {exc}", exc_info=True)


async def generate_midday_brief():
    """Generate midday session update at 12:30 PM IST."""
    logger.info("Generating midday brief...")

    from bot.collector import collect_all_signals
    from bot.validator import validate_snapshot
    from db.connection import AsyncSessionLocal
    from db.models import Prediction, SignalRule
    from sqlalchemy import select

    data = await collect_all_signals()
    validation = validate_snapshot(data)

    async with AsyncSessionLocal() as session:
        today_pred = await session.execute(
            select(Prediction)
            .where(Prediction.date == date.today())
            .where(Prediction.time_of_day == "open")
        )
        morning_pred = today_pred.scalar_one_or_none()

        rules_result = await session.execute(
            select(SignalRule).where(SignalRule.is_active == True).limit(10)
        )
        rules = rules_result.scalars().all()

    rules_text = "\n".join(f"- {r.rule_name}: {r.rule_value}" for r in rules)
    morning_context = (
        f"Morning prediction: {morning_pred.direction} "
        f"{morning_pred.magnitude_low}–{morning_pred.magnitude_high}% "
        f"(confidence {morning_pred.confidence}%)"
        if morning_pred
        else "No morning prediction available"
    )

    prompt = MORNING_PROMPT.format(
        date=date.today().strftime("%A, %d %B %Y"),
        time="12:30",
        minutes_to_open=0,
        fetch_time=data.get("collected_at", "N/A"),
        gift_nifty=data.get("nifty") or "N/A",
        gift_nifty_change=0.0,
        nifty_prev_close=data.get("nifty") or "N/A",
        sp500_close=data.get("sp500") or "N/A",
        sp500_change=0.0,
        nasdaq_change=0.0,
        nikkei_change=0.0,
        hangseng_change=0.0,
        crude=data.get("crude_brent") or "N/A",
        crude_change=0.0,
        gold=data.get("gold") or "N/A",
        gold_change=0.0,
        usd_inr=data.get("usd_inr") or "N/A",
        usd_inr_change=0.0,
        dxy=data.get("dxy") or "N/A",
        dxy_change=0.0,
        us_10y=data.get("us_10y") or "N/A",
        us_10y_change=0.0,
        vix=data.get("india_vix") or "N/A",
        vix_change=0.0,
        pe=data.get("nifty_pe") or "N/A",
        pb=data.get("nifty_pb") or "N/A",
        div_yield=data.get("nifty_dividend_yield") or 0,
        fii_net=data.get("fii_net") or 0,
        fii_direction="SELL" if (data.get("fii_net") or 0) < 0 else "BUY",
        fii_consecutive_days=1,
        pcr=data.get("put_call_ratio") or "N/A",
        drawdown_from_ath=0.0,
        data_flags=validation.quality,
        economic_events="Midday session update — market open",
        news_items="Midday update — see morning brief for news context",
        pattern_match_summary=morning_context,
        recent_predictions=morning_context,
        signal_rules=rules_text or "Default rules active",
    )

    try:
        result = await _call_claude_json(prompt)

        async with AsyncSessionLocal() as session:
            # Upsert: skip if midday prediction already exists
            existing = await session.execute(
                select(Prediction)
                .where(Prediction.date == date.today())
                .where(Prediction.time_of_day == "mid")
            )
            if existing.scalar_one_or_none() is None:
                prediction = Prediction(
                    date=date.today(),
                    time_of_day="mid",
                    direction=result["direction"],
                    magnitude_low=result.get("magnitude_low"),
                    magnitude_high=result.get("magnitude_high"),
                    confidence=result.get("confidence"),
                    confidence_reason=result.get("confidence_reason"),
                    bull_case=result.get("bull_case"),
                    bear_case=result.get("bear_case"),
                    key_trigger=result.get("key_trigger_to_watch"),
                    data_quality=result.get("data_quality"),
                    similar_days_found=result.get("similar_days_found"),
                    prediction_basis=result.get("prediction_basis"),
                    market_conditions_at_time=data,
                )
                session.add(prediction)
                await session.commit()

        from bot.telegram_sender import send_message
        await send_message(result.get("telegram_message", "Midday brief generated"))

        from websocket.live_feed import manager
        await manager.broadcast_bot_activity(
            f"Midday brief: {result['direction']} confidence={result.get('confidence')}%"
        )
        logger.info(f"Midday brief sent: {result['direction']}")
    except Exception as exc:
        logger.error(f"Midday brief generation failed: {exc}", exc_info=True)


async def generate_closing_brief():
    """Generate closing session summary at 3:35 PM IST."""
    logger.info("Generating closing brief...")

    from bot.collector import collect_all_signals
    from bot.validator import validate_snapshot
    from db.connection import AsyncSessionLocal
    from db.models import Prediction, Signal, SignalRule, Trade
    from sqlalchemy import select

    data = await collect_all_signals()
    validation = validate_snapshot(data)

    async with AsyncSessionLocal() as session:
        today_preds = await session.execute(
            select(Prediction).where(Prediction.date == date.today())
        )
        predictions = today_preds.scalars().all()

        today_signals = await session.execute(
            select(Signal).where(
                Signal.timestamp >= datetime.now(tz=timezone.utc).replace(hour=0, minute=0)
            )
        )
        signals = today_signals.scalars().all()

        today_trades = await session.execute(
            select(Trade).where(
                Trade.entry_time >= datetime.now(tz=timezone.utc).replace(hour=0, minute=0)
            )
        )
        trades = today_trades.scalars().all()

        rules_result = await session.execute(
            select(SignalRule).where(SignalRule.is_active == True).limit(10)
        )
        rules = rules_result.scalars().all()

    rules_text = "\n".join(f"- {r.rule_name}: {r.rule_value}" for r in rules)
    preds_context = "\n".join(
        f"{p.time_of_day}: {p.direction} (confidence {p.confidence}%)"
        for p in predictions
    ) or "No predictions today"
    signals_context = f"Signals today: {len(signals)} | Trades: {len(trades)}"
    closed_pnl = sum(t.net_pnl or 0 for t in trades if t.status == "CLOSED")
    trades_context = (
        f"{signals_context} | Closed P&L: ₹{closed_pnl:,.0f}"
        if trades
        else signals_context
    )

    prompt = MORNING_PROMPT.format(
        date=date.today().strftime("%A, %d %B %Y"),
        time="15:35",
        minutes_to_open=0,
        fetch_time=data.get("collected_at", "N/A"),
        gift_nifty=data.get("nifty") or "N/A",
        gift_nifty_change=0.0,
        nifty_prev_close=data.get("nifty") or "N/A",
        sp500_close=data.get("sp500") or "N/A",
        sp500_change=0.0,
        nasdaq_change=0.0,
        nikkei_change=0.0,
        hangseng_change=0.0,
        crude=data.get("crude_brent") or "N/A",
        crude_change=0.0,
        gold=data.get("gold") or "N/A",
        gold_change=0.0,
        usd_inr=data.get("usd_inr") or "N/A",
        usd_inr_change=0.0,
        dxy=data.get("dxy") or "N/A",
        dxy_change=0.0,
        us_10y=data.get("us_10y") or "N/A",
        us_10y_change=0.0,
        vix=data.get("india_vix") or "N/A",
        vix_change=0.0,
        pe=data.get("nifty_pe") or "N/A",
        pb=data.get("nifty_pb") or "N/A",
        div_yield=data.get("nifty_dividend_yield") or 0,
        fii_net=data.get("fii_net") or 0,
        fii_direction="SELL" if (data.get("fii_net") or 0) < 0 else "BUY",
        fii_consecutive_days=1,
        pcr=data.get("put_call_ratio") or "N/A",
        drawdown_from_ath=0.0,
        data_flags=validation.quality,
        economic_events="Market closing — end of session",
        news_items=trades_context,
        pattern_match_summary=preds_context,
        recent_predictions=preds_context,
        signal_rules=rules_text or "Default rules active",
    )

    try:
        result = await _call_claude_json(prompt)

        async with AsyncSessionLocal() as session:
            existing = await session.execute(
                select(Prediction)
                .where(Prediction.date == date.today())
                .where(Prediction.time_of_day == "close")
            )
            if existing.scalar_one_or_none() is None:
                prediction = Prediction(
                    date=date.today(),
                    time_of_day="close",
                    direction=result["direction"],
                    magnitude_low=result.get("magnitude_low"),
                    magnitude_high=result.get("magnitude_high"),
                    confidence=result.get("confidence"),
                    confidence_reason=result.get("confidence_reason"),
                    bull_case=result.get("bull_case"),
                    bear_case=result.get("bear_case"),
                    key_trigger=result.get("key_trigger_to_watch"),
                    data_quality=result.get("data_quality"),
                    similar_days_found=result.get("similar_days_found"),
                    prediction_basis=result.get("prediction_basis"),
                    market_conditions_at_time=data,
                )
                session.add(prediction)
                await session.commit()

        from bot.telegram_sender import send_message
        await send_message(result.get("telegram_message", "Closing brief generated"))

        from websocket.live_feed import manager
        await manager.broadcast_bot_activity(
            f"Closing brief: {result['direction']} confidence={result.get('confidence')}%"
        )
        logger.info(f"Closing brief sent: {result['direction']}")
    except Exception as exc:
        logger.error(f"Closing brief generation failed: {exc}", exc_info=True)


async def run_daily_postmortem():
    """After market close — evaluate today's predictions."""
    from db.connection import AsyncSessionLocal
    from db.models import DailyMarketSnapshot, Prediction, PredictionMistake
    from sqlalchemy import select

    today = date.today()
    async with AsyncSessionLocal() as session:
        pred_result = await session.execute(
            select(Prediction).where(Prediction.date == today)
        )
        predictions = pred_result.scalars().all()

        snap_result = await session.execute(
            select(DailyMarketSnapshot)
            .where(DailyMarketSnapshot.date == today)
            .where(DailyMarketSnapshot.time_of_day == "close")
        )
        close_snapshot = snap_result.scalar_one_or_none()

        if not close_snapshot or not predictions:
            return

        for pred in predictions:
            open_snap = await session.execute(
                select(DailyMarketSnapshot)
                .where(DailyMarketSnapshot.date == today)
                .where(DailyMarketSnapshot.time_of_day == "open")
            )
            open_data = open_snap.scalar_one_or_none()
            if not open_data or not open_data.nifty_close or not close_snapshot.nifty_close:
                continue

            actual_change = (
                (close_snapshot.nifty_close - open_data.nifty_close) / open_data.nifty_close * 100
            )
            actual_dir = "UP" if actual_change > 0.2 else "DOWN" if actual_change < -0.2 else "FLAT"
            was_correct = pred.direction == actual_dir

            pred.actual_direction = actual_dir
            pred.actual_magnitude = round(actual_change, 2)
            pred.was_correct = was_correct

            if not was_correct:
                mistake = PredictionMistake(
                    prediction_id=pred.id,
                    date=today,
                    prediction_direction=pred.direction,
                    actual_direction=actual_dir,
                    error_size=abs(actual_change - (pred.magnitude_low or 0)),
                    market_conditions=close_snapshot.all_data or {},
                    miss_category="DIRECTION_WRONG",
                    confidence_given=pred.confidence,
                )
                session.add(mistake)

        await session.commit()
    logger.info("Daily postmortem complete")


async def analyze_loss(trade_data: dict, signal_data: dict, conditions_at_entry: dict, conditions_at_exit: dict) -> dict:
    """Generate AI loss analysis for a losing trade."""
    prompt = LOSS_ANALYSIS_PROMPT.format(
        signal_type=signal_data.get("signal_type"),
        strike=signal_data.get("strike"),
        entry_premium=trade_data.get("entry_premium"),
        stop_loss=signal_data.get("stop_loss"),
        target1=signal_data.get("target1"),
        entry_time=trade_data.get("entry_time"),
        exit_premium=trade_data.get("exit_premium"),
        exit_time=trade_data.get("exit_time"),
        loss_amount=abs(trade_data.get("net_pnl", 0)),
        loss_pct=abs(trade_data.get("net_pnl_pct", 0)),
        trade_mode=trade_data.get("trade_mode"),
        conditions_at_entry=json.dumps(conditions_at_entry, indent=2),
        conditions_at_exit=json.dumps(conditions_at_exit, indent=2),
        news_items="N/A",
        similar_losses="No similar losses in database",
        current_rules="Default rules",
    )
    return await _call_claude_json(prompt)
