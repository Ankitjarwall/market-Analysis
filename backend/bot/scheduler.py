"""
APScheduler — all timed jobs for data collection, analysis, and reporting.
All Indian market prices come from AngelOne SmartStream (push).
No yfinance polling. No NSE scraping.
"""

import asyncio
import logging
import math
from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
_scheduler: AsyncIOScheduler | None = None

# In-memory cache of the latest market data for fast broadcast
_latest_market_data: dict = {}


async def start_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone=IST)

    # ── Pre-market (9:00 AM IST weekdays) ──
    _scheduler.add_job(
        job_morning_brief, CronTrigger(hour=9, minute=0, day_of_week="mon-fri", timezone=IST),
        id="morning_brief", replace_existing=True,
    )

    # ── Live data every 60s, 9:00–15:30 IST ──
    # Fast prices come from job_fast_tick_prices every 10s.
    # This job calls slow NSE APIs (FII, PCR, PE) that take 30–60s — 20s interval
    # caused "max instances reached" spam. 60s is the minimum safe interval.
    _scheduler.add_job(
        job_collect_live_data,
        CronTrigger(minute="*/1", hour="9-15", day_of_week="mon-fri", timezone=IST),
        id="collect_live", replace_existing=True,
        misfire_grace_time=20,
        coalesce=True,
        max_instances=1,
    )

    # ── Options signal checks: Nifty and BankNifty on alternating 5-min windows ──
    # Nifty runs on even minutes (0,10,20,30,40,50), BN on odd-offset (5,15,25,35,45,55).
    # They never overlap so daily signal count is shared across both underlyings.
    _scheduler.add_job(
        job_check_options_signals,
        CronTrigger(minute="0,10,20,30,40,50", hour="9-14", day_of_week="mon-fri", timezone=IST),
        id="options_signals_nifty", replace_existing=True,
    )
    _scheduler.add_job(
        job_check_banknifty_signals,
        CronTrigger(minute="5,15,25,35,45,55", hour="9-14", day_of_week="mon-fri", timezone=IST),
        id="options_signals_banknifty", replace_existing=True,
    )

    # ── Midday brief (12:30 IST) ──
    _scheduler.add_job(
        job_midday_brief,
        CronTrigger(hour=12, minute=30, day_of_week="mon-fri", timezone=IST),
        id="midday_brief", replace_existing=True,
    )

    # ── End of day ──
    _scheduler.add_job(
        job_closing_brief,
        CronTrigger(hour=15, minute=35, day_of_week="mon-fri", timezone=IST),
        id="closing_brief", replace_existing=True,
    )
    _scheduler.add_job(
        job_daily_postmortem,
        CronTrigger(hour=15, minute=45, day_of_week="mon-fri", timezone=IST),
        id="daily_postmortem", replace_existing=True,
    )
    _scheduler.add_job(
        job_update_historical,
        CronTrigger(hour=16, minute=0, day_of_week="mon-fri", timezone=IST),
        id="update_historical", replace_existing=True,
    )

    # ── Always-running tasks ──
    _scheduler.add_job(
        job_watchdog_check, IntervalTrigger(seconds=30),
        id="watchdog", replace_existing=True,
        misfire_grace_time=15,
    )
    _scheduler.add_job(
        job_broadcast_live, IntervalTrigger(seconds=5),
        id="broadcast_live", replace_existing=True,
        misfire_grace_time=10,  # don't warn if up to 10s late
    )

    # ── Weekly ──
    _scheduler.add_job(
        job_weekly_prediction_review,
        CronTrigger(day_of_week="sun", hour=9, minute=0, timezone=IST),
        id="weekly_pred_review", replace_existing=True,
    )
    _scheduler.add_job(
        job_weekly_options_review,
        CronTrigger(day_of_week="sun", hour=9, minute=30, timezone=IST),
        id="weekly_options_review", replace_existing=True,
    )

    # ── Monthly ──
    _scheduler.add_job(
        job_monthly_calibration,
        CronTrigger(day=1, hour=8, minute=0, timezone=IST),
        id="monthly_calibration", replace_existing=True,
    )

    # ── Quarterly ──
    _scheduler.add_job(
        job_quarterly_review,
        CronTrigger(month="1,4,7,10", day=1, hour=8, minute=0, timezone=IST),
        id="quarterly_review", replace_existing=True,
    )

    _scheduler.start()
    logger.info("Scheduler started with all jobs")

    # Start AngelOne SmartStream feed — all Indian market prices via WebSocket push
    asyncio.create_task(_start_angel_feed())


async def _start_angel_feed():
    """Start AngelOne SmartStream; on each tick, merge into cache and broadcast."""
    from bot.angel_feed import start_feed

    async def _on_tick(field: str, price: float, _raw):
        """Called from angel_feed on every price tick — update cache + broadcast."""
        global _latest_market_data
        if not field:
            return
        merged = dict(_latest_market_data) if _latest_market_data else {}
        merged[field] = price
        merged["nse_market_active"] = True
        _latest_market_data = merged
        # Immediate broadcast on every tick for <1s latency
        from websocket.live_feed import manager
        await manager.broadcast_market_update(merged)

    started = await start_feed(on_tick=_on_tick)
    if started:
        logger.info("AngelOne SmartStream feed started — Indian prices via WebSocket push")
    else:
        logger.warning("AngelOne not configured — set ANGELONE_API_KEY in .env to enable live data")


async def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")
    try:
        from bot.angel_feed import stop_feed
        stop_feed()
    except Exception:
        pass


# ── Job implementations ──────────────────────────────────────────────────────


async def job_collect_live_data():
    """Collect all 47 market signals and save snapshot."""
    try:
        from bot.collector import collect_all_signals, calculate_vwap
        from db.connection import AsyncSessionLocal
        from db.models import DailyMarketSnapshot
        from datetime import date
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        data = await collect_all_signals()
        vwap = await calculate_vwap()
        if vwap:
            data["vwap"] = vwap

        # Sanitize NaN/Inf before storing to JSONB (PostgreSQL rejects JSON NaN)
        data = _sanitize_for_json(data)

        # Save to DB — upsert so repeated 20s runs within the same time_of_day slot don't fail
        async with AsyncSessionLocal() as session:
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            row = {
                "date": date.today(),
                "time_of_day": _get_time_of_day(),
                "nifty_close": data.get("nifty"),
                "banknifty_close": data.get("banknifty"),
                "sp500_close": data.get("sp500"),
                "nasdaq_close": data.get("nasdaq"),
                "nikkei_close": data.get("nikkei"),
                "hangseng_close": data.get("hangseng"),
                "shanghai_close": data.get("shanghai"),
                "ftse_close": data.get("ftse"),
                "dax_close": data.get("dax"),
                "crude_brent": data.get("crude_brent"),
                "crude_wti": data.get("crude_wti"),
                "gold": data.get("gold"),
                "silver": data.get("silver"),
                "natural_gas": data.get("natural_gas"),
                "copper": data.get("copper"),
                "usd_inr": data.get("usd_inr"),
                "dxy": data.get("dxy"),
                "usd_jpy": data.get("usd_jpy"),
                "us_10y_yield": data.get("us_10y"),
                "india_vix": data.get("india_vix"),
                "us_vix": data.get("us_vix"),
                "fii_net": data.get("fii_net"),
                "dii_net": data.get("dii_net"),
                "nifty_pe": data.get("nifty_pe"),
                "nifty_pb": data.get("nifty_pb"),
                "nifty_dividend_yield": data.get("nifty_dividend_yield"),
                "put_call_ratio": data.get("put_call_ratio"),
                "advance_decline_ratio": data.get("advance_decline_ratio"),
                "vwap": vwap,
                "fresh_signals_count": data.get("fresh_signals_count"),
                "all_data": data,
            }
            stmt = pg_insert(DailyMarketSnapshot).values(**row)
            update_cols = {c: stmt.excluded[c] for c in row if c not in ("date", "time_of_day")}
            stmt = stmt.on_conflict_do_update(
                index_elements=["date", "time_of_day"],
                set_=update_cols,
            )
            await session.execute(stmt)
            await session.commit()

        # Update in-memory cache and broadcast to WebSocket clients
        global _latest_market_data
        _latest_market_data = data
        from websocket.live_feed import manager
        await manager.broadcast_market_update(data)

    except Exception as exc:
        logger.error(f"job_collect_live_data error: {exc}", exc_info=True)


async def job_morning_brief():
    try:
        from bot.analyzer import generate_morning_brief
        await generate_morning_brief()
    except Exception as exc:
        logger.error(f"job_morning_brief error: {exc}", exc_info=True)


async def job_midday_brief():
    try:
        from bot.analyzer import generate_midday_brief
        await generate_midday_brief()
    except Exception as exc:
        logger.error(f"job_midday_brief error: {exc}", exc_info=True)


async def job_closing_brief():
    try:
        from bot.analyzer import generate_closing_brief
        await generate_closing_brief()
    except Exception as exc:
        logger.error(f"job_closing_brief error: {exc}", exc_info=True)


async def job_check_options_signals():
    """Check if Nifty 50 options signal conditions are met."""
    now = datetime.now(tz=IST)
    if now.hour == 9 and now.minute < 45:
        return
    if now.hour == 14 and now.minute > 30:
        return
    if now.hour >= 15:
        return

    try:
        from bot.options_analyzer import check_and_generate_signal
        await check_and_generate_signal(underlying="NIFTY50")
    except Exception as exc:
        logger.error(f"job_check_options_signals error: {exc}", exc_info=True)


async def job_check_banknifty_signals():
    """Check if Bank Nifty options signal conditions are met."""
    now = datetime.now(tz=IST)
    if now.hour == 9 and now.minute < 45:
        return
    if now.hour == 14 and now.minute > 30:
        return
    if now.hour >= 15:
        return

    try:
        from bot.options_analyzer import check_and_generate_signal
        await check_and_generate_signal(underlying="BANKNIFTY")
    except Exception as exc:
        logger.error(f"job_check_banknifty_signals error: {exc}", exc_info=True)


async def job_daily_postmortem():
    try:
        from bot.analyzer import run_daily_postmortem
        await run_daily_postmortem()
    except Exception as exc:
        logger.error(f"job_daily_postmortem error: {exc}", exc_info=True)


async def job_update_historical():
    try:
        from bot.collector import collect_all_signals
        await collect_all_signals()  # Final EOD snapshot
    except Exception as exc:
        logger.error(f"job_update_historical error: {exc}", exc_info=True)


async def job_watchdog_check():
    try:
        from healing.watchdog import run_watchdog_check
        await run_watchdog_check()
    except Exception as exc:
        logger.debug(f"Watchdog check error: {exc}")


async def job_broadcast_live():
    """Broadcast latest cached data to WebSocket clients every 2 seconds."""
    global _latest_market_data
    try:
        from websocket.live_feed import manager

        # Use in-memory cache (updated by fast_tick and collect_live)
        if _latest_market_data:
            await manager.broadcast_market_update(_latest_market_data)
            return

        # Fallback: seed cache from DB on startup before first collection
        from db.connection import AsyncSessionLocal
        from db.models import DailyMarketSnapshot
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DailyMarketSnapshot)
                .order_by(DailyMarketSnapshot.created_at.desc())
                .limit(1)
            )
            snapshot = result.scalar_one_or_none()
            if snapshot and snapshot.all_data:
                _latest_market_data = dict(snapshot.all_data)
                await manager.broadcast_market_update(_latest_market_data)
    except Exception:
        pass


async def job_weekly_prediction_review():
    try:
        from bot.learning_engine import run_weekly_prediction_review
        await run_weekly_prediction_review()
    except Exception as exc:
        logger.error(f"Weekly prediction review error: {exc}", exc_info=True)


async def job_weekly_options_review():
    try:
        from bot.learning_engine import run_weekly_options_review
        await run_weekly_options_review()
    except Exception as exc:
        logger.error(f"Weekly options review error: {exc}", exc_info=True)


async def job_monthly_calibration():
    try:
        from bot.learning_engine import run_monthly_calibration
        await run_monthly_calibration()
    except Exception as exc:
        logger.error(f"Monthly calibration error: {exc}", exc_info=True)


async def job_quarterly_review():
    try:
        from bot.learning_engine import run_quarterly_review
        await run_quarterly_review()
    except Exception as exc:
        logger.error(f"Quarterly review error: {exc}", exc_info=True)


def _sanitize_for_json(obj):
    """Recursively replace NaN/Inf floats with None so JSONB never sees them."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def _get_time_of_day() -> str:
    hour = datetime.now(tz=IST).hour
    if hour < 11:
        return "open"
    if hour < 14:
        return "mid"
    return "close"
