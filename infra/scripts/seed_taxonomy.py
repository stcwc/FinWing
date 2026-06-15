#!/usr/bin/env python3
"""Idempotent taxonomy + asset seed job (LLD §8.3). Runs on deploy.

- Upserts topics from taxonomy.yaml; re-embeds only when displayName/aliases/
  embeddingText or the pinned model version change.
- Topics removed from config are deprecated, never deleted.
- Seeds the asset catalog and writes /static JSON for the frontend.

Usage: python seed_taxonomy.py --table finwing-content-beta [--static-out DIR]
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
import yaml

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_existing_topics(table) -> dict:
    items, start_key = {}, None
    while True:
        kwargs = {"ExclusiveStartKey": start_key} if start_key else {}
        resp = table.scan(**kwargs)
        for item in resp["Items"]:
            if item["PK"].startswith("TOPICDEF#") and item["SK"] == "DEF":
                items[item["PK"].split("#", 1)[1]] = item
        start_key = resp.get("LastEvaluatedKey")
        if not start_key:
            return items


def needs_embed(existing: dict | None, topic: dict, model_version: str) -> bool:
    if existing is None or "embedding" not in existing:
        return True
    return (
        existing.get("displayName") != topic["displayName"]
        or set(existing.get("aliases", [])) != set(topic.get("aliases", []))
        or existing.get("embeddingText", "").strip() != topic["embeddingText"].strip()
        or existing.get("embeddingModelVersion") != model_version
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--table", required=True)
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-west-2",
    )
    parser.add_argument("--static-out", default=None,
                        help="Directory to write taxonomy.json/assets.json for the SPA")
    args = parser.parse_args()

    config = yaml.safe_load((CONFIG_DIR / "taxonomy.yaml").read_text())
    assets_config = yaml.safe_load((CONFIG_DIR / "assets.yaml").read_text())
    model_version = config["embeddingModelVersion"]

    table = boto3.resource("dynamodb", region_name=args.region).Table(args.table)
    existing = load_existing_topics(table)

    # Embed lazily — only import the model if at least one topic needs it
    to_embed = [
        t for t in config["topics"] if needs_embed(existing.get(t["topicId"]), t, model_version)
    ]
    embeddings = {}
    if to_embed:
        import numpy as np
        from fastembed import TextEmbedding

        model = TextEmbedding("BAAI/bge-small-en-v1.5")
        texts = [t["embeddingText"].strip() for t in to_embed]
        for topic, emb in zip(to_embed, model.embed(texts)):
            vec = np.array(emb, dtype=np.float16)
            embeddings[topic["topicId"]] = vec.tobytes()

    upserts = 0
    for topic in config["topics"]:
        tid = topic["topicId"]
        prev = existing.get(tid)
        item = {
            "PK": f"TOPICDEF#{tid}",
            "SK": "DEF",
            "category": topic["category"],
            "subgroup": topic["subgroup"],
            "displayName": topic["displayName"],
            "aliases": topic.get("aliases", []),
            "matchMode": topic.get("matchMode", "semantic-only"),
            "qualifiers": topic.get("qualifiers", []),
            "negativeTerms": topic.get("negativeTerms", []),
            "embeddingText": topic["embeddingText"].strip(),
            "assetIds": topic.get("assetIds", []),
            "status": topic.get("status", "active"),
            "version": int(prev["version"]) + 1 if prev else 1,
            "embeddingModelVersion": model_version,
            "createdAt": prev["createdAt"] if prev else utcnow(),
            "updatedAt": utcnow(),
        }
        if tid in embeddings:
            item["embedding"] = embeddings[tid]
        elif prev and "embedding" in prev:
            item["embedding"] = bytes(prev["embedding"])
        table.put_item(Item=item)
        upserts += 1

    # Deprecate topics no longer in config
    config_ids = {t["topicId"] for t in config["topics"]}
    deprecated = 0
    for tid in set(existing) - config_ids:
        table.update_item(
            Key={"PK": f"TOPICDEF#{tid}", "SK": "DEF"},
            UpdateExpression="SET #s = :dep, updatedAt = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={":dep": "deprecated", ":now": utcnow()},
        )
        deprecated += 1

    # Seed assets
    for asset in assets_config["assets"]:
        table.put_item(
            Item={
                "PK": f"ASSET#{asset['assetId']}",
                "SK": "META",
                "symbol": asset["symbol"],
                "name": asset["name"],
                "assetClass": asset["assetClass"],
                "finnhubSymbol": asset.get("finnhubSymbol", ""),
                "hasPriceFeed": asset.get("hasPriceFeed", False),
            }
        )

    # Static JSON for the SPA (served from S3/CloudFront)
    if args.static_out:
        out = Path(args.static_out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "taxonomy.json").write_text(
            json.dumps(
                [
                    {
                        "topicId": t["topicId"],
                        "category": t["category"],
                        "subgroup": t["subgroup"],
                        "displayName": t["displayName"],
                        "assetIds": t.get("assetIds", []),
                    }
                    for t in config["topics"]
                    if t.get("status", "active") == "active"
                ]
            )
        )
        (out / "assets.json").write_text(json.dumps(assets_config["assets"]))

    print(f"Seeded {upserts} topics ({len(to_embed)} re-embedded), "
          f"{deprecated} deprecated, {len(assets_config['assets'])} assets")


if __name__ == "__main__":
    sys.exit(main())
