"""SES bounce/complaint handler (SNS-subscribed).

The digest sender references an SES configuration set whose event destination
publishes Bounce and Complaint events to an SNS topic. This Lambda processes
them: on a permanent (hard) bounce or any complaint it adds the recipient to the
SES suppression list (so we never send to it again) and turns off that user's
emailSummaries preference. Transient bounces are ignored — SES retries those.

Maintaining this loop is both good deliverability hygiene and the concrete
bounce/complaint process AWS looks for when granting production access."""

import json

import boto3

from app import settings
from app.services import db

_ses = None


def _ses_client():
    global _ses
    if _ses is None:
        _ses = boto3.client("sesv2", region_name=settings.AWS_REGION)
    return _ses


def _suppress(address: str, reason: str) -> None:
    """reason is BOUNCE or COMPLAINT (SES suppression-list reasons)."""
    try:
        _ses_client().put_suppressed_destination(EmailAddress=address, Reason=reason)
    except Exception as e:  # noqa: BLE001 — best-effort; account-level suppression also covers this
        print(json.dumps({"level": "WARN", "msg": "suppress failed", "address": address, "error": str(e)}))
    try:
        disabled = db.disable_email_for(address)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"level": "WARN", "msg": "disable_email failed", "address": address, "error": str(e)}))
        disabled = 0
    print(json.dumps({"level": "INFO", "event": "ses_suppress", "reason": reason,
                      "address": address, "profilesDisabled": disabled}))


def handler(event, context):
    for record in event.get("Records", []):
        try:
            msg = json.loads(record["Sns"]["Message"])
        except (KeyError, ValueError):
            continue
        # SES notifications use "notificationType"; config-set events use "eventType".
        kind = msg.get("notificationType") or msg.get("eventType")
        if kind == "Bounce":
            bounce = msg.get("bounce", {})
            if bounce.get("bounceType") != "Permanent":
                continue  # transient — SES retries; don't suppress
            for r in bounce.get("bouncedRecipients", []):
                if r.get("emailAddress"):
                    _suppress(r["emailAddress"], "BOUNCE")
        elif kind == "Complaint":
            for r in msg.get("complaint", {}).get("complainedRecipients", []):
                if r.get("emailAddress"):
                    _suppress(r["emailAddress"], "COMPLAINT")
    return {"ok": True}
