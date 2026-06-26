"""Runtime configuration. All values come from environment variables set by
CDK; secrets are resolved from SSM at cold start and cached for the container
lifetime."""

import os
from functools import lru_cache

APP_TABLE = os.environ.get("APP_TABLE", "finwing-app-beta")
CONTENT_TABLE = os.environ.get("CONTENT_TABLE", "finwing-content-beta")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

COGNITO_USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")
COGNITO_CLIENT_ID = os.environ.get("COGNITO_CLIENT_ID", "")
COGNITO_DOMAIN = os.environ.get("COGNITO_DOMAIN", "")

MATCHING_QUEUE_URL = os.environ.get("MATCHING_QUEUE_URL", "")
ABSTRACTION_QUEUE_URL = os.environ.get("ABSTRACTION_QUEUE_URL", "")
SUMMARY_GENERATOR_ARN = os.environ.get("SUMMARY_GENERATOR_ARN", "")
BACKFILL_FN_NAME = os.environ.get("BACKFILL_FN_NAME", "")

ENV = os.environ.get("FINWING_ENV", "beta")
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", "")

# Summary-email delivery (SES). EMAIL_SENDER must be a verified SES identity;
# when unset, the summary generator skips email and just stores the summary.
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "")
EMAIL_SENDER_NAME = os.environ.get("EMAIL_SENDER_NAME", "FinWing")
APP_URL = os.environ.get("APP_URL", "")
# SES configuration set: when set, digest sends reference it so bounce/complaint
# events publish to SNS for auto-suppression.
EMAIL_CONFIG_SET = os.environ.get("EMAIL_CONFIG_SET", "")
ALLOWED_ORIGINS = [
    o for o in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o
]

MAX_USERS = 100
MAX_LENSES_PER_USER = 5
MAX_TOPICS_PER_LENS = 10
MAX_ASSETS_PER_LENS = 10

HAIKU_MODEL = "claude-haiku-4-5-20251001"
SONNET_MODEL = "claude-sonnet-4-6"

ARTICLE_TTL_DAYS = 30
PRICE_CACHE_TTL_DAYS = 7
CHAT_WINDOW_TURNS = 20
BACKFILL_DAYS = 10

# Lens-ticker quotes: symbols per Twelve Data /quote call. The free tier allows
# 8 credits/min and each symbol is one credit, so chunk at 8 and pause a full
# rolling minute between chunks (a shorter pause 429s the next chunk).
QUOTE_REFRESH_BATCH = 8
QUOTE_RATE_PAUSE_SECONDS = 61


@lru_cache(maxsize=8)
def ssm_param(name: str) -> str:
    import boto3

    ssm = boto3.client("ssm", region_name=AWS_REGION)
    return ssm.get_parameter(Name=name, WithDecryption=True)["Parameter"]["Value"]


def anthropic_api_key() -> str:
    if key := os.environ.get("ANTHROPIC_API_KEY"):
        return key
    return ssm_param(f"/finwing/{ENV}/anthropic-api-key")


def finnhub_api_key() -> str:
    if key := os.environ.get("FINNHUB_API_KEY"):
        return key
    return ssm_param(f"/finwing/{ENV}/finnhub-api-key")


def twelvedata_api_key() -> str:
    if key := os.environ.get("TWELVEDATA_API_KEY"):
        return key
    return ssm_param(f"/finwing/{ENV}/twelvedata-api-key")


def fred_api_key() -> str:
    if key := os.environ.get("FRED_API_KEY"):
        return key
    return ssm_param(f"/finwing/{ENV}/fred-api-key")


def unsubscribe_secret() -> str:
    """HMAC key for one-click unsubscribe tokens. Shared by the API (verifies)
    and the summary generator (mints)."""
    if key := os.environ.get("UNSUBSCRIBE_SECRET"):
        return key
    return ssm_param(f"/finwing/{ENV}/unsubscribe-secret")
