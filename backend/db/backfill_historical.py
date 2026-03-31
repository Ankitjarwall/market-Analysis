"""
Historical data backfill script.
Downloads 2 years of daily OHLCV data for all key symbols via yfinance
and saves them as daily_market_snapshots (time_of_day='close') in the DB.

Run inside Docker:
    docker compose exec backend python db/backfill_historical.py

Or run standalone (requires DB access):
    python db/backfill_historical.py
"""

import asyncio
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone

import yfinance as yf
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# ── Symbols to backfill ──────────────────────────────────────────────────────
SYMBOLS = {
    "nifty_close":      "^NSEI",
    "banknifty_close":  "^NSEBANK",
    "sp500_close":      "^GSPC",
    "nasdaq_close":     "^IXIC",
    "nikkei_close":     "^N225",
    "hangseng_close":   "^HSI",
    "shanghai_close":   "000001.SS",
    "ftse_close":       "^FTSE",
    "dax_close":        "^GDAXI",
    "crude_brent":      "BZ=F",
    "crude_wti":        "CL=F",
    "gold":             "GC=F",
    "silver":           "SI=F",
    "natural_gas":      "NG=F",
    "copper":           "HG=F",
    "usd_inr":          "INR=X",
    "dxy":              "DX-Y.NYB",
    "usd_jpy":          "JPY=X",
    "us_10y_yield":     "^TNX",
    "india_vix":        "^INDIAVIX",
    "us_vix":           "^VIX",
}

# Nifty OHLCV fields (downloaded separately for open/high/low/volume)
NIFTY_SYMBOL = "^NSEI"
BACKFILL_YEARS = 2


def download_all(years: int = BACKFILL_YEARS) -> pd.DataFrame:
    """Download all symbols as a combined wide DataFrame."""
    end = datetime.now()
    start = end - timedelta(days=years * 365)

    logger.info(f"Downloading {len(SYMBOLS)} symbols from {start.date()} to {end.date()}")

    # Batch download
    tickers = list(set(SYMBOLS.values()))
    raw = yf.download(
        tickers=" ".join(tickers),
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=True,
    )
    logger.info(f"Download complete. Shape: {raw.shape}")
    return raw, start, end


def extract_series(raw: pd.DataFrame, ticker: str, col: str = "Close") -> pd.Series:
    """Extract a column series for a given ticker from batch download."""
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            if ticker in raw.columns.get_level_values(0):
                return raw[ticker][col].dropna()
        else:
            # Single ticker download
            return raw[col].dropna()
    except Exception:
        pass
    return pd.Series(dtype=float)


async def backfill():
    from db.connection import AsyncSessionLocal, engine, Base
    from db.models import DailyMarketSnapshot
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    logger.info("Connecting to database...")

    # Download all data
    loop = asyncio.get_event_loop()
    raw, start, end = await loop.run_in_executor(None, lambda: download_all(BACKFILL_YEARS))

    # Build per-date rows
    reverse_map = {v: k for k, v in SYMBOLS.items()}

    # Get all unique dates from the nifty series
    nifty_series = extract_series(raw, NIFTY_SYMBOL, "Close")
    if nifty_series.empty:
        logger.error("Nifty data is empty! Cannot backfill.")
        return

    all_dates = nifty_series.index
    logger.info(f"Building rows for {len(all_dates)} trading days...")

    # Also extract Nifty OHLCV for detail
    nifty_open   = extract_series(raw, NIFTY_SYMBOL, "Open")
    nifty_high   = extract_series(raw, NIFTY_SYMBOL, "High")
    nifty_low    = extract_series(raw, NIFTY_SYMBOL, "Low")
    nifty_vol    = extract_series(raw, NIFTY_SYMBOL, "Volume")

    rows_inserted = 0
    rows_skipped = 0

    async with AsyncSessionLocal() as session:
        for dt in all_dates:
            row_date = dt.date() if hasattr(dt, "date") else dt

            # Skip weekends
            if row_date.weekday() >= 5:
                continue

            # Check if already exists
            existing = await session.execute(
                select(DailyMarketSnapshot).where(
                    DailyMarketSnapshot.date == row_date,
                    DailyMarketSnapshot.time_of_day == "close",
                )
            )
            if existing.scalar_one_or_none():
                rows_skipped += 1
                continue

            # Build all_data JSONB blob
            all_data: dict = {"date": str(row_date), "time_of_day": "close"}

            def _get(series: pd.Series, idx) -> float | None:
                try:
                    val = series.loc[idx]
                    return round(float(val), 4) if pd.notna(val) else None
                except (KeyError, TypeError):
                    return None

            # Per-symbol values
            symbol_data = {}
            for field_name, ticker in SYMBOLS.items():
                series = extract_series(raw, ticker, "Close")
                val = _get(series, dt)
                symbol_data[field_name] = val
                if val is not None:
                    all_data[field_name.replace("_close", "")] = val
                    all_data[field_name] = val

            snapshot = DailyMarketSnapshot(
                date=row_date,
                time_of_day="close",
                nifty_open=_get(nifty_open, dt),
                nifty_high=_get(nifty_high, dt),
                nifty_low=_get(nifty_low, dt),
                nifty_close=symbol_data.get("nifty_close"),
                nifty_volume=int(nifty_vol.loc[dt]) if dt in nifty_vol.index and pd.notna(nifty_vol.loc[dt]) else None,
                banknifty_close=symbol_data.get("banknifty_close"),
                sp500_close=symbol_data.get("sp500_close"),
                nasdaq_close=symbol_data.get("nasdaq_close"),
                nikkei_close=symbol_data.get("nikkei_close"),
                hangseng_close=symbol_data.get("hangseng_close"),
                shanghai_close=symbol_data.get("shanghai_close"),
                ftse_close=symbol_data.get("ftse_close"),
                dax_close=symbol_data.get("dax_close"),
                crude_brent=symbol_data.get("crude_brent"),
                crude_wti=symbol_data.get("crude_wti"),
                gold=symbol_data.get("gold"),
                silver=symbol_data.get("silver"),
                natural_gas=symbol_data.get("natural_gas"),
                copper=symbol_data.get("copper"),
                usd_inr=symbol_data.get("usd_inr"),
                dxy=symbol_data.get("dxy"),
                usd_jpy=symbol_data.get("usd_jpy"),
                us_10y_yield=symbol_data.get("us_10y_yield"),
                india_vix=symbol_data.get("india_vix"),
                us_vix=symbol_data.get("us_vix"),
                fresh_signals_count=sum(1 for v in symbol_data.values() if v is not None),
                all_data=all_data,
            )
            session.add(snapshot)
            rows_inserted += 1

            # Commit every 50 rows to avoid large transactions
            if rows_inserted % 50 == 0:
                await session.commit()
                logger.info(f"  Committed {rows_inserted} rows so far...")

        await session.commit()

    logger.info(f"Backfill complete: {rows_inserted} rows inserted, {rows_skipped} already existed")


if __name__ == "__main__":
    asyncio.run(backfill())
