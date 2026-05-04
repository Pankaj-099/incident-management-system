"""
Signal Ingestion API — Phase 6 update
WebSocket uses new WSConnection from enhanced manager.
"""

import logging
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect, HTTPException
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.schemas.signal import IngestSignalRequest, IngestSignalResponse
from app.services.signal_queue import enqueue_signal, queue_depth, QueuedSignal
from app.services.sqlite_sink import get_recent_signals
from app.services.metrics import get_throughput_snapshot
from app.services.ws_manager import ws_manager

logger = logging.getLogger("ims.api.ingest")
router = APIRouter(tags=["ingestion"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/ingest", response_model=IngestSignalResponse, status_code=202)
@limiter.limit("2000/minute")
async def ingest_signal(request: Request, body: IngestSignalRequest):
    signal = QueuedSignal(
        signal_id=body.signal_id,
        component_id=body.component_id,
        component_type=body.component_type.value,
        severity=body.severity.value,
        message=body.message,
        payload=body.payload,
    )
    accepted = await enqueue_signal(signal)
    if not accepted:
        raise HTTPException(
            status_code=503,
            detail={"error": "queue_full", "message": "Signal queue at capacity.", "queue_depth": queue_depth()},
        )
    return IngestSignalResponse(
        accepted=True,
        signal_id=body.signal_id,
        queue_depth=queue_depth(),
        message="Signal accepted for processing",
    )


@router.post("/ingest/batch", status_code=202)
@limiter.limit("200/minute")
async def ingest_batch(request: Request, signals: list[IngestSignalRequest]):
    if len(signals) > 500:
        raise HTTPException(status_code=400, detail="Batch size cannot exceed 500")
    accepted = rejected = 0
    for body in signals:
        signal = QueuedSignal(
            signal_id=body.signal_id,
            component_id=body.component_id,
            component_type=body.component_type.value,
            severity=body.severity.value,
            message=body.message,
            payload=body.payload,
        )
        if await enqueue_signal(signal):
            accepted += 1
        else:
            rejected += 1
    return {"accepted": accepted, "rejected": rejected, "queue_depth": queue_depth()}


@router.get("/signals/recent")
async def recent_signals(limit: int = 100):
    if limit > 500:
        limit = 500
    rows = await get_recent_signals(limit)
    return {"signals": rows, "count": len(rows)}


@router.get("/metrics")
async def metrics():
    snapshot = await get_throughput_snapshot()
    snapshot["queue_depth_live"] = queue_depth()
    snapshot["ws_connections"] = ws_manager.connection_count
    snapshot["ws_clients"] = ws_manager.get_connection_info()
    return snapshot


@router.websocket("/ws/signals")
async def ws_signals(websocket: WebSocket):
    conn = await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(conn)
    except Exception:
        await ws_manager.disconnect(conn)
