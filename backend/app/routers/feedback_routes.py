from fastapi import APIRouter, Depends

from app.models.schemas import FeedbackCreate
from app.services import auth, db

router = APIRouter(tags=["feedback"])


@router.post("/feedback")
def submit_feedback(body: FeedbackCreate, user: dict = Depends(auth.current_user)):
    db.put_feedback(user["userId"], body.text, body.context)
    return {"ok": True}
