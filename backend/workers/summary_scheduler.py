"""Summary scheduler (LLD §6.5): every 5 minutes, find users whose
nextSummaryAt is due via GSI2, fan out one async summary-generator invocation
per lens, and roll nextSummaryAt forward (DST-aware)."""

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import boto3
from boto3.dynamodb.conditions import Key

from app import settings
from app.services.db import app_table, utcnow
from workers.scheduling import compute_next_summary_at

_lambda = None


def lambda_client():
    global _lambda
    if _lambda is None:
        _lambda = boto3.client("lambda", region_name=settings.AWS_REGION)
    return _lambda


def handler(event, context):
    now = utcnow()
    resp = app_table().query(
        IndexName="GSI2",
        KeyConditionExpression=Key("GSI2PK").eq("SUMMARY_QUEUE") & Key("GSI2SK").lte(now),
        Limit=25,
    )
    dispatched = 0
    for profile in resp["Items"]:
        user_id = profile["PK"].split("#", 1)[1]
        tz = profile.get("timezone", "America/Los_Angeles")
        local_date = datetime.now(timezone.utc).astimezone(ZoneInfo(tz)).strftime("%Y-%m-%d")

        lenses = app_table().query(
            KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("LENS#")
        )["Items"]
        for lens in lenses:
            lambda_client().invoke(
                FunctionName=settings.SUMMARY_GENERATOR_ARN,
                InvocationType="Event",
                Payload=json.dumps(
                    {
                        "userId": user_id,
                        "lensId": lens["SK"].split("#", 1)[1],
                        "date": local_date,
                        "timezone": tz,
                    }
                ),
            )
            dispatched += 1

        # Roll forward BEFORE generation completes — duplicate fires are
        # harmless because the summary write is conditional (LLD §5.4).
        next_at = compute_next_summary_at(profile.get("summaryTimePref", "17:00"), tz)
        app_table().update_item(
            Key={"PK": profile["PK"], "SK": "PROFILE"},
            UpdateExpression="SET nextSummaryAt = :n, GSI2SK = :n",
            ExpressionAttributeValues={":n": next_at},
        )
    print(json.dumps({"level": "INFO", "usersDue": len(resp["Items"]), "lensesDispatched": dispatched}))
