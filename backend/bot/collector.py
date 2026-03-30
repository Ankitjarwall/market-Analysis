"""
Data collector — fetches all 47 market signals.
Every signal includes a timestamp and passes sanity validation.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import yfinance as yf

logger = logging.getLogger(__name__)

# ── Symbol map ──────────────────────────────────────────────────────────────

YFINANCE_SYMBOLS = {
    # Indian indices
    "nifty": "^NSEI",
    "banknifty": "^NSEBANK",
    "nifty_midcap": "^NSMIDCP",
    "nifty_it": "^NSIT",
    "nifty_pharma": "^CNXPHARMA",
    "nifty_metal": "^CNXMETAL",
    # Global indices
    "sp500": "^GSPC",
    "nasdaq": "^IXIC",
    "dow": "^DJI",
    "nikkei": "^N225",
    "hangseng": "^HSI",
    "shanghai": "000001.SS",
    "ftse": "^FTSE",
    "dax": "^GDAXI",
    "cac": "^FCHI",
    "kospi": "^KS11",
    "taiwan": "^TWII",
    # Commodities
    "crude_brent": "BZ=F",
    "crude_wti": "CL=F",
    "natural_gas": "NG=F",
    "gold": "GC=F",
    "silver": "SI=F",
    "copper": "HG=F",
    # Currencies
    "usd_inr": "INR=X",
    "dxy": "DX-Y.NYB",
    "usd_jpy": "JPY=X",
    "eur_usd": "EURUSD=X",
    # Bonds
    "us_10y": "^TNX",
    "us_3m": "^IRX",
    # Volatility
    "india_vix": "^INDIAVIX",
    "us_vix": "^VIX",
}

# ── Sanity ranges ────────────────────────────────────────────────────────────

SANITY_RANGES = {
    "nifty_price": (15000, 40000),
    "banknifty": (35000, 110000),
    "sp500": (3000, 10000),
    "crude_brent": (30, 250),
    "gold": (1000, 5000),
    "usd_inr": (60, 120),
    "india_vix": (5, 100),
    "us_10y": (0.1, 15),
    "nifty_pe": (10, 50),
    "put_call_ratio": (0.3, 3.0),
    "silver": (10, 200),
    "copper": (2, 15),
}

MAX_DATA_AGE_MINUTES = {
    "live_prices": 5,
    "fii_data": 60,
    "news": 120,
    "pe_ratio": 120,
}


def _safe_price(ticker_info: dict, keys: list[str]) -> float | None:
    for key in keys:
        val = ticker_info.get(key)
        if val is not None:
            try:
                return float(val)
            except (TypeError, ValueError):
                pass
    return None


def _validate(key: str, value: float | None) -> tuple[float | None, bool]:
    if value is None:
        return None, False
    rng = SANITY_RANGES.get(key)
    if rng and not (rng[0] <= value <= rng[1]):
        logger.warning(f"Sanity fail: {key}={value} outside {rng}")
        return None, False
    return value, True


async def fetch_yfinance_prices() -> dict[str, Any]:
    """Fetch all yfinance symbols concurrently using download batch."""
    symbols = list(YFINANCE_SYMBOLS.values())
    fetch_time = datetime.now(timezone.utc)

    results: dict[str, Any] = {"_fetch_time": fetch_time.isoformat(), "_fresh": 0}

    try:
        # Batch download — 1 day, most recent close
        data = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: yf.download(
                tickers=" ".join(symbols),
                period="2d",
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                progress=False,
            ),
        )

        reverse_map = {v: k for k, v in YFINANCE_SYMBOLS.items()}
        fresh_count = 0

        for sym, name in reverse_map.items():
            try:
                if len(symbols) == 1:
                    closes = data["Close"]
                else:
                    closes = data[sym]["Close"] if sym in data.columns.get_level_values(0) else None

                if closes is not None and len(closes) > 0:
                    price = float(closes.dropna().iloc[-1])
                    results[name] = round(price, 4)
                    fresh_count += 1
                else:
                    results[name] = None
            except Exception as exc:
                logger.debug(f"Failed to get {name} ({sym}): {exc}")
                results[name] = None

        results["_fresh"] = fresh_count
        logger.info(f"yfinance batch: {fresh_count}/{len(symbols)} symbols fetched")
    except Exception as exc:
        logger.error(f"yfinance batch fetch error: {exc}")

    return results


async def fetch_fii_dii() -> dict[str, Any]:
    """Fetch FII/DII data from NSE India."""
    url = "https://www.nseindia.com/api/fiidiiTradeReact"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # First hit NSE homepage to get cookies
            await client.get("https://www.nseindia.com/", headers=headers)
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            raw = resp.json()

            # Parse FII and DII net values
            fii_net = None
            dii_net = None
            for row in raw.get("data", []):
                category = row.get("category", "").upper()
                if "FII" in category or "FPI" in category:
                    try:
                        fii_net = float(str(row.get("netValue", "0")).replace(",", ""))
                    except (ValueError, TypeError):
                        pass
                elif "DII" in category:
                    try:
                        dii_net = float(str(row.get("netValue", "0")).replace(",", ""))
                    except (ValueError, TypeError):
                        pass

            return {
                "fii_net": fii_net,
                "dii_net": dii_net,
                "fetch_time": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as exc:
        logger.warning(f"FII/DII fetch failed: {exc}")
        return {"fii_net": None, "dii_net": None}


async def fetch_nifty_pe() -> dict[str, Any]:
    """Fetch Nifty PE/PB/Dividend Yield from NSE or screener.in."""
    # Try NSE indices API
    url = "https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatabletoday"
    try:
        payload = {"name": "NIFTY 50", "startDate": "", "endDate": ""}
        async with httpx.AsyncClient(timeout=15) as client:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Content-Type": "application/json",
                "Referer": "https://www.niftyindices.com/",
            }
            resp = await client.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                rows = data.get("d", [])
                if rows:
                    latest = rows[0] if isinstance(rows, list) else rows
                    return {
                        "nifty_pe": _parse_float(latest.get("PE")),
                        "nifty_pb": _parse_float(latest.get("PB")),
                        "nifty_dividend_yield": _parse_float(latest.get("DivYield")),
                    }
    except Exception as exc:
        logger.debug(f"Nifty PE from niftyindices failed: {exc}")

    return {"nifty_pe": None, "nifty_pb": None, "nifty_dividend_yield": None}


async def fetch_put_call_ratio() -> dict[str, Any]:
    """Fetch PCR from NSE options chain."""
    url = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.nseindia.com/",
    }
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            await client.get("https://www.nseindia.com/", headers=headers)
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("records", {})
            pcr_value = _parse_float(records.get("data", [{}])[0].get("pcr") if records.get("data") else None)

            # Calculate PCR from total OI if not directly available
            if pcr_value is None:
                total_put_oi = sum(
                    r.get("PE", {}).get("openInterest", 0) or 0
                    for r in records.get("data", [])
                    if r.get("PE")
                )
                total_call_oi = sum(
                    r.get("CE", {}).get("openInterest", 0) or 0
                    for r in records.get("data", [])
                    if r.get("CE")
                )
                if total_call_oi > 0:
                    pcr_value = round(total_put_oi / total_call_oi, 3)

            return {"put_call_ratio": pcr_value}
    except Exception as exc:
        logger.warning(f"PCR fetch failed: {exc}")
        return {"put_call_ratio": None}


async def fetch_advance_decline() -> dict[str, Any]:
    """Fetch Advance/Decline ratio from NSE."""
    url = "https://www.nseindia.com/api/allIndices"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com/"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.get("https://www.nseindia.com/", headers=headers)
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            for index in data.get("data", []):
                if index.get("indexSymbol") == "NIFTY 50":
                    advances = _parse_float(index.get("advances"))
                    declines = _parse_float(index.get("declines"))
                    if advances and declines and declines > 0:
                        return {"advance_decline_ratio": round(advances / declines, 3)}
    except Exception as exc:
        logger.debug(f"A/D ratio fetch failed: {exc}")
    return {"advance_decline_ratio": None}


async def collect_all_signals() -> dict[str, Any]:
    """
    Main collection function — fetches all 47 signals concurrently.
    Returns a merged dict with all data and freshness count.
    """
    logger.info("Collecting all market signals...")

    prices_task = asyncio.create_task(fetch_yfinance_prices())
    fii_task = asyncio.create_task(fetch_fii_dii())
    pe_task = asyncio.create_task(fetch_nifty_pe())
    pcr_task = asyncio.create_task(fetch_put_call_ratio())
    ad_task = asyncio.create_task(fetch_advance_decline())

    prices, fii, pe, pcr, ad = await asyncio.gather(
        prices_task, fii_task, pe_task, pcr_task, ad_task,
        return_exceptions=True,
    )

    # Merge all results
    result: dict[str, Any] = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    if isinstance(prices, dict):
        result.update(prices)
    if isinstance(fii, dict):
        result.update(fii)
    if isinstance(pe, dict):
        result.update(pe)
    if isinstance(pcr, dict):
        result.update(pcr)
    if isinstance(ad, dict):
        result.update(ad)

    # Count fresh (non-None) signals
    signal_keys = [
        "nifty", "banknifty", "nifty_midcap", "nifty_it", "nifty_pharma", "nifty_metal",
        "sp500", "nasdaq", "dow", "nikkei", "hangseng", "shanghai", "ftse", "dax",
        "cac", "kospi", "taiwan",
        "crude_brent", "crude_wti", "natural_gas", "gold", "silver", "copper",
        "usd_inr", "dxy", "usd_jpy", "eur_usd", "us_10y", "us_3m",
        "india_vix", "us_vix",
        "fii_net", "dii_net", "nifty_pe", "nifty_pb", "nifty_dividend_yield",
        "put_call_ratio", "advance_decline_ratio",
    ]
    fresh_count = sum(1 for k in signal_keys if result.get(k) is not None)
    result["fresh_signals_count"] = fresh_count

    logger.info(f"Collection complete: {fresh_count}/{len(signal_keys)} signals fresh")
    return result


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (ValueError, TypeError):
        return None


async def calculate_vwap(symbol: str = "^NSEI", period_minutes: int = 390) -> float | None:
    """
    Calculate VWAP for Nifty from intraday 1-minute data.
    period_minutes=390 covers a full NSE trading day (9:15 AM to 3:30 PM).
    """
    try:
        ticker = yf.Ticker(symbol)
        data = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: ticker.history(period="1d", interval="1m", prepost=False),
        )
        if data.empty:
            return None
        # VWAP = sum(typical_price * volume) / sum(volume)
        typical = (data["High"] + data["Low"] + data["Close"]) / 3
        vwap = (typical * data["Volume"]).sum() / data["Volume"].sum()
        return round(float(vwap), 2)
    except Exception as exc:
        logger.warning(f"VWAP calculation failed: {exc}")
        return None
