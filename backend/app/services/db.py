"""DynamoDB repository layer. Implements the transaction & consistency
invariants from LLD §5: TransactWriteItems for user/lens caps, conditional
writes for dedup, idempotency, and version guards."""

import time
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app import settings

_dynamodb = None
_ddb_client = None


def dynamodb():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=settings.AWS_REGION)
    return _dynamodb


def ddb_client():
    """Pure low-level client for transact_write_items. The resource's
    `.meta.client` double-serializes typed values passed to transactions, so we
    keep a dedicated low-level client for those calls."""
    global _ddb_client
    if _ddb_client is None:
        _ddb_client = boto3.client("dynamodb", region_name=settings.AWS_REGION)
    return _ddb_client


def app_table():
    return dynamodb().Table(settings.APP_TABLE)


def content_table():
    return dynamodb().Table(settings.CONTENT_TABLE)


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class CapExceeded(Exception):
    pass


class Conflict(Exception):
    pass


# ── Users ────────────────────────────────────────────────────────


def ensure_counter() -> None:
    """Idempotently create the global counter so the signup transaction can use
    a simple `userCount < :max` guard. Comparing a missing attribute is treated
    as false by DynamoDB but raises in moto, so we never rely on that path."""
    try:
        app_table().put_item(
            Item={"PK": "SYSTEM#GLOBAL", "SK": "COUNTERS", "userCount": 0},
            ConditionExpression="attribute_not_exists(PK)",
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


def create_user(user_id: str, email: str, auth_provider: str, tz: str = "America/Los_Angeles") -> bool:
    """Create the profile and bump the global user counter in one transaction
    (LLD §5.1). Returns True if created, False if the profile already existed.
    Raises CapExceeded at the 100-user cap.

    The counter increment is guarded by `userCount < :max`, so the cap is
    enforced atomically; the profile Put's `attribute_not_exists(PK)` guard makes
    a returning user a no-op rather than a counter bump."""
    from workers.scheduling import compute_next_summary_at

    if get_user(user_id) is not None:
        return False  # returning user — never blocked by the cap, no counter change

    ensure_counter()
    now = utcnow()
    next_at = compute_next_summary_at("17:00", tz)
    try:
        ddb_client().transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": settings.APP_TABLE,
                        "Item": {
                            "PK": {"S": f"USER#{user_id}"},
                            "SK": {"S": "PROFILE"},
                            "email": {"S": email},
                            "authProvider": {"S": auth_provider},
                            "role": {"S": "user"},
                            "timezone": {"S": tz},
                            "summaryTimePref": {"S": "17:00"},
                            "language": {"S": "en"},
                            "emailSummaries": {"BOOL": True},
                            "nextSummaryAt": {"S": next_at},
                            "lensCount": {"N": "0"},
                            "signupAt": {"S": now},
                            "GSI2PK": {"S": "SUMMARY_QUEUE"},
                            "GSI2SK": {"S": next_at},
                        },
                        "ConditionExpression": "attribute_not_exists(PK)",
                    }
                },
                {
                    "Update": {
                        "TableName": settings.APP_TABLE,
                        "Key": {"PK": {"S": "SYSTEM#GLOBAL"}, "SK": {"S": "COUNTERS"}},
                        "UpdateExpression": "ADD userCount :one",
                        "ConditionExpression": "userCount < :max",
                        "ExpressionAttributeValues": {
                            ":one": {"N": "1"},
                            ":max": {"N": str(settings.MAX_USERS)},
                        },
                    }
                },
            ]
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] != "TransactionCanceledException":
            raise
        reasons = e.response.get("CancellationReasons", [])
        # Item 0 (profile) failed → returning user racing itself; not an error.
        if reasons and reasons[0].get("Code") == "ConditionalCheckFailed":
            return False
        raise CapExceeded("User cap reached")


def get_user(user_id: str) -> dict | None:
    resp = app_table().get_item(Key={"PK": f"USER#{user_id}", "SK": "PROFILE"})
    return resp.get("Item")


def update_user(user_id: str, fields: dict) -> None:
    from workers.scheduling import compute_next_summary_at

    profile = get_user(user_id)
    if profile is None:
        raise Conflict("No profile")
    tz = fields.get("timezone", profile["timezone"])
    pref = fields.get("summaryTimePref", profile["summaryTimePref"])
    next_at = compute_next_summary_at(pref, tz)
    expr = "SET #tz = :tz, summaryTimePref = :pref, nextSummaryAt = :next, GSI2SK = :next"
    values = {":tz": tz, ":pref": pref, ":next": next_at}
    if "language" in fields:
        expr += ", #lang = :lang"
        values[":lang"] = fields["language"]
    if "emailSummaries" in fields:
        expr += ", emailSummaries = :emailSummaries"
        values[":emailSummaries"] = bool(fields["emailSummaries"])
    names = {"#tz": "timezone"}
    if "language" in fields:
        names["#lang"] = "language"
    app_table().update_item(
        Key={"PK": f"USER#{user_id}", "SK": "PROFILE"},
        UpdateExpression=expr,
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def disable_email_for(email: str) -> int:
    """Turn off emailSummaries for every profile with this address (bounce/
    complaint handling). Scans PROFILE items by email; returns the count updated."""
    table = app_table()
    updated = 0
    kwargs = {
        "FilterExpression": Attr("SK").eq("PROFILE") & Attr("email").eq(email),
        "ProjectionExpression": "PK",
    }
    while True:
        resp = table.scan(**kwargs)
        for item in resp.get("Items", []):
            table.update_item(
                Key={"PK": item["PK"], "SK": "PROFILE"},
                UpdateExpression="SET emailSummaries = :f",
                ExpressionAttributeValues={":f": False},
            )
            updated += 1
        if "LastEvaluatedKey" not in resp:
            return updated
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]


def record_signin(user_id: str, auth_provider: str) -> None:
    now = utcnow()
    today = now[:10]
    app_table().put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": f"EVENT#{now}",
            "type": "signin",
            "authProvider": auth_provider,
            "GSI1PK": f"EVENT#signin#{today}",
            "GSI1SK": now,
        }
    )


# ── Lenses ───────────────────────────────────────────────────────


def create_lens(user_id: str, name: str, topic_ids: list[str], asset_ids: list[str]) -> dict:
    lens_id = uuid.uuid4().hex[:12]
    now = utcnow()
    item = {
        "PK": {"S": f"USER#{user_id}"},
        "SK": {"S": f"LENS#{lens_id}"},
        "name": {"S": name},
        "topicIds": {"L": [{"S": t} for t in topic_ids]},
        "trackedAssetIds": {"L": [{"S": a} for a in asset_ids]},
        "createdAt": {"S": now},
        "updatedAt": {"S": now},
    }
    try:
        ddb_client().transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": settings.APP_TABLE,
                        "Item": item,
                        "ConditionExpression": "attribute_not_exists(SK)",
                    }
                },
                {
                    "Update": {
                        "TableName": settings.APP_TABLE,
                        "Key": {"PK": {"S": f"USER#{user_id}"}, "SK": {"S": "PROFILE"}},
                        "UpdateExpression": "ADD lensCount :one",
                        "ConditionExpression": "lensCount < :max",
                        "ExpressionAttributeValues": {
                            ":one": {"N": "1"},
                            ":max": {"N": str(settings.MAX_LENSES_PER_USER)},
                        },
                    }
                },
            ]
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "TransactionCanceledException":
            raise CapExceeded(f"Maximum {settings.MAX_LENSES_PER_USER} lenses per account")
        raise
    return {
        "lensId": lens_id,
        "name": name,
        "topicIds": topic_ids,
        "trackedAssetIds": asset_ids,
        "createdAt": now,
        "updatedAt": now,
    }


def list_lenses(user_id: str) -> list[dict]:
    resp = app_table().query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("LENS#")
    )
    return [_lens_out(i) for i in resp["Items"]]


def get_lens(user_id: str, lens_id: str) -> dict | None:
    resp = app_table().get_item(
        Key={"PK": f"USER#{user_id}", "SK": f"LENS#{lens_id}"}, ConsistentRead=True
    )
    item = resp.get("Item")
    return _lens_out(item) if item else None


def _lens_out(item: dict) -> dict:
    return {
        "lensId": item["SK"].split("#", 1)[1],
        "name": item["name"],
        "topicIds": list(item.get("topicIds", [])),
        "trackedAssetIds": list(item.get("trackedAssetIds", [])),
        "createdAt": item.get("createdAt"),
        "updatedAt": item.get("updatedAt"),
    }


def update_lens(user_id: str, lens_id: str, fields: dict) -> None:
    expr_parts, names, values = ["updatedAt = :now"], {}, {":now": utcnow()}
    if "name" in fields:
        expr_parts.append("#n = :name")
        names["#n"] = "name"
        values[":name"] = fields["name"]
    if "topicIds" in fields:
        expr_parts.append("topicIds = :topics")
        values[":topics"] = fields["topicIds"]
    if "trackedAssetIds" in fields:
        expr_parts.append("trackedAssetIds = :assets")
        values[":assets"] = fields["trackedAssetIds"]
    kwargs = dict(
        Key={"PK": f"USER#{user_id}", "SK": f"LENS#{lens_id}"},
        UpdateExpression="SET " + ", ".join(expr_parts),
        ConditionExpression="attribute_exists(SK)",
        ExpressionAttributeValues=values,
    )
    if names:
        kwargs["ExpressionAttributeNames"] = names
    try:
        app_table().update_item(**kwargs)
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise Conflict("Lens not found")
        raise


def delete_lens(user_id: str, lens_id: str) -> None:
    try:
        ddb_client().transact_write_items(
            TransactItems=[
                {
                    "Delete": {
                        "TableName": settings.APP_TABLE,
                        "Key": {"PK": {"S": f"USER#{user_id}"}, "SK": {"S": f"LENS#{lens_id}"}},
                        "ConditionExpression": "attribute_exists(SK)",
                    }
                },
                {
                    "Update": {
                        "TableName": settings.APP_TABLE,
                        "Key": {"PK": {"S": f"USER#{user_id}"}, "SK": {"S": "PROFILE"}},
                        "UpdateExpression": "ADD lensCount :neg",
                        "ConditionExpression": "lensCount > :zero",
                        "ExpressionAttributeValues": {
                            ":neg": {"N": "-1"},
                            ":zero": {"N": "0"},
                        },
                    }
                },
            ]
        )
    except ClientError as e:
        if e.response["Error"]["Code"] == "TransactionCanceledException":
            raise Conflict("Lens not found")
        raise


# ── Feed ─────────────────────────────────────────────────────────


def _feed_item_out(item: dict, topic_id: str) -> dict:
    _, published_at, article_id = item["SK"].split("#", 2)
    return {
        "articleId": article_id,
        "topicId": topic_id,
        "publishedAt": published_at,
        "title": item["title"],
        "titleZh": item.get("titleZh"),
        "abstraction": item.get("abstraction"),
        "abstractionZh": item.get("abstractionZh"),
        "excerpt": item.get("excerpt", ""),
        "source": item.get("source", ""),
        "url": item.get("url", ""),
    }


def query_topic_feed(topic_id: str, limit: int = 50, before: str | None = None) -> list[dict]:
    cond = Key("PK").eq(f"TOPIC#{topic_id}")
    if before:
        cond = cond & Key("SK").lt(f"TS#{before}")
    else:
        cond = cond & Key("SK").begins_with("TS#")
    resp = content_table().query(
        KeyConditionExpression=cond, ScanIndexForward=False, Limit=limit
    )
    return [_feed_item_out(item, topic_id) for item in resp["Items"]]


def query_topic_window(topic_id: str, start_iso: str, end_iso: str, limit: int = 50) -> list[dict]:
    """Feed-index items for a topic within [start_iso, end_iso] (for historical
    summary windows / backfill)."""
    resp = content_table().query(
        KeyConditionExpression=Key("PK").eq(f"TOPIC#{topic_id}")
        & Key("SK").between(f"TS#{start_iso}", f"TS#{end_iso}~"),
        ScanIndexForward=False,
        Limit=limit,
    )
    return [_feed_item_out(item, topic_id) for item in resp["Items"]]


def merged_feed(topic_ids: list[str], limit: int = 50, before: str | None = None) -> tuple[list[dict], str | None]:
    """LLD §1.5: query each topic partition, merge, dedupe by articleId,
    newest first."""
    seen: dict[str, dict] = {}
    for tid in topic_ids[: settings.MAX_TOPICS_PER_LENS]:
        for item in query_topic_feed(tid, limit=limit, before=before):
            existing = seen.get(item["articleId"])
            # Keep whichever copy has an abstraction
            if existing is None or (item["abstraction"] and not existing["abstraction"]):
                seen[item["articleId"]] = item
    items = sorted(seen.values(), key=lambda i: i["publishedAt"], reverse=True)[:limit]
    next_cursor = items[-1]["publishedAt"] if len(items) == limit else None
    return items, next_cursor


# ── Summaries ────────────────────────────────────────────────────


def list_summaries(user_id: str, lens_id: str, date_from: str, date_to: str) -> list[dict]:
    resp = app_table().query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}")
        & Key("SK").between(f"SUMMARY#{lens_id}#{date_from}", f"SUMMARY#{lens_id}#{date_to}~")
    )
    return [_summary_out(i) for i in resp["Items"]]


def get_summary(user_id: str, lens_id: str, date: str) -> dict | None:
    resp = app_table().get_item(Key={"PK": f"USER#{user_id}", "SK": f"SUMMARY#{lens_id}#{date}"})
    item = resp.get("Item")
    return _summary_out(item) if item else None


def _summary_out(item: dict) -> dict:
    _, lens_id, date = item["SK"].split("#", 2)
    return {
        "date": date,
        "lensId": lens_id,
        "body": item["body"],
        "assetMoves": item.get("assetMoves", []),
        "rationale": item.get("rationale", ""),
        "editedByUser": item.get("editedByUser", False),
        "generatedAt": item.get("generatedAt"),
        "version": int(item.get("version", 1)),
    }


def put_generated_summary(
    user_id: str, lens_id: str, date: str, body: str, asset_moves: list, rationale: str
) -> bool:
    """LLD §5.4 — never overwrite a user-edited summary. Returns False if
    skipped."""
    try:
        app_table().put_item(
            Item={
                "PK": f"USER#{user_id}",
                "SK": f"SUMMARY#{lens_id}#{date}",
                "body": body,
                "assetMoves": asset_moves,
                "rationale": rationale,
                "editedByUser": False,
                "generatedAt": utcnow(),
                "version": 1,
            },
            ConditionExpression="attribute_not_exists(SK) OR editedByUser = :false",
            ExpressionAttributeValues={":false": False},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def save_user_summary_edit(user_id: str, lens_id: str, date: str, body: str, version: int) -> int:
    """LLD §5.5 — optimistic concurrency via version guard. Returns new
    version; raises Conflict on stale version."""
    try:
        resp = app_table().update_item(
            Key={"PK": f"USER#{user_id}", "SK": f"SUMMARY#{lens_id}#{date}"},
            UpdateExpression="SET body = :body, editedByUser = :true, version = version + :one",
            ConditionExpression="version = :expected",
            ExpressionAttributeValues={
                ":body": body,
                ":true": True,
                ":one": 1,
                ":expected": version,
            },
            ReturnValues="UPDATED_NEW",
        )
        return int(resp["Attributes"]["version"])
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise Conflict("Summary was modified concurrently; refresh and retry")
        raise


# ── Chat ─────────────────────────────────────────────────────────


def append_chat_turn(user_id: str, role: str, content: str) -> str:
    now = utcnow()
    msg_id = uuid.uuid4().hex[:8]
    app_table().put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": f"CHAT#{now}#{msg_id}",
            "role": role,
            "content": content,
        }
    )
    return msg_id


def recent_chat_turns(user_id: str, limit: int) -> list[dict]:
    """Newest-first from DynamoDB, returned oldest-first for the prompt."""
    resp = app_table().query(
        KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("CHAT#"),
        ScanIndexForward=False,
        Limit=limit,
    )
    return [{"role": i["role"], "content": i["content"]} for i in reversed(resp["Items"])]


def get_chat_state(user_id: str) -> dict:
    resp = app_table().get_item(Key={"PK": f"USER#{user_id}", "SK": "CHATSTATE"})
    return resp.get("Item") or {"runningSummary": "", "totalTurns": 0}


def update_chat_state(user_id: str, running_summary: str, total_turns: int) -> None:
    app_table().put_item(
        Item={
            "PK": f"USER#{user_id}",
            "SK": "CHATSTATE",
            "runningSummary": running_summary,
            "totalTurns": total_turns,
            "lastActiveAt": utcnow(),
        }
    )


# ── Feedback & admin ─────────────────────────────────────────────


def put_feedback(user_id: str, text: str, context: str | None) -> None:
    now = utcnow()
    item = {
        "PK": f"USER#{user_id}",
        "SK": f"FEEDBACK#{now}",
        "text": text,
        "GSI1PK": "FEEDBACK",
        "GSI1SK": now,
    }
    if context:
        item["context"] = context
    app_table().put_item(Item=item)


def list_feedback(limit: int = 50) -> list[dict]:
    resp = app_table().query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq("FEEDBACK"),
        ScanIndexForward=False,
        Limit=limit,
    )
    return [
        {
            "userId": i["PK"].split("#", 1)[1],
            "submittedAt": i["GSI1SK"],
            "text": i["text"],
            "context": i.get("context"),
        }
        for i in resp["Items"]
    ]


def admin_metrics() -> dict:
    today = utcnow()[:10]
    counters = app_table().get_item(
        Key={"PK": "SYSTEM#GLOBAL", "SK": "COUNTERS"}, ConsistentRead=True
    ).get("Item", {})
    events = app_table().query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"EVENT#signin#{today}"),
    )["Items"]
    return {
        "userCount": int(counters.get("userCount", 0)),
        "signinsToday": len(events),
        "activeToday": len({e["PK"] for e in events}),
    }
