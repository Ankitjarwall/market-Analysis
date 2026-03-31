"""
Market data API endpoints.
GET /api/market/live          — all 47 signals (use WebSocket for real-time)
GET /api/market/snapshot/{date}/{time}
GET /api/market/historical/{symbol}
GET /api/market/nifty-pe
GET /api/market/fii-dii
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth.middleware import get_current_user
from db.connection import get_db
from db.models import DailyMarketSnapshot, User

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/live")
async def get_live_market(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return latest cached market snapshot. For real-time, use WebSocket /ws/market."""
    result = await db.execute(
        select(DailyMarketSnapshot)
        .order_by(DailyMarketSnapshot.created_at.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        return {"status": "no_data", "message": "No market data collected yet"}
    return {
        "status": "ok",
        "timestamp": snapshot.created_at,
        "data": snapshot.all_data or {},
        "fresh_signals_count": snapshot.fresh_signals_count,
    }


@router.get("/snapshot/{snapshot_date}/{time_of_day}")
async def get_snapshot(
    snapshot_date: date,
    time_of_day: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if time_of_day not in ("open", "mid", "close"):
        raise HTTPException(status_code=400, detail="time_of_day must be open|mid|close")

    result = await db.execute(
        select(DailyMarketSnapshot).where(
            DailyMarketSnapshot.date == snapshot_date,
            DailyMarketSnapshot.time_of_day == time_of_day,
        )
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return snapshot


@router.get("/historical/{symbol}")
async def get_historical(
    symbol: str,
    days: int = Query(default=365, ge=1, le=365 * 30),
    current_user: User = Depends(get_current_user),
):
    """Fetch historical OHLCV data for a symbol via yfinance."""
    try:
        import yfinance as yf
        from datetime import datetime, timedelta
        end = datetime.now()
        start = end - timedelta(days=days)
        ticker = yf.Ticker(symbol)
        hist = ticker.history(start=start, end=end, interval="1d")
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"No data for symbol {symbol}")
        records = []
        for dt, row in hist.iterrows():
            records.append({
                "date": dt.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return {"symbol": symbol, "days": days, "data": records}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/nifty-pe")
async def get_nifty_pe(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(DailyMarketSnapshot)
        .where(DailyMarketSnapshot.nifty_pe.isnot(None))
        .order_by(DailyMarketSnapshot.created_at.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        return {"pe": None, "pb": None, "dividend_yield": None}
    return {
        "pe": snapshot.nifty_pe,
        "pb": snapshot.nifty_pb,
        "dividend_yield": snapshot.nifty_dividend_yield,
        "as_of": snapshot.created_at,
    }


@router.get("/fii-dii")
async def get_fii_dii(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(
            DailyMarketSnapshot.date,
            DailyMarketSnapshot.fii_net,
            DailyMarketSnapshot.dii_net,
        )
        .where(DailyMarketSnapshot.time_of_day == "close")
        .order_by(DailyMarketSnapshot.date.desc())
        .limit(days)
    )
    rows = result.all()
    return {
        "data": [
            {"date": str(r.date), "fii_net": r.fii_net, "dii_net": r.dii_net}
            for r in rows
        ]
    }


@router.get("/status")
async def get_market_status(current_user: User = Depends(get_current_user)):
    """Return whether NSE is currently open.
    Combines two signals:
      1. Time-based: is it 9:15–15:30 IST on a weekday?
      2. Data freshness: did yfinance return a candle < 20 min old?
    Using both handles market holidays (yfinance returns stale data on holidays).
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from bot.scheduler import _latest_market_data

    now = datetime.now(tz=ZoneInfo("Asia/Kolkata"))
    weekday = now.weekday()  # 0=Mon, 6=Sun
    mins = now.hour * 60 + now.minute
    # NSE regular hours: 9:15 AM – 3:30 PM IST, Mon–Fri
    time_based_open = (0 <= weekday <= 4) and (555 <= mins <= 930)
    # Freshness signal from the fast-tick job (False on holidays / outside hours)
    nse_data_fresh = bool(_latest_market_data.get("nse_market_active", False))
    # Both must be true: within scheduled hours AND data is actually fresh
    is_nse_open = time_based_open and nse_data_fresh
    return {
        "is_nse_open": is_nse_open,
        "ist_time": now.isoformat(),
        "ist_hour": now.hour,
        "ist_minute": now.minute,
        "weekday": weekday,
        "time_based_open": time_based_open,
        "nse_data_fresh": nse_data_fresh,
    }
