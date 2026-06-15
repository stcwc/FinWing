"""Cognito JWT verification + httpOnly cookie session (LLD §2.1).

The SPA exchanges a Cognito authorization code at /auth/callback; we set the
access token in an httpOnly cookie. Every request verifies the JWT against
Cognito's JWKS (cached in module state for the container lifetime)."""

import base64
import json
import time
import urllib.request

import requests
from fastapi import HTTPException, Request

from app import settings

_jwks_cache: dict = {}
_jwks_fetched_at: float = 0
JWKS_TTL = 86400


def _jwks() -> dict:
    global _jwks_cache, _jwks_fetched_at
    if _jwks_cache and time.time() - _jwks_fetched_at < JWKS_TTL:
        return _jwks_cache
    url = (
        f"https://cognito-idp.{settings.AWS_REGION}.amazonaws.com/"
        f"{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    )
    with urllib.request.urlopen(url, timeout=5) as resp:
        _jwks_cache = {k["kid"]: k for k in json.load(resp)["keys"]}
    _jwks_fetched_at = time.time()
    return _jwks_cache


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify_token(token: str) -> dict:
    """Verify RS256 signature, expiry, and issuer. Returns claims."""
    try:
        header_b64, payload_b64, sig_b64 = token.split(".")
        header = json.loads(_b64url_decode(header_b64))
        claims = json.loads(_b64url_decode(payload_b64))
    except Exception:
        raise HTTPException(401, "Malformed token")

    key = _jwks().get(header.get("kid"))
    if key is None:
        raise HTTPException(401, "Unknown signing key")

    # RS256 verification using only stdlib + the JWK n/e values
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

    n = int.from_bytes(_b64url_decode(key["n"]), "big")
    e = int.from_bytes(_b64url_decode(key["e"]), "big")
    pub = RSAPublicNumbers(e, n).public_key()
    try:
        pub.verify(
            _b64url_decode(sig_b64),
            f"{header_b64}.{payload_b64}".encode(),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except Exception:
        raise HTTPException(401, "Invalid signature")

    if claims.get("exp", 0) < time.time():
        raise HTTPException(401, "Token expired")
    expected_iss = (
        f"https://cognito-idp.{settings.AWS_REGION}.amazonaws.com/"
        f"{settings.COGNITO_USER_POOL_ID}"
    )
    if claims.get("iss") != expected_iss:
        raise HTTPException(401, "Invalid issuer")
    return claims


def current_user(request: Request) -> dict:
    """FastAPI dependency: resolve the session cookie to user claims."""
    token = request.cookies.get("finwing_session")
    if not token:
        raise HTTPException(401, "Not signed in")
    claims = verify_token(token)
    groups = claims.get("cognito:groups", [])
    return {
        "userId": claims["sub"],
        "email": claims.get("email", ""),
        "isAdmin": "finwing-admins" in groups,
        "authProvider": "google" if claims.get("identities") else "email",
    }


def require_admin(request: Request) -> dict:
    user = current_user(request)
    if not user["isAdmin"]:
        raise HTTPException(403, "Admin only")
    return user


def exchange_code(code: str, redirect_uri: str) -> dict:
    """Exchange Cognito hosted-UI authorization code for tokens."""
    resp = requests.post(
        f"https://{settings.COGNITO_DOMAIN}/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.COGNITO_CLIENT_ID,
            "code": code,
            "redirect_uri": redirect_uri,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    if resp.status_code != 200:
        raise HTTPException(401, "Code exchange failed")
    return resp.json()  # {access_token, id_token, refresh_token, expires_in}


def refresh_session(refresh_token: str) -> dict:
    resp = requests.post(
        f"https://{settings.COGNITO_DOMAIN}/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": settings.COGNITO_CLIENT_ID,
            "refresh_token": refresh_token,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    if resp.status_code != 200:
        raise HTTPException(401, "Refresh failed")
    return resp.json()


def session_cookie_headers(tokens: dict) -> list[tuple[str, str]]:
    """Build Set-Cookie headers for the id token (carries email/groups claims)
    and refresh token."""
    secure = "; Secure" if settings.ENV != "local" else ""
    domain = f"; Domain={settings.COOKIE_DOMAIN}" if settings.COOKIE_DOMAIN else ""
    headers = [
        (
            "set-cookie",
            f"finwing_session={tokens['id_token']}; HttpOnly{secure}; "
            f"SameSite=Lax; Path=/{domain}; Max-Age={tokens.get('expires_in', 3600)}",
        )
    ]
    if "refresh_token" in tokens:
        headers.append(
            (
                "set-cookie",
                f"finwing_refresh={tokens['refresh_token']}; HttpOnly{secure}; "
                f"SameSite=Lax; Path=/auth{domain}; Max-Age=2592000",
            )
        )
    return headers
