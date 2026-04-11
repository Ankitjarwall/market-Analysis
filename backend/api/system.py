"""
System monitoring endpoints.
GET  /api/system/logs          窶・recent log buffer
GET  /api/system/status        窶・DB / Redis / scheduler / AngelOne health
GET  /api/system/test-feeds    窶・live-test all external data sources
"""

import asyncio
import time

from fastapi import APIRouter, Depends, Query

from auth.middleware import get_current_user, require_roles
from config import settings
from core.log_buffer import get_recent_logs
from db.models import User

router = APIRouter(prefix="/api/system", tags=["system"])

RequireAdmin = require_roles("super_admin", "admin")


@router.get("/logs")
async def get_logs(
    limit: int = Query(default=200, ge=1, le=500),
    source: str | None = Query(default=None),
    level: str | None = Query(default=None),
    _: User = Depends(get_current_user),
):
    logs = get_recent_logs(limit * 2)
    if source:
        logs = [l for l in logs if l.get("source") == source]
    if level:
        logs = [l for l in logs if l.get("level") == level.upper()]
    return {"logs": logs[:limit], "total": len(logs)}


@router.get("/status")
async def get_system_status(_: User = Depends(get_current_user)):
    """Check local dependencies plus role-aware worker ownership."""
    status: dict = {}

    try:
        from db.connection import AsyncSessionLocal
        from sqlalchemy import text

        t0 = time.perf_counter()
        async with AsyncSessionLocal() as s:
            await s.execute(text("SELECT 1"))
        status["postgres"] = {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as e:
        status["postgres"] = {"ok": False, "error": str(e)}

    try:
        import redis.asyncio as aioredis

        t0 = time.perf_counter()
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        status["redis"] = {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as e:
        status["redis"] = {"ok": False, "error": str(e)}

    if settings.app_role in ("all", "market_worker"):
        try:
            from bot.scheduler import _scheduler

            status["scheduler"] = {
                "ok": _scheduler is not None and _scheduler.running,
                "local": True,
                "jobs": len(_scheduler.get_jobs()) if _scheduler else 0,
            }
        except Exception as e:
            status["scheduler"] = {"ok": False, "local": True, "error": str(e)}
    else:
        status["scheduler"] = {"ok": True, "local": False, "managed_in": "market_worker"}

    if settings.app_role in ("all", "market_worker", "execution_worker"):
        try:
            from bot.angel_feed import get_all_live_prices, is_active

            prices = get_all_live_prices()
            status["angel_feed"] = {
                "ok": is_active(),
                "local": True,
                "connected": is_active(),
                "nifty": prices.get("nifty"),
                "banknifty": prices.get("banknifty"),
                "india_vix": prices.get("india_vix"),
                "price_fields": len(prices),
            }
        except Exception as e:
            status["angel_feed"] = {"ok": False, "local": True, "error": str(e)}
    else:
        status["angel_feed"] = {"ok": True, "local": False, "managed_in": "market_worker/execution_worker"}

    try:
        from ws.live_feed import _connections, get_latest_market_snapshot

        total = sum(len(v) for v in _connections.values())
        latest_market = await get_latest_market_snapshot()
        status["websocket"] = {"ok": True, "connections": total, "users": len(_connections)}
        status["data_cache"] = {
            "ok": bool(latest_market),
            "local": settings.app_role in ("all", "market_worker"),
            "keys": len(latest_market or {}),
            "has_nifty": "nifty" in (latest_market or {}),
            "has_news": "news" in (latest_market or {}),
            "backed_by": "redis",
        }
    except Exception as e:
        status["websocket"] = {"ok": False, "error": str(e)}
        status["data_cache"] = {"ok": False, "error": str(e)}

    overall = all(v.get("ok", False) for v in status.values())
    return {"ok": overall, "app_role": settings.app_role, "execution_mode": settings.execution_mode, "services": status}

@router.get("/test-feeds")
async def test_data_feeds(_: User = Depends(RequireAdmin)):
    """Live-test every external data source and return latency + sample data."""
    results: dict = {}

    # 笏笏 AngelOne SmartStream (replaces yfinance) 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏
    try:
        from bot.angel_feed import is_active, get_all_live_prices
        t0 = time.perf_counter()
        connected = is_active()
        prices = get_all_live_prices()
        elapsed = round((time.perf_counter() - t0) * 1000, 0)
        results["angel_feed"] = {
            "ok": connected,
            "latency_ms": elapsed,
            "connected": connected,
            "prices": {
                k: v for k, v in prices.items()
                if not any(k.endswith(s) for s in ("_open", "_high", "_low", "_prev_close", "_vwap"))
            },
            "note": "Live via WebSocket push 窶・no polling" if connected else "Market closed or credentials not set",
        }
    except Exception as e:
        results["angel_feed"] = {"ok": False, "error": str(e)}

    # 笏笏 NewsAPI 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏
    try:
        from bot.collector import fetch_market_news
        t0 = time.perf_counter()
        news = await fetch_market_news()
        elapsed = round((time.perf_counter() - t0) * 1000, 0)
        results["newsapi"] = {
            "ok": news.get("news_count", 0) > 0,
            "latency_ms": elapsed,
            "articles": news.get("news_count", 0),
            "sample_title": news.get("news", [{}])[0].get("title", "")[:80] if news.get("news") else None,
        }
    except Exception as e:
        results["newsapi"] = {"ok": False, "error": str(e)}

    # 笏笏 AlphaVantage News 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏
    try:
        from bot.collector import fetch_alphavantage_news
        t0 = time.perf_counter()
        av = await fetch_alphavantage_news()
        elapsed = round((time.perf_counter() - t0) * 1000, 0)
        results["alphavantage"] = {
            "ok": av.get("av_news_count", 0) > 0,
            "latency_ms": elapsed,
            "articles": av.get("av_news_count", 0),
        }
    except Exception as e:
        results["alphavantage"] = {"ok": False, "error": str(e)}

    # 笏笏 Claude AI 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏
    try:
        from config import settings
        import anthropic
        t0 = time.perf_counter()
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        msg = await client.messages.create(
            model=settings.claude_model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Reply: OK"}],
        )
        elapsed = round((time.perf_counter() - t0) * 1000, 0)
        results["claude_ai"] = {
            "ok": True,
            "latency_ms": elapsed,
            "model": settings.claude_model,
            "response": msg.content[0].text if msg.content else "",
        }
    except Exception as e:
        results["claude_ai"] = {"ok": False, "error": str(e)}

    # 笏笏 Live cache snapshot 笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏笏
    try:
        from bot.scheduler import _latest_market_data
        results["live_cache"] = {
            "ok": bool(_latest_market_data),
            "keys": len(_latest_market_data),
            "nifty": _latest_market_data.get("nifty"),
            "banknifty": _latest_market_data.get("banknifty"),
            "india_vix": _latest_market_data.get("india_vix"),
            "news_count": _latest_market_data.get("news_count", 0),
        }
    except Exception as e:
        results["live_cache"] = {"ok": False, "error": str(e)}

    return {"results": results, "tested_at": asyncio.get_event_loop().time()}


@router.get("/test-claude")
async def test_claude_api(_: User = Depends(RequireAdmin)):
    """Ping Claude API with a minimal prompt to verify the key and model are working."""
    import time as _time
    from config import settings

    if not settings.anthropic_api_key:
        return {"ok": False, "error": "ANTHROPIC_API_KEY is not set in .env"}

    try:
        import anthropic
        t0 = _time.perf_counter()
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        msg = await client.messages.create(
            model=settings.claude_model,
            max_tokens=30,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        )
        elapsed = round((_time.perf_counter() - t0) * 1000, 0)
        response_text = msg.content[0].text if msg.content else ""
        return {
            "ok": True,
            "model": settings.claude_model,
            "response": response_text,
            "latency_ms": elapsed,
            "input_tokens": msg.usage.input_tokens,
            "output_tokens": msg.usage.output_tokens,
        }
    except anthropic.AuthenticationError:
        return {"ok": False, "error": "API key is invalid or expired"}
    except anthropic.RateLimitError:
        return {"ok": False, "error": "Rate limit hit 窶・key is valid but quota exhausted"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/time")
async def get_server_time():
    """Public endpoint for frontend time synchronisation 窶・no auth required."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    now_utc = datetime.now(timezone.utc)
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    return {
        "utc": now_utc.isoformat(),
        "ist": now_ist.isoformat(),
        "unix": now_utc.timestamp(),
    }






