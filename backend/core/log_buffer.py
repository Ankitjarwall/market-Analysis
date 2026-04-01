"""
Central log buffer — captures all Python log records and API request logs,
stores them in a circular buffer, and broadcasts via WebSocket in real-time.
"""

import asyncio
import logging
import uuid
from collections import deque
from datetime import datetime, timezone

# ── Circular log buffer (max 500 entries) ─────────────────────────────────────
_log_buffer: deque = deque(maxlen=500)


def _make_entry(level: str, source: str, message: str, details: dict | None = None) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "source": source,
        "message": message,
        "details": details or {},
    }


def add_log_entry(entry: dict) -> None:
    """Append entry to buffer and schedule WebSocket broadcast if loop is running."""
    _log_buffer.append(entry)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_broadcast_log(entry))
    except RuntimeError:
        pass  # No running event loop — just store in buffer


async def _broadcast_log(entry: dict) -> None:
    try:
        from ws.live_feed import manager
        await manager.broadcast({"type": "LOG_ENTRY", "entry": entry})
    except Exception:
        pass


def get_recent_logs(limit: int = 200) -> list[dict]:
    logs = list(_log_buffer)
    return list(reversed(logs[-limit:]))


# ── Source classifier for Python log records ──────────────────────────────────
_SOURCE_MAP = {
    "bot.scheduler": "scheduler",
    "bot.collector": "collector",
    "bot.analyzer": "ai",
    "bot.options_analyzer": "scheduler",
    "websocket.live_feed": "websocket",
    "apscheduler": "scheduler",
    "sqlalchemy.engine": "db",
    "main": "system",
    "healing": "system",
    "auth": "api",
}


def _classify_source(name: str) -> str:
    for prefix, src in _SOURCE_MAP.items():
        if name.startswith(prefix):
            return src
    return "system"


# ── Custom logging.Handler ─────────────────────────────────────────────────────
class WebSocketLogHandler(logging.Handler):
    """
    Attaches to the root logger and forwards structured records to the buffer.

    Filters:
    - sqlalchemy below WARNING (too noisy)
    - apscheduler "Running job" / "executed successfully" (handled by our own job logs)
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Suppress noisy internal sources entirely
            if record.name.startswith("sqlalchemy") and record.levelno < logging.WARNING:
                return
            if record.name.startswith("apscheduler.executors"):
                return  # "Running job / executed successfully / missed" — all internal noise
            if record.name == "watchfiles.main":
                return
            if record.name.startswith("httpx"):
                return  # health-check HTTP logs

            source = _classify_source(record.name)
            message = self.format(record)

            entry = {
                "id": str(uuid.uuid4()),
                "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
                "level": record.levelname,
                "source": source,
                "message": message,
                "details": {"logger": record.name},
            }
            add_log_entry(entry)
        except Exception:
            pass


def setup_ws_log_handler() -> None:
    """Install the WebSocket log handler on the root logger."""
    handler = WebSocketLogHandler()
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(handler)