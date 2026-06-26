"""SES bounce/complaint handler: hard bounce + complaint suppress & disable;
transient bounce is ignored."""

import json

from app.services import db
from workers import ses_events


def _sns(message: dict) -> dict:
    return {"Records": [{"Sns": {"Message": json.dumps(message)}}]}


def _seed_profile(email: str) -> str:
    user_id = "u-" + email.split("@")[0]
    db.app_table().put_item(Item={
        "PK": f"USER#{user_id}", "SK": "PROFILE", "email": email,
        "timezone": "America/Los_Angeles", "summaryTimePref": "17:00",
        "emailSummaries": True,
    })
    return user_id


def _suppressed(monkeypatch):
    calls = []
    monkeypatch.setattr(ses_events, "_ses_client",
                        lambda: type("C", (), {"put_suppressed_destination": staticmethod(
                            lambda **k: calls.append(k))})())
    return calls


def test_permanent_bounce_suppresses_and_disables(tables, monkeypatch):
    uid = _seed_profile("bad@example.com")
    calls = _suppressed(monkeypatch)
    ses_events.handler(_sns({
        "notificationType": "Bounce",
        "bounce": {"bounceType": "Permanent",
                   "bouncedRecipients": [{"emailAddress": "bad@example.com"}]},
    }), None)
    assert calls == [{"EmailAddress": "bad@example.com", "Reason": "BOUNCE"}]
    assert db.get_user(uid)["emailSummaries"] is False


def test_complaint_suppresses_and_disables(tables, monkeypatch):
    uid = _seed_profile("angry@example.com")
    calls = _suppressed(monkeypatch)
    ses_events.handler(_sns({
        "notificationType": "Complaint",
        "complaint": {"complainedRecipients": [{"emailAddress": "angry@example.com"}]},
    }), None)
    assert calls[0]["Reason"] == "COMPLAINT"
    assert db.get_user(uid)["emailSummaries"] is False


def test_transient_bounce_ignored(tables, monkeypatch):
    uid = _seed_profile("busy@example.com")
    calls = _suppressed(monkeypatch)
    ses_events.handler(_sns({
        "notificationType": "Bounce",
        "bounce": {"bounceType": "Transient",
                   "bouncedRecipients": [{"emailAddress": "busy@example.com"}]},
    }), None)
    assert calls == []  # not suppressed
    assert db.get_user(uid)["emailSummaries"] is True  # still opted in
