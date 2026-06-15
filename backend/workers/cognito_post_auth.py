"""Cognito post-authentication trigger: records a sign-in event for the
admin "active today" metrics (LLD remaining-item from HLD)."""

from app.services.db import record_signin


def handler(event, context):
    user_id = event["request"]["userAttributes"]["sub"]
    provider = "google" if event.get("userName", "").startswith("google_") else "email"
    record_signin(user_id, provider)
    return event
