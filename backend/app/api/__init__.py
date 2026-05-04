from fastapi import APIRouter
from app.api.health import router as health_router
from app.api.ingest import router as ingest_router
from app.api.work_items import router as work_items_router, alert_router
from app.api.rca import router as rca_router
from app.api.observability import router as observability_router
from app.api.ws_status import router as ws_status_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(ingest_router)
api_router.include_router(work_items_router)
api_router.include_router(alert_router)
api_router.include_router(rca_router)
api_router.include_router(observability_router)
api_router.include_router(ws_status_router)
