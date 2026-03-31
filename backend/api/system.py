"""
System monitoring endpoints.
GET  /api/system/logs          — recent log buffer
GET  /api/system/status        — DB / Redis / scheduler health
GET  /api/system/test-feeds    — live-test all external data sources
"""

import asyncio
import time

from fastapi import APIRouter, Depends, Query

from auth.middleware import get_current_user, require_roles
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
    logs = get_recent_logs(limit * 2)  # fetch extra then filter
    if source:
        logs = [l for l in logs if l.get("source") == source]
    if level:
        logs = [l for l in logs if l.get("level") == level.upper()]
    return {"logs": logs[:limit], "total": len(logs)}


@router.get("/status")
async def get_system_status(_: User = Depends(get_current_user)):
    """Check Postgres, Redis, scheduler, and WebSocket connection counts."""
    status: dict = {}

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    try:
        from db.connection import AsyncSessionLocal
        from sqlalchemy import text
        t0 = time.perf_counter()
        async with AsyncSessionLocal() as s:
            await s.execute(text("SELECT 1"))
        status["postgres"] = {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as e:
        status["postgres"] = {"ok": False, "error": str(e)}

    # ── Redis ─────────────────────────────────────────────────────────────────
    try:
        import redis.asyncio as aioredis
        from config import settings
        t0 = time.perf_counter()
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.aclose()
        status["redis"] = {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000, 1)}
    except Exception as e:
        status["redis"] = {"ok": False, "error": str(e)}

    # ── Scheduler ────────────────────────────────────────────────────────────
    try:
        from bot.scheduler import _scheduler
        status["scheduler"] = {
            "ok": _scheduler is not None and _scheduler.running,
            "jobs": len(_scheduler.get_jobs()) if _scheduler else 0,
        }
    except Exception as e:
        status["scheduler"] = {"ok": False, "error": str(e)}

    # ── WebSocket connections ─────────────────────────────────────────────────
    try:
        from websocket.live_feed import _connections
        total = sum(len(v) for v in _connections.values())
        status["websocket"] = {"ok": True, "connections": total, "users": len(_connections)}
    except Exception as e:
        status["websocket"] = {"ok": False, "error": str(e)}

    # ── Cache ─────────────────────────────────────────────────────────────────
    try:
        from bot.scheduler import _latest_market_data
        status["data_cache"] = {
            "ok": bool(_latest_market_data),
            "keys": len(_latest_market_data),
            "has_nifty": "nifty" in _latest_market_data,
        }
    except Exception as e:
        status["data_cache"] = {"ok": False, "error": str(e)}

    overall = all(v.get("ok", False) for v in status.values())
    return {"ok": overall, "services": status}


@router.get("/test-feeds")
async def test_data_feeds(_: User = Depends(RequireAdmin)):
    """Live-test every external data source and return latency + sample data."""
    results: dict = {}

    # ── yfinance ──────────────────────────────────────────────────────────────
    try:
        import yfinance as yf
        t0 = time.perf_counter()
        raw = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: yf.download(
                "^NSEI ^GSPC GC=F INR=X ^INDIAVIX",
                period="1d", interval="1m",
                group_by="ticker", auto_adjust=True, progress=False,
            ),
        )
        elapsed = round((time.perf_counter() - t0) * 1000, 0)
        prices = {}
        sym_map = {"^NSEI": "nifty", "^GSPC": "sp500", "GC=F": "gold", "INR=X": "usd_inr", "^INDIAVIX": "india_vix"}
        if not raw.empty and hasattr(raw.columns, "get_level_values") and len(raw.columns.names) > 1:
            level0 = raw.columns.get_level_values(0)
            for sym, name in sym_map.items():
                try:
                    if sym in level0:
                        s = raw[sym]["Close"]
                        val = float(s.dropna().iloc[-1])
                        if val == val:
                            prices[name] = round(val, 2)
                except Exception:
                    pass
        results["yfinance"] = {
            "ok": bool(prices),
            "latency_ms": elapsed,
            "shape": f"{raw.shape[0]}r × {raw.shape[1]}c",
            "prices": prices,
        }
    except Exception as e:
        results["yfinance"] = {"ok": False, "error": str(e)}

    # ── NSE FII/DII ───────────────────────────────────────────────────────────
    try:
        import httpx
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=10) as client:
            await client.get("https://www.nseindia.com/",
                             headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
            resp = await client.get(
                "https://www.nseindia.com/api/fiidiiTradeReact",
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com/"},
            )
        elapsed = round((time.perf_counter() - t0) * 1000, 0)
        data = resp.json() if resp.status_code == 200 else None
        results["nse_fii"] = {
            "ok": resp.status_code == 200,
            "latency_ms": elapsed,
            "http_status": resp.status_code,
            "rows": len(data) if isinstance(data, list) else 0,
            "sample": data[0] if isinstance(data, list) and data else None,
        }
    except Exception as e:
        results["nse_fii"] = {"ok": False, "error": str(e)}

    # ── NSE Options Chain (PCR) ────────────────────────────────────────────────
    try:
        import httpx
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            await client.get("https://www.nseindia.com/",
                             headers={"User-Agent": "Mozilla/5.0", "Accept": "text/html"})
            resp = await client.get(
                "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY",
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json",
                    "Referer": "https://www.nseindia.com/",
                },
            )
        elapsed = round((time.perf_counter() - t0) * 1000, 0)
        pcr = None
        if resp.status_code == 200:
            d = resp.json()
            filtered = d.get("filtered", {})
            pe_oi = filtered.get("PE", {}).get("totOI", 0) if isinstance(filtered.get("PE"), dict) else 0
            ce_oi = filtered.get("CE", {}).get("totOI", 0) if isinstance(filtered.get("CE"), dict) else 0
            if pe_oi and ce_oi:
                pcr = round(pe_oi / ce_oi, 3)
        results["nse_pcr"] = {
            "ok": resp.status_code == 200,
            "latency_ms": elapsed,
            "http_status": resp.status_code,
            "pcr": pcr,
        }
    except Exception as e:
        results["nse_pcr"] = {"ok": False, "error": str(e)}

    # ── Nifty Indices (PE/PB) ─────────────────────────────────────────────────
    try:
        import httpx
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.post(
                "https://www.niftyindices.com/Backpage.aspx/getHistoricaldatatabletoday",
                json={"name": "NIFTY 50", "startDate": "", "endDate": ""},
                headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json",
                         "Referer": "https://www.niftyindices.com/"},
            )
        elapsed = round((time.perf_counter() - t0) * 1000, 0)
        pe = None
        if resp.status_code == 200:
            rows = resp.json().get("d", [])
            if rows:
                pe = rows[0].get("PE")
        results["nifty_pe"] = {
            "ok": resp.status_code == 200,
            "latency_ms": elapsed,
            "http_status": resp.status_code,
            "pe": pe,
        }
    except Exception as e:
        results["nifty_pe"] = {"ok": False, "error": str(e)}

    # ── Cache snapshot ────────────────────────────────────────────────────────
    try:
        from bot.scheduler import _latest_market_data
        results["live_cache"] = {
            "ok": bool(_latest_market_data),
            "keys": len(_latest_market_data),
            "nifty": _latest_market_data.get("nifty"),
            "sp500": _latest_market_data.get("sp500"),
            "gold": _latest_market_data.get("gold"),
            "usd_inr": _latest_market_data.get("usd_inr"),
            "india_vix": _latest_market_data.get("india_vix"),
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
        return {"ok": False, "error": "Rate limit hit — key is valid but quota exhausted"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/time")
async def get_server_time():
    """Public endpoint for frontend time synchronisation — no auth required."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    now_utc = datetime.now(timezone.utc)
    now_ist = datetime.now(ZoneInfo("Asia/Kolkata"))
    return {
        "utc": now_utc.isoformat(),
        "ist": now_ist.isoformat(),
        "unix": now_utc.timestamp(),
    }