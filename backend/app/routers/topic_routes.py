from fastapi import APIRouter, Depends

from app.models.schemas import SuggestRequest, SuggestResponse
from app.services import auth, suggest

router = APIRouter(prefix="/topics", tags=["topics"])


@router.post("/suggest", response_model=SuggestResponse)
def suggest_topics(body: SuggestRequest, user: dict = Depends(auth.current_user)):
    """Map free-form interests to taxonomy topic + asset IDs (onboarding)."""
    return suggest.suggest(body.text)
