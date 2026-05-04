"""
WebSocket Manager — Phase 6 (Redis Pub/Sub fanout + heartbeat)

Any service calls ws_manager.broadcast(event_type, data)
  → Redis PUBLISH "ims:events"
  → All worker processes subscribed receive the message
  → Each worker pushes to its local WebSocket connections

Additional: per-connection heartbeat ping every 30s, graceful shutdown.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import WebSocket
from starlette.websockets import WebSocketState

logger = logging.getLogger("ims.ws")

_CHANNEL       = "ims:events"
_HEARTBEAT_SEC = 30


@dataclass
class WSConnection:
    ws: WebSocket
    client_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    connected_at: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)

    def age_seconds(self) -> float:
        return time.time() - self.connected_at


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, WSConnection] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task | None = None
        self._pubsub_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name="ws-heartbeat")
        self._pubsub_task    = asyncio.create_task(self._pubsub_listener(), name="ws-pubsub")
        logger.info("WS manager started (channel=%s, heartbeat=%ds)", _CHANNEL, _HEARTBEAT_SEC)

    async def stop(self) -> None:
        for task in [self._heartbeat_task, self._pubsub_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        async with self._lock:
            for conn in list(self._connections.values()):
                try:
                    await conn.ws.close(code=1001)
                except Exception:
                    pass
            self._connections.clear()
        logger.info("WS manager stopped")

    async def connect(self, ws: WebSocket) -> WSConnection:
        await ws.accept()
        conn = WSConnection(ws=ws)
        async with self._lock:
            self._connections[conn.client_id] = conn
        await self._send_to(conn, "connected", {
            "client_id": conn.client_id,
            "server_time": datetime.now(timezone.utc).isoformat(),
            "active_connections": len(self._connections),
        })
        logger.info("WS client %s connected (total=%d)", conn.client_id, len(self._connections))
        return conn

    async def disconnect(self, conn: WSConnection) -> None:
        async with self._lock:
            self._connections.pop(conn.client_id, None)
        logger.info("WS client %s disconnected (total=%d)", conn.client_id, len(self._connections))

    async def broadcast(self, event_type: str, data: dict) -> None:
        message = json.dumps({
            "type": event_type,
            "data": data,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        try:
            from app.db.redis import get_redis
            redis = await get_redis()
            await redis.publish(_CHANNEL, message)
        except Exception as exc:
            logger.warning("Redis publish failed, local fallback: %s", exc)
            await self._local_broadcast_raw(message)

    async def _local_broadcast_raw(self, message: str) -> None:
        async with self._lock:
            connections = list(self._connections.values())
        dead: list[str] = []
        for conn in connections:
            try:
                if conn.ws.client_state == WebSocketState.CONNECTED:
                    await conn.ws.send_text(message)
            except Exception:
                dead.append(conn.client_id)
        if dead:
            async with self._lock:
                for cid in dead:
                    self._connections.pop(cid, None)

    async def _send_to(self, conn: WSConnection, event_type: str, data: dict) -> None:
        try:
            await conn.ws.send_text(json.dumps({
                "type": event_type,
                "data": data,
                "ts": datetime.now(timezone.utc).isoformat(),
            }))
        except Exception:
            pass

    async def _pubsub_listener(self) -> None:
        while True:
            try:
                from app.db.redis import get_redis
                redis = await get_redis()
                pubsub = redis.pubsub()
                await pubsub.subscribe(_CHANNEL)
                logger.info("Subscribed to Redis channel %s", _CHANNEL)
                async for msg in pubsub.listen():
                    if msg["type"] == "message":
                        raw = msg["data"]
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8")
                        await self._local_broadcast_raw(raw)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Pub/sub error: %s — reconnecting in 2s", exc)
                await asyncio.sleep(2)

    async def _heartbeat_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(_HEARTBEAT_SEC)
                async with self._lock:
                    connections = list(self._connections.values())
                dead: list[str] = []
                for conn in connections:
                    try:
                        if conn.ws.client_state == WebSocketState.CONNECTED:
                            await conn.ws.send_text(json.dumps({
                                "type": "ping",
                                "data": {"ts": datetime.now(timezone.utc).isoformat()},
                                "ts": datetime.now(timezone.utc).isoformat(),
                            }))
                            conn.last_ping = time.time()
                        else:
                            dead.append(conn.client_id)
                    except Exception:
                        dead.append(conn.client_id)
                if dead:
                    async with self._lock:
                        for cid in dead:
                            self._connections.pop(cid, None)
                    logger.info("Heartbeat pruned %d dead connections", len(dead))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Heartbeat error: %s", exc)

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    def get_connection_info(self) -> list[dict]:
        return [
            {
                "client_id": c.client_id,
                "connected_at": datetime.fromtimestamp(c.connected_at, tz=timezone.utc).isoformat(),
                "age_seconds": round(c.age_seconds()),
            }
            for c in self._connections.values()
        ]


ws_manager = ConnectionManager()
