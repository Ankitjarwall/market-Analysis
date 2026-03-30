"""
Watchdog — monitors all services every 30 seconds.
Classifies errors by severity and triggers appropriate responses.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

SERVICES = [
    {"name": "fastapi", "type": "http", "url": "http://localhost:8000/health"},
    {"name": "postgres", "type": "db"},
    {"name": "redis", "type": "redis"},
    {"name": "data_feed", "type": "custom"},
]

SEVERITY_RULES = {
    1: ["DeprecationWarning", "slow_response"],
    2: ["ConnectionError", "Timeout", "ProcessCrashed"],
    3: ["SyntaxError", "ImportError", "AttributeError"],
    4: ["PermissionError", "SecurityError", "DBMigration", "AuthChange"],
}

_watchdog_running = False


async def start_watchdog():
    global _watchdog_running
    _watchdog_running = True
    logger.info("Watchdog started")


async def run_watchdog_check():
    """Called every 30 seconds by the scheduler."""
    from db.connection import AsyncSessionLocal
    from db.models import SystemHealthLog

    results = await asyncio.gather(
        _check_http("fastapi", "http://localhost:8000/health"),
        _check_db(),
        _check_redis(),
        _check_data_feed(),
        return_exceptions=True,
    )

    service_names = ["fastapi", "postgres", "redis", "data_feed"]

    async with AsyncSessionLocal() as session:
        for name, result in zip(service_names, results):
            if isinstance(result, Exception):
                status = "ERROR"
                details = {"error": str(result)}
                response_ms = None
            else:
                status = result.get("status", "OK")
                details = result.get("details", {})
                response_ms = result.get("response_ms")

            log = SystemHealthLog(
                service=name,
                status=status,
                response_time_ms=response_ms,
                details=details,
            )
            session.add(log)

            if status in ("ERROR", "CRASHED"):
                await _handle_service_error(name, status, details)

        await session.commit()


async def _check_http(name: str, url: str) -> dict:
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(url)
        elapsed = int((time.monotonic() - start) * 1000)
        if resp.status_code == 200:
            return {"status": "OK", "response_ms": elapsed}
        return {"status": "WARNING", "response_ms": elapsed, "details": {"code": resp.status_code}}
    except Exception as exc:
        return {"status": "ERROR", "details": {"error": str(exc)}}


async def _check_db() -> dict:
    try:
        from db.connection import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"status": "OK"}
    except Exception as exc:
        return {"status": "ERROR", "details": {"error": str(exc)}}


async def _check_redis() -> dict:
    try:
        import redis.asyncio as aioredis
        from config import settings
        client = aioredis.from_url(settings.redis_url, socket_timeout=3)
        await client.ping()
        await client.aclose()
        return {"status": "OK"}
    except Exception as exc:
        return {"status": "ERROR", "details": {"error": str(exc)}}


async def _check_data_feed() -> dict:
    """Check that market data was collected recently."""
    try:
        from db.connection import AsyncSessionLocal
        from db.models import DailyMarketSnapshot
        from sqlalchemy import select
        from datetime import timedelta

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(DailyMarketSnapshot)
                .order_by(DailyMarketSnapshot.created_at.desc())
                .limit(1)
            )
            snapshot = result.scalar_one_or_none()

        if not snapshot:
            return {"status": "WARNING", "details": {"message": "No snapshots yet"}}

        age_minutes = (datetime.now(timezone.utc) - snapshot.created_at).total_seconds() / 60
        if age_minutes > 10:
            return {"status": "WARNING", "details": {"age_minutes": age_minutes}}
        return {"status": "OK", "details": {"age_minutes": round(age_minutes, 1)}}
    except Exception as exc:
        return {"status": "ERROR", "details": {"error": str(exc)}}


async def _handle_service_error(service: str, status: str, details: dict):
    """Handle a detected service error."""
    from db.connection import AsyncSessionLocal
    from db.models import Error
    from healing.classifier import classify_error

    error_type = details.get("error", "ServiceUnavailable")
    severity = classify_error(service, error_type)

    async with AsyncSessionLocal() as session:
        error = Error(
            service=service,
            error_type=error_type,
            severity=severity,
            log_context=str(details),
            system_state=details,
        )
        session.add(error)
        await session.commit()
        await session.refresh(error)

    if severity == 1:
        logger.warning(f"Severity 1 ({service}): {error_type}")
    elif severity == 2:
        logger.warning(f"Severity 2 ({service}): auto-restart attempted")
        # Could trigger process restart here
    elif severity == 3:
        logger.error(f"Severity 3 ({service}): requesting AI fix")
        from healing.ai_fixer import request_ai_fix
        asyncio.create_task(request_ai_fix(error.id))
    elif severity == 4:
        logger.critical(f"Severity 4 ({service}): HUMAN REQUIRED — {error_type}")
        from websocket.live_feed import manager
        await manager.broadcast_heal_warning({
            "severity": 4,
            "service": service,
            "error": error_type,
            "message": "⚠️ CRITICAL: Manual intervention required",
        })
