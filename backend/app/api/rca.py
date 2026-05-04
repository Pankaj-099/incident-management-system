"""
RCA API — Phase 5

POST /work-items/{id}/rca      → submit / re-submit RCA
GET  /work-items/{id}/rca      → get existing RCA
GET  /rcas                     → list all RCAs (most recent first)
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import get_db
from app.schemas.rca import RCACreateRequest, RCAOut
from app.services.rca_service import create_or_update_rca, get_rca, list_rcas
from app.services.work_item_service import get_work_item

logger = logging.getLogger("ims.api.rca")
router = APIRouter(tags=["rca"])


def _rca_to_dict(rca, mttr: int | None = None) -> dict:
    return {
        "id": rca.id,
        "work_item_id": rca.work_item_id,
        "incident_start": rca.incident_start.isoformat(),
        "incident_end": rca.incident_end.isoformat(),
        "root_cause_category": rca.root_cause_category,
        "root_cause_description": rca.root_cause_description,
        "fix_applied": rca.fix_applied,
        "prevention_steps": rca.prevention_steps,
        "submitted_by": rca.submitted_by,
        "mttr_seconds": mttr,
        "created_at": rca.created_at.isoformat() if rca.created_at else None,
    }


@router.post("/work-items/{work_item_id}/rca", status_code=201)
async def submit_rca(
    work_item_id: str,
    payload: RCACreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Submit (or re-submit) an RCA for a Work Item.

    - Validates all required fields
    - Calculates MTTR automatically from incident_start / incident_end
    - Writes MTTR back to the Work Item
    - Allows re-submission (replaces previous RCA)
    - Does NOT auto-close; use PATCH /work-items/{id}/transition after submitting
    """
    wi = await get_work_item(db, work_item_id)
    if not wi:
        raise HTTPException(status_code=404, detail="Work item not found")

    if wi.status == "CLOSED":
        raise HTTPException(
            status_code=422,
            detail="Cannot modify RCA for a CLOSED work item",
        )

    try:
        rca, mttr = await create_or_update_rca(db, work_item_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except SQLAlchemyError as e:
        logger.error("RCA DB error for WI %s: %s", work_item_id, e)
        raise HTTPException(status_code=500, detail="Database error persisting RCA")

    return {
        "success": True,
        "rca": _rca_to_dict(rca, mttr),
        "mttr_seconds": mttr,
        "mttr_minutes": round(mttr / 60, 1),
        "message": (
            f"RCA submitted. MTTR: {round(mttr / 60, 1)} minutes. "
            "You can now close the incident via PATCH /work-items/{id}/transition."
        ),
    }


@router.get("/work-items/{work_item_id}/rca")
async def get_rca_endpoint(work_item_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch the RCA for a Work Item (if it exists)."""
    wi = await get_work_item(db, work_item_id)
    if not wi:
        raise HTTPException(status_code=404, detail="Work item not found")

    rca = await get_rca(db, work_item_id)
    if not rca:
        return {"rca": None, "work_item_id": work_item_id}

    from app.services.rca_service import _calculate_mttr
    mttr = _calculate_mttr(rca.incident_start, rca.incident_end)
    return {"rca": _rca_to_dict(rca, mttr), "work_item_id": work_item_id}


@router.get("/rcas")
async def list_rcas_endpoint(limit: int = 50, db: AsyncSession = Depends(get_db)):
    """List all submitted RCAs, most recent first."""
    from app.services.rca_service import _calculate_mttr
    rcas = await list_rcas(db, limit=limit)
    return {
        "rcas": [
            _rca_to_dict(r, _calculate_mttr(r.incident_start, r.incident_end))
            for r in rcas
        ],
        "count": len(rcas),
    }
