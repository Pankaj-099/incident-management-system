"""
WebSocket Status API — Phase 6

GET /ws/status → connected clients, pub/sub channel info
"""

import logging
from fastapi import APIRouter
from app.services.ws_manager import ws_manager

logger = logging.getLogger("ims.api.ws_status")
router = APIRouter(prefix="/ws", tags=["websocket"])


@router.get("/status")
async def ws_status():
    """Return current WebSocket connection info."""
    return {
        "connected_clients": ws_manager.connection_count,
        "connections": ws_manager.get_connection_info(),
        "channel": "ims:events",
        "transport": "redis_pubsub",
    }
