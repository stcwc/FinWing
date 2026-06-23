"""SES inbound forwarder: re-sends mail received at support@finwingnews.com to a
personal inbox.

SES stores the raw message in S3 (the rule's S3 action) and invokes this Lambda
(the rule's Lambda action). We can't relay the message verbatim — the original
sender's domain won't pass SPF/DKIM/DMARC from our infrastructure — so we send a
fresh message FROM our verified domain, set Reply-To to the original sender (so a
reply goes back to them), and preserve the subject and body.
"""

import email
import os

import boto3

s3 = boto3.client("s3")
ses = boto3.client("ses")

BUCKET = os.environ["MAIL_BUCKET"]
KEY_PREFIX = os.environ.get("KEY_PREFIX", "")
FORWARD_TO = os.environ["FORWARD_TO"]   # personal destination inbox
MAIL_FROM = os.environ["MAIL_FROM"]     # verified sender, e.g. support@finwingnews.com


def handler(event, context):
    ses_record = event["Records"][0]["ses"]
    message_id = ses_record["mail"]["messageId"]
    envelope_from = ses_record["mail"]["source"]

    raw = s3.get_object(Bucket=BUCKET, Key=f"{KEY_PREFIX}{message_id}")["Body"].read()
    msg = email.message_from_bytes(raw)

    original_from = msg.get("From", envelope_from)
    subject = msg.get("Subject", "(no subject)")

    # Strip headers that would either fail validation or misroute the reply, then
    # re-stamp the message as coming from us with a reply path to the sender.
    for h in ("DKIM-Signature", "From", "Sender", "Return-Path", "Reply-To", "To"):
        del msg[h]
    msg["From"] = f"FinWing Support <{MAIL_FROM}>"
    msg["Reply-To"] = original_from
    msg["To"] = FORWARD_TO

    ses.send_raw_email(
        Source=MAIL_FROM,
        Destinations=[FORWARD_TO],
        RawMessage={"Data": msg.as_bytes()},
    )
    print(f'{{"level":"INFO","forwarded":"{message_id}","from":"{original_from}"}}')
