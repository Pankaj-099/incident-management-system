"""
Unit tests — Phase 6: WebSocket Manager (Redis Pub/Sub + Heartbeat)
"""

import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ── WSConnection tests ─────────────────────────────────────────────────────────

def test_ws_connection_has_client_id():
    from app.services.ws_manager import WSConnection
    mock_ws = MagicMock()
    conn = WSConnection(ws=mock_ws)
    assert isinstance(conn.client_id, str)
    assert len(conn.client_id) > 0


def test_ws_connection_age_is_positive():
    from app.services.ws_manager import WSConnection
    import time
    mock_ws = MagicMock()
    conn = WSConnection(ws=mock_ws)
    time.sleep(0.01)
    assert conn.age_seconds() >= 0


def test_ws_connection_ids_are_unique():
    from app.services.ws_manager import WSConnection
    mock_ws = MagicMock()
    ids = {WSConnection(ws=mock_ws).client_id for _ in range(20)}
    assert len(ids) == 20


# ── ConnectionManager tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_adds_to_registry():
    from app.services.ws_manager import ConnectionManager
    manager = ConnectionManager()

    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()
    mock_ws.client_state = MagicMock()

    conn = await manager.connect(mock_ws)
    assert conn.client_id in manager._connections
    assert manager.connection_count == 1


@pytest.mark.asyncio
async def test_disconnect_removes_from_registry():
    from app.services.ws_manager import ConnectionManager
    manager = ConnectionManager()

    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()

    conn = await manager.connect(mock_ws)
    await manager.disconnect(conn)
    assert manager.connection_count == 0


@pytest.mark.asyncio
async def test_connect_sends_welcome_event():
    from app.services.ws_manager import ConnectionManager
    manager = ConnectionManager()

    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    sent_messages = []
    mock_ws.send_text = AsyncMock(side_effect=lambda m: sent_messages.append(m))

    await manager.connect(mock_ws)

    assert len(sent_messages) == 1
    msg = json.loads(sent_messages[0])
    assert msg["type"] == "connected"
    assert "client_id" in msg["data"]
    assert "server_time" in msg["data"]


@pytest.mark.asyncio
async def test_connection_count_accurate_with_multiple_clients():
    from app.services.ws_manager import ConnectionManager
    manager = ConnectionManager()

    connections = []
    for _ in range(5):
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        conn = await manager.connect(mock_ws)
        connections.append(conn)

    assert manager.connection_count == 5

    await manager.disconnect(connections[0])
    await manager.disconnect(connections[1])
    assert manager.connection_count == 3


@pytest.mark.asyncio
async def test_broadcast_publishes_to_redis():
    from app.services.ws_manager import ConnectionManager
    manager = ConnectionManager()

    mock_redis = AsyncMock()
    published = []
    mock_redis.publish = AsyncMock(side_effect=lambda ch, msg: published.append((ch, msg)))

    with patch("app.services.ws_manager.get_redis", AsyncMock(return_value=mock_redis)):
        await manager.broadcast("signal", {"component_id": "RDBMS_PRIMARY"})

    assert len(published) == 1
    channel, raw = published[0]
    assert channel == "ims:events"
    msg = json.loads(raw)
    assert msg["type"] == "signal"
    assert msg["data"]["component_id"] == "RDBMS_PRIMARY"
    assert "ts" in msg


@pytest.mark.asyncio
async def test_broadcast_falls_back_to_local_on_redis_failure():
    from app.services.ws_manager import ConnectionManager
    from starlette.websockets import WebSocketState
    manager = ConnectionManager()

    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()
    mock_ws.client_state = WebSocketState.CONNECTED

    conn = await manager.connect(mock_ws)
    # Reset send_text call count after welcome message
    mock_ws.send_text.reset_mock()

    with patch("app.services.ws_manager.get_redis", side_effect=Exception("Redis down")):
        await manager.broadcast("test_event", {"key": "value"})

    # Should have received the broadcast via local fallback
    assert mock_ws.send_text.called
    sent = json.loads(mock_ws.send_text.call_args[0][0])
    assert sent["type"] == "test_event"


@pytest.mark.asyncio
async def test_local_broadcast_prunes_dead_connections():
    from app.services.ws_manager import ConnectionManager
    from starlette.websockets import WebSocketState
    manager = ConnectionManager()

    # Healthy connection
    mock_ws_alive = AsyncMock()
    mock_ws_alive.accept = AsyncMock()
    mock_ws_alive.send_text = AsyncMock()
    mock_ws_alive.client_state = WebSocketState.CONNECTED

    # Dead connection — send_text raises
    mock_ws_dead = AsyncMock()
    mock_ws_dead.accept = AsyncMock()
    mock_ws_dead.send_text = AsyncMock(side_effect=Exception("broken pipe"))
    mock_ws_dead.client_state = WebSocketState.CONNECTED

    conn_alive = await manager.connect(mock_ws_alive)
    conn_dead  = await manager.connect(mock_ws_dead)
    mock_ws_alive.send_text.reset_mock()
    mock_ws_dead.send_text.reset_mock()

    assert manager.connection_count == 2

    await manager._local_broadcast_raw(json.dumps({"type": "test", "data": {}, "ts": "now"}))

    # Dead connection should be pruned
    assert manager.connection_count == 1
    assert conn_alive.client_id in manager._connections
    assert conn_dead.client_id not in manager._connections


@pytest.mark.asyncio
async def test_get_connection_info_returns_metadata():
    from app.services.ws_manager import ConnectionManager
    manager = ConnectionManager()

    mock_ws = AsyncMock()
    mock_ws.accept = AsyncMock()
    mock_ws.send_text = AsyncMock()

    conn = await manager.connect(mock_ws)
    info = manager.get_connection_info()

    assert len(info) == 1
    assert info[0]["client_id"] == conn.client_id
    assert "connected_at" in info[0]
    assert "age_seconds" in info[0]
    assert isinstance(info[0]["age_seconds"], (int, float))
