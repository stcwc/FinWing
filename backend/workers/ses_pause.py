"""SES reputation kill-switch (CloudWatch-alarm → SNS-subscribed).

CloudWatch alarms watch the digest configuration set's Reputation.BounceRate and
Reputation.ComplaintRate. If either crosses the SES enforcement threshold
(bounce 5%, complaint 0.1%) the alarm publishes to an SNS topic that fans out to
this Lambda, which disables sending on the configuration set. All digests flow
through that config set, so this halts outbound mail within minutes — before the
account's reputation can degrade far enough for SES to suspend it — while leaving
the rest of the account untouched. Re-enabling is a deliberate manual step once
the cause is understood.

This automated pause is the concrete "protect sender reputation / deliverability"
control AWS asks for when granting production access."""

import json

import boto3

from app import settings

_ses = None


def _ses_client():
    global _ses
    if _ses is None:
        _ses = boto3.client("sesv2", region_name=settings.AWS_REGION)
    return _ses


def _pause(config_set: str, reason: str) -> None:
    try:
        _ses_client().put_configuration_set_sending_options(
            ConfigurationSetName=config_set, SendingEnabled=False
        )
        print(json.dumps({"level": "WARN", "event": "ses_sending_paused",
                          "configSet": config_set, "reason": reason}))
    except Exception as e:  # noqa: BLE001 — surface but never raise back into SNS retries
        print(json.dumps({"level": "ERROR", "msg": "pause failed",
                          "configSet": config_set, "error": str(e)}))


def handler(event, context):
    config_set = settings.EMAIL_CONFIG_SET
    if not config_set:
        print(json.dumps({"level": "ERROR", "msg": "EMAIL_CONFIG_SET unset; cannot pause"}))
        return {"ok": False}
    for record in event.get("Records", []):
        try:
            msg = json.loads(record["Sns"]["Message"])
        except (KeyError, ValueError):
            msg = {}
        # CloudWatch alarm notification; fall back to a generic reason if the
        # shape is unexpected so we still pause on any signal on this topic.
        if msg.get("NewStateValue") and msg.get("NewStateValue") != "ALARM":
            continue  # OK / INSUFFICIENT_DATA transitions — nothing to do
        reason = msg.get("AlarmName") or "ses-reputation-alarm"
        _pause(config_set, reason)
    return {"ok": True}
