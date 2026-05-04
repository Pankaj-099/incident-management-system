"""
Work Items API — Phase 4 update

New endpoints:
  PATCH /work-items/{id}/transition   → state machine transition
  GET   /work-items/{id}/transitions  → allowed transitions from current state
  GET   /alert-strategies             → all registered alerting strategies
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.work_item_service import get_work_item, list_work_items, get_stats
from app.services.sqlite_sink import get_signals_for_work_item
from app.services.dashboard_cache import (
    get_cached_work_items, set_cached_work_items,
    get_cached_stats, set_cached_stats,
)
from app.services.workflow_engine import (
    transition_work_item, describe_allowed_transitions, RCARequiredError,
)
from app.services.state_machine import InvalidTransitionError
from app.services.alert_strategy import AlertStrategyFactory
from app.services.ws_manager import ws_manager

logger = logging.getLogger("ims.api.work_items")
router = APIRouter(prefix="/work-items", tags=["work-items"])
alert_router = APIRouter(tags=["alerting"])


def _wi_to_dict(wi) -> dict:
    return {
        "id": wi.id,
        "component_id": wi.component_id,
        "component_type": wi.component_type,
        "status": wi.status,
        "priority": wi.priority,
        "title": wi.title,
        "description": wi.description,
        "signal_count": wi.signal_count,
        "mttr_seconds": wi.mttr_seconds,
        "created_at": wi.created_at.isoformat() if wi.created_at else None,
        "updated_at": wi.updated_at.isoformat() if wi.updated_at else None,
        "resolved_at": wi.resolved_at.isoformat() if wi.resolved_at else None,
        "closed_at": wi.closed_at.isoformat() if wi.closed_at else None,
    }


@router.get("")
async def list_work_items_endpoint(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    use_cache = (status is None and priority is None and offset == 0 and limit == 50)
    if use_cache:
        cached = await get_cached_work_items()
        if cached is not None:
            return {"items": cached, "total": len(cached), "cached": True}
    items, total = await list_work_items(db, status=status, priority=priority,
                                          limit=limit, offset=offset)
    dicts = [_wi_to_dict(wi) for wi in items]
    if use_cache:
        await set_cached_work_items(dicts)
    return {"items": dicts, "total": total, "cached": False}


@router.get("/stats")
async def work_item_stats(db: AsyncSession = Depends(get_db)):
    cached = await get_cached_stats()
    if cached:
        return {**cached, "cached": True}
    stats = await get_stats(db)
    await set_cached_stats(stats)
    return {**stats, "cached": False}


@router.get("/{work_item_id}")
async def get_work_item_endpoint(work_item_id: str, db: AsyncSession = Depends(get_db)):
    wi = await get_work_item(db, work_item_id)
    if not wi:
        raise HTTPException(status_code=404, detail="Work item not found")
    return _wi_to_dict(wi)


@router.get("/{work_item_id}/signals")
async def get_work_item_signals(work_item_id: str, db: AsyncSession = Depends(get_db)):
    wi = await get_work_item(db, work_item_id)
    if not wi:
        raise HTTPException(status_code=404, detail="Work item not found")
    signals = await get_signals_for_work_item(work_item_id)
    return {"work_item_id": work_item_id, "signals": signals, "count": len(signals)}


@router.get("/{work_item_id}/transitions")
async def get_allowed_transitions(work_item_id: str, db: AsyncSession = Depends(get_db)):
    wi = await get_work_item(db, work_item_id)
    if not wi:
        raise HTTPException(status_code=404, detail="Work item not found")
    transitions = describe_allowed_transitions(wi.status)
    return {
        "work_item_id": work_item_id,
        "current_status": wi.status,
        "transitions": transitions,
    }


class TransitionRequest(BaseModel):
    status: str
    actor: str | None = None


@router.patch("/{work_item_id}/transition")
async def transition_endpoint(
    work_item_id: str,
    body: TransitionRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        wi = await transition_work_item(
            db=db,
            work_item_id=work_item_id,
            target_status=body.status,
            actor=body.actor,
        )
        return {"success": True, "work_item": _wi_to_dict(wi), "message": f"Transitioned to {wi.status}"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidTransitionError as e:
        raise HTTPException(status_code=422, detail={
            "error": "invalid_transition", "from": e.from_state,
            "to": e.to_state, "reason": e.reason,
        })
    except RCARequiredError as e:
        raise HTTPException(status_code=422, detail={
            "error": "rca_required", "message": str(e),
        })


@alert_router.get("/alert-strategies")
async def get_alert_strategies():
    return {"strategies": AlertStrategyFactory.all_strategies()}


@router.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    conn = await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(conn)
    except Exception:
        await ws_manager.disconnect(conn)
