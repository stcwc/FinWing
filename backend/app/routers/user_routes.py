from fastapi import APIRouter, Depends, HTTPException

from app.models.schemas import UserProfile, UserUpdate
from app.services import auth, db

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/me", response_model=UserProfile)
def create_me(user: dict = Depends(auth.current_user)):
    try:
        created = db.create_user(user["userId"], user["email"], user["authProvider"])
    except db.CapExceeded:
        raise HTTPException(
            409,
            detail={
                "code": "USER_CAP",
                "message": "FinWing is at capacity. Please submit feedback to request access.",
            },
        )
    profile = db.get_user(user["userId"])
    return UserProfile(
        userId=user["userId"],
        email=profile["email"],
        role=profile.get("role", "user"),
        timezone=profile["timezone"],
        summaryTimePref=profile["summaryTimePref"],
        lensCount=int(profile.get("lensCount", 0)),
        firstSignIn=created,
    )


@router.get("/me", response_model=UserProfile)
def get_me(user: dict = Depends(auth.current_user)):
    profile = db.get_user(user["userId"])
    if profile is None:
        raise HTTPException(404, detail={"code": "NO_PROFILE", "message": "Sign up first"})
    return UserProfile(
        userId=user["userId"],
        email=profile["email"],
        role=profile.get("role", "user"),
        timezone=profile["timezone"],
        summaryTimePref=profile["summaryTimePref"],
        lensCount=int(profile.get("lensCount", 0)),
    )


@router.patch("/me")
def update_me(body: UserUpdate, user: dict = Depends(auth.current_user)):
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(400, detail={"code": "EMPTY", "message": "Nothing to update"})
    db.update_user(user["userId"], fields)
    return {"ok": True}
