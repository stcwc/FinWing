"""Public, login-free unsubscribe endpoint for summary emails.

Linked from every digest email and its List-Unsubscribe header. A valid signed
token flips the user's emailSummaries preference off; GET returns a small
confirmation page (for the in-email link), POST returns 200 (RFC 8058 one-click
from the mail client). Invalid tokens are treated as already-unsubscribed so we
never leak whether a token is valid.
"""

from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse

from app.services import db, unsubscribe

router = APIRouter(tags=["unsubscribe"])

_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>FinWing</title></head>
<body style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#f4f5f7;margin:0;padding:48px 24px;text-align:center;color:#1f2933;">
  <div style="max-width:460px;margin:0 auto;background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:32px;">
    <div style="font-size:20px;font-weight:700;color:#0b3d2e;margin-bottom:12px;">FinWing</div>
    <p style="font-size:15px;line-height:1.6;">{message}</p>
  </div>
</body></html>"""


def _opt_out(token: str) -> None:
    user_id = unsubscribe.parse_token(token)
    if not user_id:
        return
    try:
        db.update_user(user_id, {"emailSummaries": False})
    except Exception:  # noqa: BLE001 — no profile / already gone: treat as done
        pass


@router.get("/unsubscribe", response_class=HTMLResponse)
def unsubscribe_get(token: str = ""):
    _opt_out(token)
    return _PAGE.format(
        message="You've been unsubscribed from FinWing daily-summary emails. "
        "You can turn them back on anytime in Settings."
    )


@router.post("/unsubscribe")
def unsubscribe_post(token: str = ""):
    _opt_out(token)
    return Response(status_code=200)
