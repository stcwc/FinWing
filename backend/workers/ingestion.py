"""Ingestion worker (LLD §6.2): polls RSS + Finnhub news every minute,
conditional GETs, dedupes by URL hash, enqueues new articles for matching.

Feed source list comes from SSM; per-source ETag/Last-Modified state lives in
the Content table (SRC# items) so it survives across invocations."""

import hashlib
import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import boto3
import feedparser
import requests

from app import settings
from app.services.db import content_table, utcnow

MAX_ITEMS_PER_SOURCE = 20
EXCERPT_MAX = 500

_sqs = None


def sqs():
    global _sqs
    if _sqs is None:
        _sqs = boto3.client("sqs", region_name=settings.AWS_REGION)
    return _sqs


def article_id_for(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def load_sources() -> list[dict]:
    ssm = boto3.client("ssm", region_name=settings.AWS_REGION)
    raw = ssm.get_parameter(Name=f"/finwing/{settings.ENV}/feed-sources")["Parameter"]["Value"]
    return json.loads(raw)["sources"]


def get_source_state(source_id: str) -> dict:
    resp = content_table().get_item(Key={"PK": f"SRC#{source_id}", "SK": "STATE"})
    return resp.get("Item", {})


def save_source_state(source_id: str, etag: str | None, last_modified: str | None) -> None:
    item = {"PK": f"SRC#{source_id}", "SK": "STATE", "updatedAt": utcnow()}
    if etag:
        item["etag"] = etag
    if last_modified:
        item["lastModified"] = last_modified
    content_table().put_item(Item=item)


def fetch_rss(src: dict) -> list[dict]:
    state = get_source_state(src["id"])
    headers = {"User-Agent": "FinWing/1.0 (+https://finwingnews.com)"}
    if state.get("etag"):
        headers["If-None-Match"] = state["etag"]
    if state.get("lastModified"):
        headers["If-Modified-Since"] = state["lastModified"]

    resp = requests.get(src["url"], headers=headers, timeout=10)
    if resp.status_code == 304:
        return []
    resp.raise_for_status()
    save_source_state(src["id"], resp.headers.get("ETag"), resp.headers.get("Last-Modified"))

    feed = feedparser.parse(resp.content)
    items = []
    for entry in feed.entries[:MAX_ITEMS_PER_SOURCE]:
        url = entry.get("link")
        if not url:
            continue
        published = _parse_published(entry)
        items.append(
            {
                "url": url,
                "title": strip_html(entry.get("title", ""))[:300],
                "excerpt": strip_html(entry.get("summary", ""))[:EXCERPT_MAX],
                "source": feed.feed.get("title", src["id"])[:80],
                "publishedAt": published,
            }
        )
    return items


def _parse_published(entry) -> str:
    for field in ("published", "updated"):
        raw = entry.get(field)
        if raw:
            try:
                return parsedate_to_datetime(raw).astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError):
                pass
    if entry.get("published_parsed"):
        return datetime.fromtimestamp(
            time.mktime(entry.published_parsed), tz=timezone.utc
        ).isoformat()
    return utcnow()


def fetch_finnhub(src: dict) -> list[dict]:
    resp = requests.get(
        "https://finnhub.io/api/v1/news",
        params={"category": src["category"], "token": settings.finnhub_api_key()},
        timeout=10,
    )
    resp.raise_for_status()
    items = []
    for raw in resp.json()[:MAX_ITEMS_PER_SOURCE]:
        if not raw.get("url"):
            continue
        items.append(
            {
                "url": raw["url"],
                "title": (raw.get("headline") or "")[:300],
                "excerpt": strip_html(raw.get("summary", ""))[:EXCERPT_MAX],
                "source": raw.get("source", "Finnhub")[:80],
                "publishedAt": datetime.fromtimestamp(
                    raw.get("datetime", time.time()), tz=timezone.utc
                ).isoformat(),
            }
        )
    return items


def write_article(article_id: str, item: dict) -> bool:
    """Conditional put — returns False if the article already exists."""
    from botocore.exceptions import ClientError

    try:
        content_table().put_item(
            Item={
                "PK": f"ART#{article_id}",
                "SK": "META",
                "url": item["url"],
                "source": item["source"],
                "publishedAt": item["publishedAt"],
                "title": item["title"],
                "excerpt": item["excerpt"],
                "ttl": int(time.time()) + settings.ARTICLE_TTL_DAYS * 86400,
            },
            ConditionExpression="attribute_not_exists(PK)",
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def handler(event, context):
    new_ids = []
    for src in load_sources():
        try:
            items = fetch_rss(src) if src["type"] == "rss" else fetch_finnhub(src)
        except Exception as e:
            print(json.dumps({"level": "WARN", "source": src["id"], "error": str(e)}))
            continue
        for item in items:
            aid = article_id_for(item["url"])
            if write_article(aid, item):
                new_ids.append(aid)

    # Enqueue for matching, 10 per SQS batch
    for i in range(0, len(new_ids), 10):
        batch = new_ids[i : i + 10]
        sqs().send_message_batch(
            QueueUrl=settings.MATCHING_QUEUE_URL,
            Entries=[
                {"Id": str(n), "MessageBody": json.dumps({"articleId": aid})}
                for n, aid in enumerate(batch)
            ],
        )
    print(json.dumps({"level": "INFO", "newArticles": len(new_ids)}))
    return {"newArticles": len(new_ids)}
