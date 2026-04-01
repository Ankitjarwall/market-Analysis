"""
Intraday technical analysis — RSI, EMA, volume ratio.
Primary source: AngelOne getCandleData REST API.
Fallback: yfinance 5-minute candle data (used when AngelOne not configured).

Options chain summary uses AngelOne if available, otherwise approximates
ATM/OTM prices via Black-Scholes with India VIX as the IV proxy.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from math import erf, exp, log, sqrt
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")

# AngelOne instrument tokens for index candle data
ANGEL_TOKENS = {
    "NIFTY": "26000",
    "BANKNIFTY": "26009",
}

# yfinance symbols for intraday candles
YF_SYMBOLS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}


# ── Public API ────────────────────────────────────────────────────────────────

async def get_intraday_technicals(
    symbol: str = "NIFTY", interval: str = "FIVE_MINUTE"
) -> dict[str, Any]:
    """
    Compute intraday RSI(14), EMA(9), EMA(21), volume_ratio.
    1. Try AngelOne getCandleData (requires credentials)
    2. Fall back to yfinance 5-minute data
    """
    # --- AngelOne path ---
    candles = await _fetch_candles_angel(symbol, interval, days=5)
    if candles and len(candles) >= 22:
        return _compute_technicals(candles, symbol, source="angelone")

    # --- yfinance fallback ---
    candles_yf = await _fetch_candles_yfinance(symbol, days=5)
    if candles_yf and len(candles_yf) >= 22:
        return _compute_technicals(candles_yf, symbol, source="yfinance")

    # --- bare minimum: just live price ---
    from bot.angel_feed import get_live_price
    field = "nifty" if symbol == "NIFTY" else "banknifty"
    ltp = get_live_price(field)
    if ltp:
        return {"symbol": symbol, "current_price": ltp, "source": "cache_only"}
    return {}


async def get_options_chain_summary(
    symbol: str = "NIFTY", spot_price: float = 22000
) -> dict[str, Any]:
    """
    Return options chain summary with ATM and near-strikes for Claude.
    Builds estimated LTPs via Black-Scholes + India VIX when live chain unavailable.
    """
    from bot.angel_feed import get_live_price

    field = "nifty" if symbol == "NIFTY" else "banknifty"
    live_spot = get_live_price(field)
    if live_spot:
        spot_price = live_spot
    else:
        # Try collector global cache first
        try:
            from bot.collector import _global_price_cache
            cached = _global_price_cache.get(field)
            if cached:
                spot_price = cached
        except Exception:
            pass
        # Final fallback: fetch live price from yfinance right now
        if spot_price == 22000:
            try:
                yf_sym = YF_SYMBOLS.get(symbol.upper(), "^NSEI")
                import yfinance as yf
                t = yf.Ticker(yf_sym)
                hist = t.history(period="1d", interval="1m")
                if not hist.empty:
                    spot_price = float(hist["Close"].iloc[-1])
            except Exception:
                pass

    strike_interval = 100 if symbol == "BANKNIFTY" else 50
    atm = round(spot_price / strike_interval) * strike_interval

    # Build estimated chain using Black-Scholes
    chain = _build_estimated_chain(spot_price, atm, strike_interval, symbol)

    return {
        "atm_strike": float(atm),
        "spot_price": spot_price,
        "max_pain": float(atm),
        "chain_around_atm": chain,
        "source": "bs_estimated",
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _compute_technicals(candles: list, symbol: str, source: str) -> dict[str, Any]:
    closes = [c[4] for c in candles]
    volumes = [c[5] for c in candles]
    rsi = _compute_rsi(closes)
    ema9 = _compute_ema(closes, 9)
    ema21 = _compute_ema(closes, 21)
    recent_vols = volumes[-20:] if len(volumes) >= 20 else volumes
    avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 1
    vol_ratio = round(volumes[-1] / avg_vol, 2) if avg_vol > 0 else 1.0
    cur = closes[-1]
    return {
        "symbol": symbol,
        "current_price": round(cur, 2),
        "rsi_14": round(rsi, 2),
        "ema9": round(ema9, 2),
        "ema21": round(ema21, 2),
        "volume_ratio": vol_ratio,
        "above_ema9": cur > ema9,
        "above_ema21": cur > ema21,
        "ema9_above_ema21": ema9 > ema21,
        "source": source,
    }


async def _fetch_candles_angel(symbol: str, interval: str, days: int) -> list:
    token = ANGEL_TOKENS.get(symbol.upper())
    if not token:
        return []
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
            return []
        result = api.getCandleData(params)
        if result and result.get("status") and result.get("data"):
            return result["data"]
        return []

    try:
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(loop.run_in_executor(None, _fetch), timeout=15)
    except Exception as exc:
        logger.debug(f"AngelOne getCandleData failed ({symbol}): {exc}")
        return []


async def _fetch_candles_yfinance(symbol: str, days: int = 5) -> list:
    """Fetch 5-minute OHLCV candles from yfinance. Returns list of [ts,o,h,l,c,v]."""
    yf_sym = YF_SYMBOLS.get(symbol.upper())
    if not yf_sym:
        return []

    def _fetch():
        import yfinance as yf
        ticker = yf.Ticker(yf_sym)
        hist = ticker.history(period=f"{days}d", interval="5m")
        if hist.empty:
            return []
        rows = []
        for ts, row in hist.iterrows():
            rows.append([
                ts,
                float(row["Open"]),
                float(row["High"]),
                float(row["Low"]),
                float(row["Close"]),
                float(row.get("Volume", 0)),
            ])
        return rows

    try:
        loop = asyncio.get_event_loop()
        candles = await asyncio.wait_for(loop.run_in_executor(None, _fetch), timeout=20)
        logger.info(f"yfinance candles for {symbol}: {len(candles)} bars")
        return candles
    except Exception as exc:
        logger.warning(f"yfinance candle fetch failed ({symbol}): {exc}")
        return []


def _build_estimated_chain(
    spot: float, atm: int, interval: int, symbol: str
) -> list[dict]:
    """
    Build estimated option chain using Black-Scholes + India VIX.
    Generates ATM ±4 strikes for both CE and PE.
    """
    from bot.angel_feed import get_live_price

    vix = get_live_price("india_vix") or 15.0
    iv = vix / 100.0  # annualized IV from VIX

    # Time to nearest weekly expiry (Thursday)
    now = datetime.now(tz=IST)
    days_to_expiry = (3 - now.weekday()) % 7  # days until next Thursday
    if days_to_expiry == 0 and now.hour >= 15:
        days_to_expiry = 7
    T = max(days_to_expiry / 365.0, 1 / 365.0)

    r = 0.07  # India risk-free rate approximation

    strikes = [atm + i * interval for i in range(-4, 5)]
    chain = []
    for strike in strikes:
        ce_price = _bs_price(spot, strike, T, r, iv, "CE")
        pe_price = _bs_price(spot, strike, T, r, iv, "PE")
        moneyness = "ATM" if strike == atm else ("ITM" if strike < atm else "OTM")
        chain.append({
            "strike": strike,
            "CE_ltp": round(ce_price, 2),
            "PE_ltp": round(pe_price, 2),
            "moneyness": moneyness,
            "days_to_expiry": days_to_expiry,
            "estimated": True,
        })

    logger.info(
        f"[{symbol}] Estimated chain: ATM={atm} VIX={vix:.1f}% "
        f"T={days_to_expiry}d CE≈₹{chain[4]['CE_ltp']} PE≈₹{chain[4]['PE_ltp']}"
    )
    return chain


def _bs_price(S: float, K: float, T: float, r: float, sigma: float, opt: str) -> float:
    """Black-Scholes European option price."""
    if T <= 0:
        return max(0.0, S - K) if opt == "CE" else max(0.0, K - S)
    d1 = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    d2 = d1 - sigma * sqrt(T)
    N = lambda x: (1.0 + erf(x / sqrt(2.0))) / 2.0
    if opt == "CE":
        return S * N(d1) - K * exp(-r * T) * N(d2)
    return K * exp(-r * T) * N(-d2) - S * N(-d1)


def _compute_rsi(closes: list, period: int = 14) -> float:
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
    return 100.0 - (100.0 / (1 + avg_gain / avg_loss))


def _compute_ema(closes: list, span: int) -> float:
    if not closes:
        return 0.0
    k = 2.0 / (span + 1)
    ema = closes[0]
    for price in closes[1:]:
        ema = price * k + ema * (1 - k)
    return ema
