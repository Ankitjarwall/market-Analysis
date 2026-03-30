"""
WebSocket server — broadcasts live market data and trade alerts to connected clients.

Events broadcast:
  PRICE_UPDATE, SIGNAL_GENERATED, TRADE_OPENED, TRADE_ALERT_T1,
  TRADE_ALERT_T2, TRADE_ALERT_SL, BOT_ACTIVITY, HEAL_WARNING, PNL_UPDATE
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt

from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Active connections: {user_id: [WebSocket, ...]}
_connections: dict[str, list[WebSocket]] = {}


class ConnectionManager:
    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        if user_id not in _connections:
            _connections[user_id] = []
        _connections[user_id].append(websocket)
        logger.info(f"WebSocket connected: user={user_id}, total={sum(len(v) for v in _connections.values())}")

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in _connections:
            _connections[user_id] = [ws for ws in _connections[user_id] if ws != websocket]
            if not _connections[user_id]:
                del _connections[user_id]

    async def send_to_user(self, user_id: str, event: dict):
        """Send event to all connections for a specific user."""
        conns = _connections.get(str(user_id), [])
        dead = []
        for ws in conns:
            try:
                await ws.send_text(json.dumps(event, default=str))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, str(user_id))

    async def broadcast(self, event: dict):
        """Broadcast event to ALL connected users."""
        all_users = list(_connections.keys())
        for user_id in all_users:
            await self.send_to_user(user_id, event)

    async def broadcast_market_update(self, data: dict):
        await self.broadcast({"type": "PRICE_UPDATE", "data": data, "ts": datetime.now(timezone.utc).isoformat()})

    async def broadcast_bot_activity(self, message: str, level: str = "INFO"):
        await self.broadcast({
            "type": "BOT_ACTIVITY",
            "message": message,
            "level": level,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    async def broadcast_signal(self, signal: dict):
        await self.broadcast({"type": "SIGNAL_GENERATED", "signal": signal, "ts": datetime.now(timezone.utc).isoformat()})

    async def send_trade_event(self, user_id: str, event_type: str, payload: dict):
        await self.send_to_user(str(user_id), {
            "type": event_type,
            "payload": payload,
            "ts": datetime.now(timezone.utc).isoformat(),
        })

    async def broadcast_heal_warning(self, warning: dict):
        await self.broadcast({"type": "HEAL_WARNING", "warning": warning, "ts": datetime.now(timezone.utc).isoformat()})


manager = ConnectionManager()


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
        # Send a welcome event with current state
        await websocket.send_text(json.dumps({
            "type": "CONNECTED",
            "message": "Connected to Market Intelligence Platform live feed",
            "ts": datetime.now(timezone.utc).isoformat(),
        }))

        # Keep connection alive — receive pings
        while True:
            data = await websocket.receive_text()
            # Handle ping/pong
            try:
                msg = json.loads(data)
                if msg.get("type") == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id)
        logger.info(f"WebSocket disconnected: user={user_id}")
