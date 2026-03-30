"""
Market Intelligence Platform — FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop background services with the application."""
    logger.info("Starting Market Intelligence Platform...")

    # Start APScheduler
    try:
        from bot.scheduler import start_scheduler
        await start_scheduler()
        logger.info("Scheduler started")
    except Exception as exc:
        logger.warning(f"Scheduler failed to start: {exc}")

    # Start self-healing watchdog
    try:
        from healing.watchdog import start_watchdog
        await start_watchdog()
        logger.info("Watchdog started")
    except Exception as exc:
        logger.warning(f"Watchdog failed to start: {exc}")

    yield

    # Shutdown
    logger.info("Shutting down...")
    try:
        from bot.scheduler import stop_scheduler
        await stop_scheduler()
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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register routers ──
from auth.router import router as auth_router
from api.market import router as market_router
from api.signals import router as signals_router
from api.trades import router as trades_router
from api.predictions import router as predictions_router
from api.admin import router as admin_router
from api.self_heal import router as heal_router
from websocket.live_feed import router as ws_router

app.include_router(auth_router)
app.include_router(market_router)
app.include_router(signals_router)
app.include_router(trades_router)
app.include_router(predictions_router)
app.include_router(admin_router)
app.include_router(heal_router)
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0", "environment": settings.environment}


@app.get("/")
async def root():
    return {
        "name": "Market Intelligence Platform API",
        "docs": "/docs",
        "health": "/health",
    }
