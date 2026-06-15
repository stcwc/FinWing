from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.schemas import FeedPage, Lens, LensCreate, LensUpdate, Summary, SummaryEdit
from app.services import auth, db, taxonomy

router = APIRouter(prefix="/lenses", tags=["lenses"])


def _validate(topic_ids: list[str] | None, asset_ids: list[str] | None):
    if topic_ids is not None:
        if bad := taxonomy.validate_topic_ids(topic_ids):
            raise HTTPException(400, detail={"code": "BAD_TOPIC", "message": f"Unknown topics: {bad}"})
    if asset_ids is not None:
        if bad := taxonomy.validate_asset_ids(asset_ids):
            raise HTTPException(400, detail={"code": "BAD_ASSET", "message": f"Unknown assets: {bad}"})


@router.get("", response_model=list[Lens])
def list_lenses(user: dict = Depends(auth.current_user)):
    return db.list_lenses(user["userId"])


@router.post("", response_model=Lens)
def create_lens(body: LensCreate, user: dict = Depends(auth.current_user)):
    _validate(body.topicIds, body.trackedAssetIds)
    try:
        return db.create_lens(user["userId"], body.name, body.topicIds, body.trackedAssetIds)
    except db.CapExceeded as e:
        raise HTTPException(409, detail={"code": "LENS_CAP", "message": str(e)})


@router.get("/{lens_id}", response_model=Lens)
def get_lens(lens_id: str, user: dict = Depends(auth.current_user)):
    lens = db.get_lens(user["userId"], lens_id)
    if lens is None:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Lens not found"})
    return lens


@router.patch("/{lens_id}")
def update_lens(lens_id: str, body: LensUpdate, user: dict = Depends(auth.current_user)):
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(400, detail={"code": "EMPTY", "message": "Nothing to update"})
    _validate(fields.get("topicIds"), fields.get("trackedAssetIds"))
    try:
        db.update_lens(user["userId"], lens_id, fields)
    except db.Conflict:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Lens not found"})
    return {"ok": True}


@router.delete("/{lens_id}")
def delete_lens(lens_id: str, user: dict = Depends(auth.current_user)):
    try:
        db.delete_lens(user["userId"], lens_id)
    except db.Conflict:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Lens not found"})
    return {"ok": True}


# ── Feed ─────────────────────────────────────────────────────────


@router.get("/{lens_id}/feed", response_model=FeedPage)
def lens_feed(
    lens_id: str,
    limit: int = Query(default=50, le=100),
    cursor: str | None = None,
    user: dict = Depends(auth.current_user),
):
    lens = db.get_lens(user["userId"], lens_id)
    if lens is None:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "Lens not found"})
    items, next_cursor = db.merged_feed(lens["topicIds"], limit=limit, before=cursor)
    return {"items": items, "nextCursor": next_cursor}


# ── Summaries ────────────────────────────────────────────────────


@router.get("/{lens_id}/summaries", response_model=list[Summary])
def list_summaries(
    lens_id: str,
    date_from: str = Query(alias="from"),
    date_to: str = Query(alias="to"),
    user: dict = Depends(auth.current_user),
):
    return db.list_summaries(user["userId"], lens_id, date_from, date_to)


@router.get("/{lens_id}/summaries/{date}", response_model=Summary)
def get_summary(lens_id: str, date: str, user: dict = Depends(auth.current_user)):
    summary = db.get_summary(user["userId"], lens_id, date)
    if summary is None:
        raise HTTPException(404, detail={"code": "NOT_FOUND", "message": "No summary for this date"})
    return summary


@router.put("/{lens_id}/summaries/{date}")
def edit_summary(
    lens_id: str, date: str, body: SummaryEdit, user: dict = Depends(auth.current_user)
):
    try:
        new_version = db.save_user_summary_edit(
            user["userId"], lens_id, date, body.body, body.version
        )
    except db.Conflict as e:
        raise HTTPException(409, detail={"code": "VERSION_CONFLICT", "message": str(e)})
    return {"ok": True, "version": new_version}
