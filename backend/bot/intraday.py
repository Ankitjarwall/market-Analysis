"""
Intraday technical analysis — RSI, EMA, volume ratio, VWAP.
Used by options signal engine.
"""

import asyncio
import logging
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


async def get_intraday_technicals(
    symbol: str = "^NSEI", interval: str = "5m"
) -> dict[str, Any]:
    """
    Compute intraday technical indicators for options signal generation.
    Returns RSI(14), EMA(9), EMA(21), volume_ratio.
    """
    try:
        ticker = yf.Ticker(symbol)
        data = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: ticker.history(period="5d", interval=interval, prepost=False),
        )

        if data is None or data.empty or len(data) < 22:
            return {}

        closes = data["Close"].dropna()
        volumes = data["Volume"].dropna()

        rsi = _compute_rsi(closes, period=14)
        ema9 = float(closes.ewm(span=9, adjust=False).mean().iloc[-1])
        ema21 = float(closes.ewm(span=21, adjust=False).mean().iloc[-1])

        # Volume ratio — current vs 20-period average
        avg_vol = float(volumes.tail(20).mean())
        curr_vol = float(volumes.iloc[-1])
        vol_ratio = round(curr_vol / avg_vol, 2) if avg_vol > 0 else 1.0

        current_price = float(closes.iloc[-1])

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
    except Exception as exc:
        logger.warning(f"Intraday technicals failed for {symbol}: {exc}")
        return {}


def _compute_rsi(closes: pd.Series, period: int = 14) -> float:
    delta = closes.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


async def get_options_chain_summary(
    symbol: str = "NIFTY", spot_price: float = 22000
) -> dict[str, Any]:
    """
    Fetch NSE options chain and return key strike levels for signal generation.
    Returns top OI strikes, max pain, and relevant put/call data.
    """
    import httpx
    url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/",
    }
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            await client.get("https://www.nseindia.com/", headers=headers)
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        records = data.get("records", {}).get("data", [])
        if not records:
            return {}

        # Find ATM strike (nearest to spot)
        strikes = sorted(set(r["strikePrice"] for r in records if "strikePrice" in r))
        atm = min(strikes, key=lambda s: abs(s - spot_price)) if strikes else spot_price

        # Get OI data around ATM (±5 strikes)
        atm_idx = strikes.index(atm) if atm in strikes else len(strikes) // 2
        relevant = strikes[max(0, atm_idx - 5): atm_idx + 6]

        chain_summary = []
        for r in records:
            if r.get("strikePrice") in relevant:
                entry = {"strike": r["strikePrice"]}
                if r.get("CE"):
                    entry["ce_oi"] = r["CE"].get("openInterest", 0)
                    entry["ce_ltp"] = r["CE"].get("lastPrice", 0)
                    entry["ce_iv"] = r["CE"].get("impliedVolatility", 0)
                if r.get("PE"):
                    entry["pe_oi"] = r["PE"].get("openInterest", 0)
                    entry["pe_ltp"] = r["PE"].get("lastPrice", 0)
                    entry["pe_iv"] = r["PE"].get("impliedVolatility", 0)
                chain_summary.append(entry)

        # Max pain — strike where maximum options expire worthless
        max_pain = _calculate_max_pain(records) if records else atm

        return {
            "atm_strike": atm,
            "max_pain": max_pain,
            "spot_price": spot_price,
            "chain_around_atm": chain_summary,
        }
    except Exception as exc:
        logger.warning(f"Options chain fetch failed: {exc}")
        return {}


def _calculate_max_pain(records: list) -> float:
    """Calculate max pain level from options chain data."""
    try:
        strikes = sorted(set(r["strikePrice"] for r in records if "strikePrice" in r))
        min_loss = float("inf")
        max_pain_strike = strikes[len(strikes) // 2]

        for candidate in strikes:
            loss = 0
            for r in records:
                s = r.get("strikePrice", 0)
                if r.get("CE"):
                    oi = r["CE"].get("openInterest", 0) or 0
                    loss += max(0, candidate - s) * oi
                if r.get("PE"):
                    oi = r["PE"].get("openInterest", 0) or 0
                    loss += max(0, s - candidate) * oi
            if loss < min_loss:
                min_loss = loss
                max_pain_strike = candidate

        return float(max_pain_strike)
    except Exception:
        return 0.0
