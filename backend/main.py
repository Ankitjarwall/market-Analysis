"""
Market Intelligence Platform - FastAPI application entry point.
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from core.log_buffer import add_log_entry, setup_ws_log_handler

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

# Install WebSocket log handler (captures all Python logger output)
setup_ws_log_handler()


def _role_in(*roles: str) -> bool:
    return settings.app_role in roles


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop background services with the application."""
    logger.info(
        "Starting Market Intelligence Platform role=%s execution_mode=%s instance=%s",
        settings.app_role,
        settings.execution_mode,
        settings.service_instance_id,
    )

    if _role_in("all", "api"):
        try:
            from ws.live_feed import start_event_listener

            await start_event_listener()
            logger.info("Redis event listener started")
        except Exception as exc:
            logger.warning("Redis event listener failed to start: %s", exc)

    if _role_in("all", "market_worker"):
        try:
            from bot.scheduler import start_scheduler

            await start_scheduler()
            logger.info("Scheduler started")
        except Exception as exc:
            logger.warning("Scheduler failed to start: %s", exc)

    yield

    logger.info("Shutting down role=%s", settings.app_role)

    if _role_in("all", "market_worker"):
        try:
            from bot.scheduler import stop_scheduler

            await stop_scheduler()
        except Exception:
            pass

    if _role_in("all", "api"):
        try:
            from ws.live_feed import stop_event_listener

            await stop_event_listener()
        except Exception:
            pass


app = FastAPI(
    title="Market Intelligence Platform",
    description="AI-powered Nifty 50 options trading intelligence system",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logger_middleware(request: Request, call_next):
    skip_paths = {"/health", "/"}
    path = request.url.path
    if path in skip_paths or path.startswith("/ws/"):
        return await call_next(request)

    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - start) * 1000, 1)

    level = "ERROR" if response.status_code >= 500 else "WARN" if response.status_code >= 400 else "INFO"
    msg = f"{request.method} {path} -> {response.status_code} ({elapsed_ms}ms)"

    add_log_entry(
        {
            "id": str(uuid.uuid4()),
            "ts": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "level": level,
            "source": "api",
            "message": msg,
            "details": {
                "method": request.method,
                "path": path,
                "query": str(request.url.query) or None,
                "status": response.status_code,
                "duration_ms": elapsed_ms,
            },
        }
    )
    return response


from auth.router import router as auth_router
from api.admin import router as admin_router
from api.market import router as market_router
from api.predictions import router as predictions_router
from api.self_heal import router as self_heal_router
from api.signals import router as signals_router
from api.system import router as system_router
from api.trades import router as trades_router
from ws.live_feed import router as ws_router

app.include_router(auth_router)
app.include_router(market_router)
app.include_router(signals_router)
app.include_router(trades_router)
app.include_router(predictions_router)
app.include_router(admin_router)
app.include_router(system_router)
app.include_router(self_heal_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": "1.0.0",
        "environment": settings.environment,
        "app_role": settings.app_role,
        "execution_mode": settings.execution_mode,
    }


@app.get("/")
async def root():
    return {
        "name": "Market Intelligence Platform API",
        "docs": "/docs",
        "health": "/health",
        "app_role": settings.app_role,
        "execution_mode": settings.execution_mode,
    }
