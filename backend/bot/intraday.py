"""
Intraday technical analysis — RSI, EMA, volume ratio.
Data sourced from AngelOne getCandleData REST API.
No yfinance. No NSE web scraping.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# AngelOne instrument tokens for index candle data
ANGEL_TOKENS = {
    "NIFTY": "26000",
    "BANKNIFTY": "26009",
}


async def get_intraday_technicals(
    symbol: str = "NIFTY", interval: str = "FIVE_MINUTE"
) -> dict[str, Any]:
    """
    Compute intraday technical indicators using AngelOne getCandleData.
    Returns RSI(14), EMA(9), EMA(21), volume_ratio.
    symbol: "NIFTY" or "BANKNIFTY"
    """
    from bot.angel_feed import get_live_price

    token = ANGEL_TOKENS.get(symbol.upper())
    if not token:
        logger.warning(f"Unknown symbol for intraday technicals: {symbol}")
        return {}

    candles = await _fetch_candles(token, interval, days=5)
    if not candles or len(candles) < 22:
        # Fall back to just returning live price from cache
        field = "nifty" if symbol == "NIFTY" else "banknifty"
        ltp = get_live_price(field)
        if ltp:
            return {"symbol": symbol, "current_price": ltp, "source": "cache_only"}
        return {}

    closes = [c[4] for c in candles]   # index 4 = close
    volumes = [c[5] for c in candles]  # index 5 = volume

    rsi = _compute_rsi(closes, period=14)
    ema9 = _compute_ema(closes, span=9)
    ema21 = _compute_ema(closes, span=21)

    recent_vols = volumes[-20:] if len(volumes) >= 20 else volumes
    avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 1
    vol_ratio = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0

    current_price = closes[-1]
    return {
        "symbol": symbol,
        "interval": interval,
        "current_price": round(current_price, 2),
        "rsi_14": round(rsi, 2),
        "ema9": round(ema9, 2),
        "ema21": round(ema21, 2),
        "volume_ratio": vol_ratio,
        "above_ema9": current_price > ema9,
        "above_ema21": current_price > ema21,
        "ema9_above_ema21": ema9 > ema21,
    }


async def _fetch_candles(token: str, interval: str, days: int = 5) -> list:
    """Fetch OHLCV candles from AngelOne getCandleData REST API."""
    api_key = os.environ.get("ANGELONE_API_KEY", "")
    client_code = os.environ.get("ANGELONE_CLIENT_ID", "")
    password = os.environ.get("ANGELONE_PASSWORD", "")
    totp_secret = os.environ.get("ANGELONE_TOTP_SECRET", "")

    if not all([api_key, client_code, password, totp_secret]):
        return []

    now = datetime.now(tz=IST)
    from_dt = now - timedelta(days=days)
    params = {
        "exchange": "NSE",
        "symboltoken": token,
        "interval": interval,
        "fromdate": from_dt.strftime("%Y-%m-%d %H:%M"),
        "todate": now.strftime("%Y-%m-%d %H:%M"),
    }

    def _fetch():
        import pyotp
        from SmartApi import SmartConnect
        totp = pyotp.TOTP(totp_secret).now()
        api = SmartConnect(api_key=api_key)
        session = api.generateSession(client_code, password, totp)
        if not session or not session.get("status"):
            logger.warning("AngelOne auth failed in _fetch_candles")
            return []
        result = api.getCandleData(params)
        if result and result.get("status") and result.get("data"):
            return result["data"]
        return []

    try:
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(loop.run_in_executor(None, _fetch), timeout=15)
    except Exception as exc:
        logger.warning(f"AngelOne getCandleData failed (token={token}): {exc}")
        return []


def _compute_rsi(closes: list, period: int = 14) -> float:
    """Wilder's RSI — pure Python, no numpy."""
    if len(closes) < period + 1:
        return 50.0

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1 + rs))


def _compute_ema(closes: list, span: int) -> float:
    """Exponential moving average — pure Python."""
    if not closes:
        return 0.0
    k = 2.0 / (span + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = price * k + ema * (1 - k)
    return ema


async def get_options_chain_summary(
    symbol: str = "NIFTY", spot_price: float = 22000
) -> dict[str, Any]:
    """
    Return options chain summary using AngelOne live data.
    ATM strike derived from live spot price.
    """
    from bot.angel_feed import get_live_price

    live_spot = get_live_price("nifty" if symbol == "NIFTY" else "banknifty")
    if live_spot:
        spot_price = live_spot

    strike_interval = 100 if symbol == "BANKNIFTY" else 50
    atm = round(spot_price / strike_interval) * strike_interval

    return {
        "atm_strike": float(atm),
        "spot_price": spot_price,
        "max_pain": float(atm),
        "chain_around_atm": [],
    }
