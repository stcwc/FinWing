#!/usr/bin/env python3
"""Backfill feed-index edges for a newly added topic (LLD §8.4): match the
last N days of stored articles (which already carry embeddings) against the
new topic's vector + aliases, so the topic isn't empty on day one.

Usage: python backfill_topic.py --table finwing-content-beta --topic theme-ai --days 14
"""

import argparse
import os
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import boto3
import numpy as np

SIM_THRESHOLD = 0.68


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2",
    )
    args = parser.parse_args()

    table = boto3.resource("dynamodb", region_name=args.region).Table(args.table)

    topic = table.get_item(Key={"PK": f"TOPICDEF#{args.topic}", "SK": "DEF"}).get("Item")
    if not topic or "embedding" not in topic:
        raise SystemExit(f"Topic {args.topic} not found or not embedded — run seed first")
    topic_emb = np.frombuffer(bytes(topic["embedding"]), dtype=np.float16).astype(np.float32)
    topic_emb /= np.linalg.norm(topic_emb)

    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat()
    written, scanned, start_key = 0, 0, None
    while True:
        kwargs = {"ExclusiveStartKey": start_key} if start_key else {}
        resp = table.scan(**kwargs)
        for item in resp["Items"]:
            if not (item["PK"].startswith("ART#") and item["SK"] == "META"):
                continue
            if "embedding" not in item or item.get("publishedAt", "") < cutoff:
                continue
            scanned += 1
            art_emb = np.frombuffer(bytes(item["embedding"]), dtype=np.float16).astype(np.float32)
            art_emb /= np.linalg.norm(art_emb)
            score = float(np.dot(art_emb, topic_emb))
            if score < SIM_THRESHOLD:
                continue
            article_id = item["PK"].split("#", 1)[1]
            table.put_item(
                Item={
                    "PK": f"TOPIC#{args.topic}",
                    "SK": f"TS#{item['publishedAt']}#{article_id}",
                    "title": item["title"],
                    "excerpt": item.get("excerpt", ""),
                    "abstraction": item.get("abstraction"),
                    "source": item.get("source", ""),
                    "url": item["url"],
                    "score": Decimal(str(round(score, 4))),
                    "ttl": int(time.time()) + 30 * 86400,
                }
            )
            written += 1
        start_key = resp.get("LastEvaluatedKey")
        if not start_key:
            break

    print(f"Scanned {scanned} embedded articles, wrote {written} feed-index items for {args.topic}")


if __name__ == "__main__":
    main()
