"""
Data collector — all market data from Yahoo Finance + NSE India APIs.
News from NewsAPI (primary) + AlphaVantage (secondary).

Signal coverage (47 tracked):
  25 base prices  — Yahoo Finance (22) + 3 Indian sectoral indices
   7 NSE metrics  — FII/DII, Nifty PE/PB/DivYield, PCR, A/D ratio
  15 change%      — for key price signals
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ── Yahoo Finance symbol → field name ─────────────────────────────────────────
_YF_SYMBOLS = {
    # Indian indices (fallback when AngelOne SmartStream is not configured)
    "^NSEI":      "nifty",
    "^NSEBANK":   "banknifty",
    "^INDIAVIX":  "india_vix",
    "^BSESN":     "sensex",
    "^NSMIDCP":   "nifty_midcap",
    "^CNXIT":     "nifty_it",
    "^CNXPHARMA": "nifty_pharma",
    # Global indices
    "^GSPC":      "sp500",
    "^IXIC":      "nasdaq",
    "^N225":      "nikkei",
    "^HSI":       "hangseng",
    "000001.SS":  "shanghai",
    "^FTSE":      "ftse",
    "^GDAXI":     "dax",
    # Commodities
    "BZ=F":       "crude_brent",
    "CL=F":       "crude_wti",
    "GC=F":       "gold",
    "SI=F":       "silver",
    "NG=F":       "natural_gas",
    "HG=F":       "copper",
    # Forex / rates
    "USDINR=X":   "usd_inr",
    "DX-Y.NYB":   "dxy",
    "USDJPY=X":   "usd_jpy",
    "^TNX":       "us_10y",
    "^VIX":       "us_vix",
}

# All 47 signals tracked for freshness
_ALL_SIGNAL_KEYS = (
    # 25 base prices
    list(_YF_SYMBOLS.values())
    # 7 NSE/derived metrics
    + ["fii_net", "dii_net", "nifty_pe", "nifty_pb", "nifty_dividend_yield",
       "put_call_ratio", "advance_decline_ratio"]
    # 15 key change% signals
    + ["nifty_chg_pct", "banknifty_chg_pct", "india_vix_chg_pct", "sensex_chg_pct",
       "nifty_midcap_chg_pct", "nifty_it_chg_pct", "nifty_pharma_chg_pct",
       "sp500_chg_pct", "nasdaq_chg_pct", "gold_chg_pct", "crude_brent_chg_pct",
       "usd_inr_chg_pct", "us_10y_chg_pct", "ftse_chg_pct", "dax_chg_pct"]
)  # total = 47

# ── Yahoo Finance crumb/cookie cache ──────────────────────────────────────────
_global_price_cache: dict[str, float] = {}
_global_price_cache_ts: float = 0.0
_yf_crumb: str = ""
_yf_cookies: dict = {}
_yf_crumb_ts: float = 0.0

# ── NSE session cache (cookies + timing) ─────────────────────────────────────
_nse_cookies: dict = {}
_nse_session_ts: float = 0.0
_NSE_SESSION_TTL = 270  # refresh NSE cookies every ~4.5 minutes

# ── Per-endpoint result caches ────────────────────────────────────────────────
_fii_cache: dict[str, Any] = {}
_fii_cache_ts: float = 0.0
_nse_ext_cache: dict[str, Any] = {}
_nse_ext_cache_ts: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# NSE session management
# ─────────────────────────────────────────────────────────────────────────────

async def _ensure_nse_session() -> tuple[dict, dict]:
    """
    Return (api_headers, cookies) for NSE API calls.
    Visits nseindia.com first to get a valid session cookie if needed.
    """
    global _nse_cookies, _nse_session_ts
    now = time.monotonic()

    if not _nse_cookies or now - _nse_session_ts > _NSE_SESSION_TTL:
        try:
            html_headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            }
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get("https://www.nseindia.com/", headers=html_headers)
                _nse_cookies = dict(resp.cookies)
                _nse_session_ts = now
                logger.debug(f"NSE session refreshed ({len(_nse_cookies)} cookies)")
        except Exception as exc:
            logger.debug(f"NSE session init failed: {exc}")

    api_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/",
        "X-Requested-With": "XMLHttpRequest",
        "Connection": "keep-alive",
    }
    return api_headers, _nse_cookies


# ─────────────────────────────────────────────────────────────────────────────
# FII / DII
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_fii_dii_data() -> dict[str, Any]:
    """
    Fetch FII/DII net flows from NSE public API.
    NSE returns rows with category ("DII", "FII/FPI") and netValue field.
    Cached for 5 minutes — NSE updates this only a few times per day.
    """
    global _fii_cache, _fii_cache_ts
    now = time.monotonic()

    if _fii_cache and now - _fii_cache_ts < 300:
        return dict(_fii_cache)

    headers, cookies = await _ensure_nse_session()
    try:
        async with httpx.AsyncClient(
            timeout=10, headers=headers, cookies=cookies, follow_redirects=True
        ) as client:
            resp = await client.get("https://www.nseindia.com/api/fiidiiTradeReact")
            if resp.status_code != 200:
                logger.debug(f"FII/DII: HTTP {resp.status_code}")
                return dict(_fii_cache)
            data = resp.json()

        result: dict[str, Any] = {}
        if isinstance(data, list):
            for row in data:
                cat = str(row.get("category", "")).upper()
                net = _parse_float(row.get("netValue"))
                if net is None:
                    continue
                if "DII" in cat and "FII" not in cat:
                    result["dii_net"] = round(net, 2)
                elif "FII" in cat or "FPI" in cat:
                    result["fii_net"] = round(net, 2)

        if result:
            _fii_cache = result
            _fii_cache_ts = now
            logger.info(
                f"FII/DII: fii_net={result.get('fii_net')}, dii_net={result.get('dii_net')}"
            )
        return result

    except Exception as exc:
        logger.debug(f"FII/DII fetch failed: {exc}")
        return dict(_fii_cache)


# ─────────────────────────────────────────────────────────────────────────────
# NSE extended metrics: PE, PB, Dividend Yield, PCR, Advance/Decline
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_nse_extended_data() -> dict[str, Any]:
    """
    Fetch from NSE allIndices:
      - nifty_pe, nifty_pb, nifty_dividend_yield (dy field)
      - advance_decline_ratio (advances / declines)
    And from options chain:
      - put_call_ratio (PE totOI / CE totOI) — only available on trading days
    Cached for 5 minutes.
    """
    global _nse_ext_cache, _nse_ext_cache_ts
    now = time.monotonic()

    if _nse_ext_cache and now - _nse_ext_cache_ts < 300:
        return dict(_nse_ext_cache)

    headers, cookies = await _ensure_nse_session()
    result: dict[str, Any] = {}

    async with httpx.AsyncClient(
        timeout=12, headers=headers, cookies=cookies, follow_redirects=True
    ) as client:
        # allIndices — PE, PB, DivYield, Advance/Decline for all indices in one call
        try:
            resp = await client.get("https://www.nseindia.com/api/allIndices")
            if resp.status_code == 200:
                data = resp.json()
                nifty = next(
                    (x for x in data.get("data", []) if x.get("index") == "NIFTY 50"),
                    None,
                )
                if nifty:
                    if nifty.get("pe"):
                        result["nifty_pe"] = _parse_float(nifty["pe"])
                    if nifty.get("pb"):
                        result["nifty_pb"] = _parse_float(nifty["pb"])
                    if nifty.get("dy"):
                        result["nifty_dividend_yield"] = _parse_float(nifty["dy"])
                    advances = _parse_float(nifty.get("advances"))
                    declines = _parse_float(nifty.get("declines"))
                    if advances is not None and declines and declines > 0:
                        result["advance_decline_ratio"] = round(advances / declines, 2)
                sensex_data = next(
                    (x for x in data.get("data", []) if x.get("index") == "S&P BSE SENSEX"),
                    None,
                )
                if sensex_data and sensex_data.get("last"):
                    result["sensex"] = _parse_float(sensex_data["last"])
                if sensex_data and sensex_data.get("previousClose"):
                    result["sensex_prev_close"] = _parse_float(sensex_data["previousClose"])
                if sensex_data and sensex_data.get("open"):
                    result["sensex_today_open"] = _parse_float(sensex_data["open"])
                if sensex_data and sensex_data.get("yearHigh"):
                    result["sensex_chg_pct"] = _parse_float(sensex_data.get("percentChange"))
            else:
                logger.debug(f"NSE allIndices: HTTP {resp.status_code}")
        except Exception as exc:
            logger.debug(f"NSE PE/PB/ADR fetch failed: {exc}")

        # PCR from Nifty options chain (only available on trading days)
        # NSE option-chain requires a more established session — warm it up first
        try:
            await client.get(
                "https://www.nseindia.com/market-data/live-market-data-changes",
                timeout=8,
            )
        except Exception:
            pass
        try:
            resp = await client.get(
                "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY",
                timeout=12,
            )
            if resp.status_code == 200:
                data = resp.json()
                filtered = data.get("filtered", {})
                ce_oi = filtered.get("CE", {}).get("totOI", 0)
                pe_oi = filtered.get("PE", {}).get("totOI", 0)
                if ce_oi and ce_oi > 0:
                    result["put_call_ratio"] = round(pe_oi / ce_oi, 3)
            else:
                logger.warning(f"NSE option chain HTTP {resp.status_code} — PCR unavailable")
                # Carry forward last cached PCR if available
                if _nse_ext_cache.get("put_call_ratio"):
                    result["put_call_ratio"] = _nse_ext_cache["put_call_ratio"]
        except Exception as exc:
            logger.warning(f"NSE PCR fetch failed: {exc}")
            if _nse_ext_cache.get("put_call_ratio"):
                result["put_call_ratio"] = _nse_ext_cache["put_call_ratio"]

    if result:
        _nse_ext_cache = result
        _nse_ext_cache_ts = now
        logger.info(
            f"NSE extended: pe={result.get('nifty_pe')}, pb={result.get('nifty_pb')}, "
            f"dy={result.get('nifty_dividend_yield')}, pcr={result.get('put_call_ratio')}, "
            f"adr={result.get('advance_decline_ratio')}"
        )

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Yahoo Finance prices
# ─────────────────────────────────────────────────────────────────────────────

async def _refresh_yahoo_crumb() -> bool:
    """Fetch Yahoo Finance crumb + cookies (required for v7 quote API since 2024)."""
    global _yf_crumb, _yf_cookies, _yf_crumb_ts
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r1 = await client.get("https://fc.yahoo.com/", headers=headers)
            cookies = dict(r1.cookies)
            r2 = await client.get(
                "https://query2.finance.yahoo.com/v1/test/getcrumb",
                headers=headers, cookies=cookies,
            )
            crumb = r2.text.strip()
        if crumb:
            _yf_crumb = crumb
            _yf_cookies = cookies
            _yf_crumb_ts = time.monotonic()
            return True
    except Exception as exc:
        logger.debug(f"Yahoo crumb refresh failed: {exc}")
    return False


async def fetch_global_prices() -> dict[str, Any]:
    """
    Fetch all 25 prices (Indian + global indices, commodities, forex) via
    Yahoo Finance JSON API. Single HTTP call for all symbols.
    Cached for 60 seconds.
    """
    global _global_price_cache, _global_price_cache_ts, _yf_crumb, _yf_cookies, _yf_crumb_ts
    now = time.monotonic()

    if _global_price_cache and now - _global_price_cache_ts < 60:
        return dict(_global_price_cache)

    if not _yf_crumb or now - _yf_crumb_ts > 3600:
        await _refresh_yahoo_crumb()

    symbols_str = ",".join(_YF_SYMBOLS.keys())
    params = {
        "symbols": symbols_str,
        "crumb": _yf_crumb,
        "fields": (
            "regularMarketPrice,regularMarketChangePercent,"
            "regularMarketPreviousClose,regularMarketChange,"
            "regularMarketOpen,regularMarketDayHigh,regularMarketDayLow"
        ),
        "formatted": "false",
        "lang": "en-US",
        "region": "US",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            resp = await client.get(
                "https://query2.finance.yahoo.com/v7/finance/quote",
                params=params, headers=headers, cookies=_yf_cookies,
            )
            if resp.status_code == 401:
                await _refresh_yahoo_crumb()
                params["crumb"] = _yf_crumb
                resp = await client.get(
                    "https://query2.finance.yahoo.com/v7/finance/quote",
                    params=params, headers=headers, cookies=_yf_cookies,
                )
            resp.raise_for_status()
            data = resp.json()

        result: dict[str, Any] = {}
        quotes = data.get("quoteResponse", {}).get("result", [])
        for q in quotes:
            symbol = q.get("symbol", "")
            key = _YF_SYMBOLS.get(symbol)
            if key and q.get("regularMarketPrice") is not None:
                result[key] = round(float(q["regularMarketPrice"]), 4)
            if key and q.get("regularMarketChangePercent") is not None:
                result[f"{key}_chg_pct"] = round(float(q["regularMarketChangePercent"]), 4)
            if key and q.get("regularMarketPreviousClose") is not None:
                result[f"{key}_prev_close"] = round(float(q["regularMarketPreviousClose"]), 4)
            if key and q.get("regularMarketOpen") is not None:
                result[f"{key}_today_open"] = round(float(q["regularMarketOpen"]), 4)
            if key and q.get("regularMarketDayHigh") is not None:
                result[f"{key}_today_high"] = round(float(q["regularMarketDayHigh"]), 4)
            if key and q.get("regularMarketDayLow") is not None:
                result[f"{key}_today_low"] = round(float(q["regularMarketDayLow"]), 4)

        _global_price_cache = result
        _global_price_cache_ts = now
        fresh = sum(1 for k in _YF_SYMBOLS.values() if result.get(k) is not None)
        logger.info(
            f"Yahoo prices: {fresh}/{len(_YF_SYMBOLS)} symbols "
            f"(nifty={result.get('nifty')}, banknifty={result.get('banknifty')}, "
            f"vix={result.get('india_vix')})"
        )
        return result

    except Exception as exc:
        logger.warning(f"Yahoo Finance fetch failed: {exc} — using cache")
        return dict(_global_price_cache)


# ─────────────────────────────────────────────────────────────────────────────
# News
# ─────────────────────────────────────────────────────────────────────────────

async def fetch_market_news() -> dict[str, Any]:
    """Fetch top India market news from NewsAPI."""
    try:
        import os
        api_key = os.environ.get("NEWS_API_KEY", "")
        if not api_key:
            from config import settings
            api_key = getattr(settings, "news_api_key", "")
        if not api_key:
            return {"news": [], "news_count": 0}

        params = {
            "q": 'Nifty OR SEBI OR RBI OR "Indian market" OR "stock market India"',
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "apiKey": api_key,
        }
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get("https://newsapi.org/v2/everything", params=params)
            resp.raise_for_status()
            articles = resp.json().get("articles", [])
        news = [
            {
                "title": a.get("title", ""),
                "source": a.get("source", {}).get("name", ""),
                "published_at": a.get("publishedAt", ""),
                "url": a.get("url", ""),
                "description": a.get("description", ""),
            }
            for a in articles
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]
        logger.info(f"NewsAPI: {len(news)} articles")
        return {"news": news, "news_count": len(news)}
    except Exception as exc:
        logger.warning(f"NewsAPI fetch failed: {exc}")
        return {"news": [], "news_count": 0}


async def fetch_alphavantage_news() -> dict[str, Any]:
    """Fetch India market news from AlphaVantage as secondary source."""
    try:
        import os
        api_key = os.environ.get("NEWS_API_KEY2", "")
        if not api_key:
            return {}
        params = {
            "function": "NEWS_SENTIMENT",
            "topics": "financial_markets,economy_macro",
            "sort": "LATEST",
            "limit": "10",
            "apikey": api_key,
        }
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get("https://www.alphavantage.co/query", params=params)
            resp.raise_for_status()
            feed = resp.json().get("feed", [])
        av_news = [
            {
                "title": a.get("title", ""),
                "source": a.get("source", "AlphaVantage"),
                "published_at": a.get("time_published", ""),
                "url": a.get("url", ""),
                "description": a.get("summary", ""),
                "sentiment": a.get("overall_sentiment_label", ""),
            }
            for a in feed if a.get("title")
        ]
        logger.info(f"AlphaVantage: {len(av_news)} articles")
        return {"av_news": av_news, "av_news_count": len(av_news)}
    except Exception as exc:
        logger.debug(f"AlphaVantage fetch failed: {exc}")
        return {}


# ─────────────────────────────────────────────────────────────────────────────
# Main collection
# ─────────────────────────────────────────────────────────────────────────────

async def collect_all_signals() -> dict[str, Any]:
    """
    Collect all 47 market signals concurrently:
      - 25 prices + 15 change%  : Yahoo Finance
      -  7 NSE metrics           : NSE India APIs (with session cookies)
      - News                     : NewsAPI + AlphaVantage
      - Indian live prices        : AngelOne SmartStream (if configured)
    """
    from bot.angel_feed import get_all_live_prices

    # Run all external fetches concurrently
    global_task  = asyncio.create_task(fetch_global_prices())
    fii_task     = asyncio.create_task(fetch_fii_dii_data())
    nse_ext_task = asyncio.create_task(fetch_nse_extended_data())
    news_task    = asyncio.create_task(fetch_market_news())
    av_task      = asyncio.create_task(fetch_alphavantage_news())

    global_prices, fii_data, nse_ext, news, av_news = await asyncio.gather(
        global_task, fii_task, nse_ext_task, news_task, av_task,
        return_exceptions=True,
    )

    result: dict[str, Any] = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    if isinstance(global_prices, dict):
        result.update(global_prices)

    if isinstance(fii_data, dict):
        result.update(fii_data)

    if isinstance(nse_ext, dict):
        result.update(nse_ext)

    # AngelOne data takes priority over Yahoo fallbacks for Indian indices
    angel_prices = get_all_live_prices()
    result.update(angel_prices)

    # VWAP fallback: AngelOne does not emit average_traded_price for NSE index tokens.
    # Compute intraday typical-price approximation (H+L+C)/3 from OHLC when needed.
    if not result.get("vwap"):
        h = result.get("nifty_today_high")
        l = result.get("nifty_today_low")
        c = result.get("nifty")
        if h and l and c:
            result["vwap"] = round((h + l + c) / 3, 2)
            logger.info(f"VWAP (OHLC fallback): ₹{result['vwap']} (H:{h} L:{l} C:{c})")

    if not result.get("banknifty_vwap"):
        h = result.get("banknifty_today_high")
        l = result.get("banknifty_today_low")
        c = result.get("banknifty")
        if h and l and c:
            result["banknifty_vwap"] = round((h + l + c) / 3, 2)

    # Merge news
    if isinstance(news, dict):
        result.update(news)
    if isinstance(av_news, dict):
        main_articles = result.get("news", [])
        av_articles   = av_news.get("av_news", [])
        if av_articles:
            result["news"]       = main_articles + av_articles
            result["news_count"] = len(result["news"])

    # Count fresh signals across all 47 defined keys
    fresh_count = sum(1 for k in _ALL_SIGNAL_KEYS if result.get(k) is not None)
    result["fresh_signals_count"] = fresh_count
    result["total_signals"]       = len(_ALL_SIGNAL_KEYS)  # always 47

    logger.info(
        f"Collection complete: {fresh_count}/{len(_ALL_SIGNAL_KEYS)} signals fresh "
        f"(nifty={result.get('nifty')}, fii={result.get('fii_net')}, "
        f"pe={result.get('nifty_pe')}, pcr={result.get('put_call_ratio')})"
    )
    return result


async def calculate_vwap(symbol: str = "^NSEI", period_minutes: int = 390) -> float | None:
    """Return VWAP from AngelOne if available, else compute (H+L+C)/3 from live OHLC."""
    from bot.angel_feed import get_live_price
    vwap = get_live_price("vwap")
    if vwap:
        return vwap
    h = get_live_price("nifty_today_high")
    l = get_live_price("nifty_today_low")
    c = get_live_price("nifty")
    if h and l and c:
        return round((h + l + c) / 3, 2)
    # Final fallback: use _global_price_cache OHLC from Yahoo
    h = _global_price_cache.get("nifty_today_high")
    l = _global_price_cache.get("nifty_today_low")
    c = _global_price_cache.get("nifty")
    if h and l and c:
        return round((h + l + c) / 3, 2)
    return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# NSE Open Interest chain — per-strike OI, max pain, call/put walls
# ─────────────────────────────────────────────────────────────────────────────

# OI chain cache: symbol → {data} / symbol → timestamp
_oi_cache: dict[str, Any] = {}
_oi_cache_ts: dict[str, float] = {}
_OI_CACHE_TTL = 60  # refresh every 60 s during market hours


async def fetch_nse_oi_chain(symbol: str = "NIFTY") -> dict[str, Any]:
    """
    Fetch NSE options chain for the nearest weekly expiry.

    Returns per-strike OI/LTP/IV/volume for both CE and PE, plus:
      - pcr          : total PE OI / total CE OI
      - max_pain     : strike where total option-buyer loss is maximised
      - call_wall    : strike with highest CE OI (strong resistance level)
      - put_wall     : strike with highest PE OI (strong support level)
      - top_oi_strikes : top-10 strikes by combined OI (descending)

    Cached for 60 seconds. Falls back to previous cache on failure.
    """
    global _oi_cache, _oi_cache_ts
    now = time.monotonic()

    if _oi_cache.get(symbol) and now - _oi_cache_ts.get(symbol, 0) < _OI_CACHE_TTL:
        return dict(_oi_cache[symbol])

    headers, cookies = await _ensure_nse_session()

    try:
        async with httpx.AsyncClient(
            timeout=15, headers=headers, cookies=cookies, follow_redirects=True
        ) as client:
            # Warm-up page so NSE recognises this as a browser session
            try:
                await client.get(
                    "https://www.nseindia.com/market-data/live-market-data-changes",
                    timeout=8,
                )
            except Exception:
                pass

            resp = await client.get(
                f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}",
                timeout=15,
            )
            if resp.status_code != 200:
                logger.warning(f"NSE OI chain ({symbol}): HTTP {resp.status_code}")
                return dict(_oi_cache.get(symbol, {}))

            data = resp.json()

    except Exception as exc:
        logger.warning(f"NSE OI chain fetch failed ({symbol}): {exc}")
        return dict(_oi_cache.get(symbol, {}))

    records = data.get("records", {})
    chain_rows = records.get("data", [])
    expiry_dates = records.get("expiryDates", [])

    # Always use the nearest expiry for intraday signal decisions
    nearest_expiry = expiry_dates[0] if expiry_dates else None

    strikes: dict[int, dict] = {}
    total_ce_oi = 0
    total_pe_oi = 0

    for row in chain_rows:
        strike = row.get("strikePrice")
        expiry = row.get("expiryDate")
        if not strike:
            continue
        if nearest_expiry and expiry != nearest_expiry:
            continue

        ce = row.get("CE", {}) or {}
        pe = row.get("PE", {}) or {}

        ce_oi  = int(ce.get("openInterest", 0) or 0)
        pe_oi  = int(pe.get("openInterest", 0) or 0)
        ce_coi = int(ce.get("changeinOpenInterest", 0) or 0)
        pe_coi = int(pe.get("changeinOpenInterest", 0) or 0)

        strikes[int(strike)] = {
            "strike":      int(strike),
            "CE_oi":       ce_oi,
            "PE_oi":       pe_oi,
            "CE_change_oi": ce_coi,
            "PE_change_oi": pe_coi,
            "CE_ltp":      _parse_float(ce.get("lastPrice")) or 0.0,
            "PE_ltp":      _parse_float(pe.get("lastPrice")) or 0.0,
            "CE_iv":       _parse_float(ce.get("impliedVolatility")) or 0.0,
            "PE_iv":       _parse_float(pe.get("impliedVolatility")) or 0.0,
            "CE_vol":      int(ce.get("totalTradedVolume", 0) or 0),
            "PE_vol":      int(pe.get("totalTradedVolume", 0) or 0),
        }
        total_ce_oi += ce_oi
        total_pe_oi += pe_oi

    if not strikes:
        return dict(_oi_cache.get(symbol, {}))

    pcr = round(total_pe_oi / total_ce_oi, 3) if total_ce_oi > 0 else None
    max_pain  = _compute_max_pain(strikes)
    call_wall = max(strikes.values(), key=lambda x: x["CE_oi"])["strike"]
    put_wall  = max(strikes.values(), key=lambda x: x["PE_oi"])["strike"]

    # Top-10 strikes by combined (CE + PE) OI — high activity zones
    top_strikes = sorted(
        strikes.values(),
        key=lambda x: x["CE_oi"] + x["PE_oi"],
        reverse=True,
    )[:10]

    result: dict[str, Any] = {
        "symbol":         symbol,
        "expiry":         nearest_expiry,
        "strikes":        strikes,
        "total_ce_oi":    total_ce_oi,
        "total_pe_oi":    total_pe_oi,
        "pcr":            pcr,
        "max_pain":       max_pain,
        "call_wall":      call_wall,
        "put_wall":       put_wall,
        "top_oi_strikes": [s["strike"] for s in top_strikes],
        "collected_at":   datetime.now(timezone.utc).isoformat(),
    }

    _oi_cache[symbol] = result
    _oi_cache_ts[symbol] = now

    logger.info(
        f"NSE OI ({symbol}): {len(strikes)} strikes | "
        f"PCR={pcr} | MaxPain={max_pain} | "
        f"CallWall={call_wall} | PutWall={put_wall}"
    )
    return result


def _compute_max_pain(strikes: dict[int, dict]) -> int | None:
    """
    Max pain = the expiry price at which total option-buyer loss is maximised
    (equivalently, total option-writer gain is maximised).

    For each candidate expiry price S (one of the strike prices):
      CE buyer loss at S = Σ max(0, S − K) × CE_OI(K)   for all K
      PE buyer loss at S = Σ max(0, K − S) × PE_OI(K)   for all K
      Total pain(S)      = CE loss + PE loss
    Max-pain strike = argmax_S Total pain(S)
    """
    sorted_strikes = sorted(strikes.keys())
    if not sorted_strikes:
        return None

    best_strike = None
    best_pain   = -1.0

    for s in sorted_strikes:
        sf = float(s)
        ce_pain = sum(
            max(0.0, sf - float(k)) * v["CE_oi"]
            for k, v in strikes.items()
        )
        pe_pain = sum(
            max(0.0, float(k) - sf) * v["PE_oi"]
            for k, v in strikes.items()
        )
        total_pain = ce_pain + pe_pain
        if total_pain > best_pain:
            best_pain   = total_pain
            best_strike = s

    return best_strike


def get_best_strike(
    spot: float,
    signal_type: str,
    oi_data: dict,
    symbol: str = "NIFTY",
) -> dict[str, Any]:
    """
    Return the optimal strike for a BUY_CALL or BUY_PUT signal using OI data.

    Selection logic:
    ─ Start from ATM; evaluate ATM, +1 OTM, +2 OTM (CALL) or -1/-2 OTM (PUT).
    ─ Prefer strikes with: high OI (liquidity), positive change OI (fresh buildup).
    ─ Penalise: the call/put wall (strong resistance/support against the move),
                strikes near max pain (price tends to pin there into expiry).
    ─ Returns the highest-scoring candidate with full rationale.
    """
    interval = 100 if "BANK" in symbol.upper() else 50
    atm = round(spot / interval) * interval
    option_type = "CE" if signal_type == "BUY_CALL" else "PE"

    strikes    = oi_data.get("strikes", {})
    call_wall  = oi_data.get("call_wall")
    put_wall   = oi_data.get("put_wall")
    max_pain   = oi_data.get("max_pain")

    if not strikes:
        return {
            "strike":      atm,
            "option_type": option_type,
            "rationale":   "ATM — OI data unavailable",
            "oi_score":    0,
        }

    candidates = []
    for offset in [0, 1, 2]:
        k = atm + offset * interval if signal_type == "BUY_CALL" else atm - offset * interval
        row = strikes.get(int(k))
        if not row:
            continue

        oi        = row[f"{option_type}_oi"]
        ltp       = row[f"{option_type}_ltp"]
        change_oi = row[f"{option_type}_change_oi"]

        at_wall = (k == call_wall and signal_type == "BUY_CALL") or \
                  (k == put_wall  and signal_type == "BUY_PUT")
        near_max_pain = bool(max_pain and abs(k - max_pain) <= interval)

        score = oi / 1_000 if oi > 0 else 0.0
        if change_oi > 0:
            score *= 1.25   # fresh OI buildup is bullish for direction
        if at_wall:
            score *= 0.25   # strong resistance/support likely to cap the move
        if near_max_pain:
            score *= 0.80   # price tends to pin near max pain at expiry

        candidates.append({
            "strike":        k,
            "option_type":   option_type,
            "oi":            oi,
            "ltp":           ltp,
            "change_oi":     change_oi,
            "at_wall":       at_wall,
            "near_max_pain": near_max_pain,
            "oi_score":      round(score, 2),
            "offset":        offset,
        })

    if not candidates:
        return {"strike": atm, "option_type": option_type, "rationale": "ATM — no strike data", "oi_score": 0}

    best = max(candidates, key=lambda x: x["oi_score"])

    parts = []
    if best["offset"] == 0:
        parts.append("ATM")
    else:
        tag = f"+{best['offset']} OTM" if signal_type == "BUY_CALL" else f"-{best['offset']} OTM"
        parts.append(tag)
    if best["change_oi"] > 0:
        parts.append(f"fresh OI +{best['change_oi']:,}")
    if best["at_wall"]:
        parts.append("AT WALL ⚠")
    if best["near_max_pain"]:
        parts.append(f"near max-pain {max_pain}")

    return {
        "strike":      best["strike"],
        "option_type": option_type,
        "oi":          best["oi"],
        "ltp":         best["ltp"],
        "change_oi":   best["change_oi"],
        "rationale":   " | ".join(parts),
        "oi_score":    best["oi_score"],
        "call_wall":   call_wall,
        "put_wall":    put_wall,
        "max_pain":    max_pain,
    }
