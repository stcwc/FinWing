from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.services import auth, db

router = APIRouter(prefix="/auth", tags=["auth"])


class CallbackBody(BaseModel):
    code: str
    redirectUri: str


@router.post("/callback")
def callback(body: CallbackBody, response: Response):
    tokens = auth.exchange_code(body.code, body.redirectUri)
    for name, value in auth.session_cookie_headers(tokens):
        response.headers.append(name, value)
    claims = auth.verify_token(tokens["id_token"])
    db.record_signin(claims["sub"], "google" if claims.get("identities") else "email")
    return {"ok": True}


@router.post("/refresh")
def refresh(request: Request, response: Response):
    refresh_token = request.cookies.get("finwing_refresh", "")
    tokens = auth.refresh_session(refresh_token)
    for name, value in auth.session_cookie_headers(tokens):
        response.headers.append(name, value)
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.headers.append(
        "set-cookie", "finwing_session=; HttpOnly; Path=/; Max-Age=0"
    )
    response.headers.append(
        "set-cookie", "finwing_refresh=; HttpOnly; Path=/api/auth; Max-Age=0"
    )
    return {"ok": True}


@router.get("/me")
def me(user: dict = Depends(auth.current_user)):
    return {"userId": user["userId"], "email": user["email"], "isAdmin": user["isAdmin"]}
