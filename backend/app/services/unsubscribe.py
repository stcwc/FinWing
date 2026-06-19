"""Signed, login-free unsubscribe tokens for summary emails.

The summary generator mints a token per recipient (link_for) and embeds it in
the email body and the List-Unsubscribe header; the public /unsubscribe route
verifies it (parse_token) and flips emailSummaries off. The token is an
HMAC-SHA256 over the userId, so it can't be forged and needs no server-side
state.
"""

import base64
import hashlib
import hmac

from app import settings


def _sign(user_id: str) -> str:
    secret = settings.unsubscribe_secret().encode()
    return hmac.new(secret, user_id.encode(), hashlib.sha256).hexdigest()[:32]


def make_token(user_id: str) -> str:
    raw = f"{user_id}:{_sign(user_id)}".encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def parse_token(token: str) -> str | None:
    """Return the userId if the token is authentic, else None."""
    try:
        pad = "=" * (-len(token) % 4)
        raw = base64.urlsafe_b64decode(token + pad).decode()
        user_id, mac = raw.rsplit(":", 1)
    except Exception:  # noqa: BLE001 — any malformed token is simply invalid
        return None
    if hmac.compare_digest(mac, _sign(user_id)):
        return user_id
    return None


def link_for(user_id: str) -> str | None:
    """Absolute unsubscribe URL, or None when no app URL is configured."""
    if not settings.APP_URL:
        return None
    return f"{settings.APP_URL}/api/unsubscribe?token={make_token(user_id)}"
