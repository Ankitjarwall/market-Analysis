"""
WebSocket server - broadcasts live market data and trade alerts to connected clients.

In split-runtime mode, events are published through Redis so market/execution workers
can push updates to the API process that owns browser WebSocket connections.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

_connections: dict[str, list[WebSocket]] = {}
_EVENT_CHANNEL = "market-platform:events"
_LATEST_MARKET_KEY = "market-platform:latest-market"
_redis_client: redis.Redis | None = None
_listener_task: asyncio.Task | None = None
_listener_stop: asyncio.Event | None = None


async def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def _cache_latest_market(data: dict):
    try:
        client = await _get_redis()
        await client.set(_LATEST_MARKET_KEY, json.dumps(data, default=str), ex=300)
    except Exception as exc:
        logger.debug("Failed to cache latest market snapshot: %s", exc)


async def get_latest_market_snapshot() -> dict | None:
    try:
        client = await _get_redis()
        raw = await client.get(_LATEST_MARKET_KEY)
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.debug("Failed to load latest market snapshot from Redis: %s", exc)
        return None


async def _publish_event(event: dict, user_id: str | None = None):
    payload = {
        "emitter_id": settings.service_instance_id,
        "user_id": str(user_id) if user_id else None,
        "event": event,
    }
    try:
        client = await _get_redis()
        await client.publish(_EVENT_CHANNEL, json.dumps(payload, default=str))
    except Exception as exc:
        logger.warning("Failed to publish WebSocket event to Redis: %s", exc)


class ConnectionManager:
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        _connections.setdefault(user_id, []).append(websocket)
        logger.info(
            "WebSocket connected: user=%s total=%s",
            user_id,
            sum(len(v) for v in _connections.values()),
        )

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in _connections:
            _connections[user_id] = [ws for ws in _connections[user_id] if ws != websocket]
            if not _connections[user_id]:
                del _connections[user_id]

    async def send_to_user(self, user_id: str, event: dict):
        await self._emit(event, user_id=str(user_id))

    async def broadcast(self, event: dict):
        await self._emit(event)

    async def _send_to_user_local(self, user_id: str, event: dict):
        conns = _connections.get(str(user_id), [])
        dead = []
        for ws in conns:
            try:
                await ws.send_text(json.dumps(event, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, str(user_id))

    async def _broadcast_local(self, event: dict):
        for user_id in list(_connections.keys()):
            await self._send_to_user_local(user_id, event)

    async def _emit(self, event: dict, user_id: str | None = None):
        if user_id:
            await self._send_to_user_local(str(user_id), event)
        else:
            await self._broadcast_local(event)
        await _publish_event(event, user_id=user_id)

    async def dispatch_bus_message(self, envelope: dict):
        event = envelope.get("event") or {}
        user_id = envelope.get("user_id")
        if user_id:
            await self._send_to_user_local(str(user_id), event)
        else:
            await self._broadcast_local(event)

    async def broadcast_market_update(self, data: dict):
        await _cache_latest_market(data)
        await self._emit(
            {
                "type": "PRICE_UPDATE",
                "data": data,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def broadcast_bot_activity(self, message: str, level: str = "INFO"):
        await self._emit(
            {
                "type": "BOT_ACTIVITY",
                "message": message,
                "level": level,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def broadcast_signal(self, signal: dict):
        await self._emit(
            {
                "type": "SIGNAL_GENERATED",
                "signal": signal,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def send_trade_event(self, user_id: str, event_type: str, payload: dict):
        await self._emit(
            {
                "type": event_type,
                "payload": payload,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
            user_id=str(user_id),
        )

    async def broadcast_heal_warning(self, warning: dict):
        await self._emit(
            {
                "type": "HEAL_WARNING",
                "warning": warning,
                "ts": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def broadcast_log_entry(self, entry: dict):
        await self._emit({"type": "LOG_ENTRY", "entry": entry})


manager = ConnectionManager()


async def _event_listener_loop():
    pubsub = None
    try:
        client = await _get_redis()
        pubsub = client.pubsub()
        await pubsub.subscribe(_EVENT_CHANNEL)
        logger.info("Redis WebSocket listener subscribed to %s", _EVENT_CHANNEL)

        while _listener_stop and not _listener_stop.is_set():
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if not message:
                continue
            try:
                envelope = json.loads(message.get("data", "{}"))
            except json.JSONDecodeError:
                continue
            if envelope.get("emitter_id") == settings.service_instance_id:
                continue
            await manager.dispatch_bus_message(envelope)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning("Redis WebSocket listener stopped unexpectedly: %s", exc)
    finally:
        if pubsub is not None:
            try:
                await pubsub.unsubscribe(_EVENT_CHANNEL)
                await pubsub.aclose()
            except Exception:
                pass


async def start_event_listener():
    global _listener_task, _listener_stop
    if _listener_task and not _listener_task.done():
        return
    _listener_stop = asyncio.Event()
    _listener_task = asyncio.create_task(_event_listener_loop())


async def stop_event_listener():
    global _listener_task, _listener_stop, _redis_client
    if _listener_stop:
        _listener_stop.set()
    if _listener_task:
        _listener_task.cancel()
        try:
            await _listener_task
        except asyncio.CancelledError:
            pass
        _listener_task = None
    _listener_stop = None
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception:
            pass
        _redis_client = None


def _validate_ws_token(token: str) -> str | None:
    """Validate JWT and return user_id or None."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


@router.websocket("/ws/market")
async def websocket_market(websocket: WebSocket, token: str = ""):
    user_id = _validate_ws_token(token)
    if not user_id:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    await manager.connect(websocket, user_id)
    try:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "CONNECTED",
                    "message": "Connected to Market Intelligence Platform live feed",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "app_role": settings.app_role,
                    "execution_mode": settings.execution_mode,
                }
            )
        )

        try:
            latest_market = None
            from bot.scheduler import _latest_market_data

            if _latest_market_data:
                latest_market = _latest_market_data
            if latest_market is None:
                latest_market = await get_latest_market_snapshot()
            if latest_market:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "PRICE_UPDATE",
                            "data": latest_market,
                            "ts": datetime.now(timezone.utc).isoformat(),
                        },
                        default=str,
                    )
                )
        except Exception:
            pass

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info("WebSocket disconnected: user=%s", user_id)


