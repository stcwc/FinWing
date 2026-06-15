from fastapi import APIRouter, Depends

from app.models.schemas import AdminMetrics
from app.services import auth, db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/metrics", response_model=AdminMetrics)
def metrics(user: dict = Depends(auth.require_admin)):
    return db.admin_metrics()


@router.get("/feedback")
def feedback(user: dict = Depends(auth.require_admin)):
    return {"items": db.list_feedback()}
