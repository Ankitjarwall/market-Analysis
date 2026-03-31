"""
Data collector — all Indian market data from AngelOne SmartStream.
News from NewsAPI (primary) + AlphaVantage (secondary).

No yfinance. No NSE web scraping.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def fetch_market_news() -> dict[str, Any]:
    """Fetch top India market news from NewsAPI."""
    try:
        import os
        api_key = os.environ.get("NEWS_API_KEY", "")
        if not api_key:
            from config import settings
            api_key = settings.news_api_key
        if not api_key:
            return {"news": [], "news_count": 0}

        url = "https://newsapi.org/v2/everything"
        params = {
            "q": "Nifty OR SEBI OR RBI OR \"Indian market\" OR \"stock market India\"",
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "apiKey": api_key,
        }
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", [])
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
    """Fetch India market news from AlphaVantage as a secondary source."""
    try:
        import os
        api_key = os.environ.get("NEWS_API_KEY2", "")
        if not api_key:
            return {}

        url = "https://www.alphavantage.co/query"
        params = {
            "function": "NEWS_SENTIMENT",
            "topics": "financial_markets,economy_macro",
            "sort": "LATEST",
            "limit": "10",
            "apikey": api_key,
        }
        async with httpx.AsyncClient(timeout=8) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            feed = data.get("feed", [])
            av_news = [
                {
                    "title": a.get("title", ""),
                    "source": a.get("source", "AlphaVantage"),
                    "published_at": a.get("time_published", ""),
                    "url": a.get("url", ""),
                    "description": a.get("summary", ""),
                    "sentiment": a.get("overall_sentiment_label", ""),
                }
                for a in feed
                if a.get("title")
            ]
            logger.info(f"AlphaVantage: {len(av_news)} articles")
            return {"av_news": av_news, "av_news_count": len(av_news)}
    except Exception as exc:
        logger.debug(f"AlphaVantage fetch failed: {exc}")
        return {}


async def collect_all_signals() -> dict[str, Any]:
    """
    Collect all market data from AngelOne SmartStream + news APIs.
    Indian prices (Nifty, BankNifty, VIX, OHLC, VWAP) come from the live
    WebSocket feed. No yfinance polling. No NSE web scraping.
    """
    from bot.angel_feed import get_all_live_prices

    # Fetch news concurrently while reading from the always-live price cache
    news_task = asyncio.create_task(fetch_market_news())
    av_task = asyncio.create_task(fetch_alphavantage_news())

    news, av_news = await asyncio.gather(news_task, av_task, return_exceptions=True)

    result: dict[str, Any] = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    # All Indian market data — real-time from AngelOne WebSocket cache
    angel_prices = get_all_live_prices()
    result.update(angel_prices)

    # Merge news
    if isinstance(news, dict):
        result.update(news)
    if isinstance(av_news, dict):
        main_news = result.get("news", [])
        av_articles = av_news.get("av_news", [])
        if av_articles:
            result["news"] = main_news + av_articles
            result["news_count"] = len(result["news"])

    # Count fresh Indian signals (fields AngelOne provides)
    signal_keys = [
        "nifty", "banknifty", "india_vix",
        "nifty_midcap", "nifty_it", "nifty_pharma",
        "nifty_vwap", "banknifty_vwap",
    ]
    fresh_count = sum(1 for k in signal_keys if result.get(k) is not None)
    result["fresh_signals_count"] = fresh_count

    logger.info(
        f"Collection: {fresh_count} AngelOne prices, "
        f"{result.get('news_count', 0)} news articles"
    )
    return result


async def calculate_vwap(symbol: str = "^NSEI", period_minutes: int = 390) -> float | None:
    """
    Return intraday VWAP for Nifty from AngelOne feed.
    AngelOne SnapQuote provides average_traded_price (server-computed VWAP).
    The symbol/period_minutes args are kept for call-site compatibility.
    """
    from bot.angel_feed import get_live_price
    return get_live_price("vwap")


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (ValueError, TypeError):
        return None
