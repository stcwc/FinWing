"""Matching worker (LLD §6.3): alias pre-filter → local embedding (bge-small)
→ cosine vs topic vectors → optional Haiku tie-break for the ambiguous band.

Runs as a container Lambda (fastembed ONNX model baked into the image).
Topic vectors are cached per container for an hour."""

import json
import re
import time
from decimal import Decimal

import boto3
import numpy as np
from boto3.dynamodb.conditions import Key

from app import settings
from app.services.db import content_table, utcnow

SIM_THRESHOLD = 0.68
TIE_BREAK_LOW = 0.58
MAX_TIE_BREAKS_PER_ARTICLE = 3
MAX_TOPICS_PER_ARTICLE = 5

_model = None
_topic_cache: dict | None = None
_cache_loaded_at: float = 0.0
_sqs = None


def get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        _model = TextEmbedding("BAAI/bge-small-en-v1.5")
    return _model


def sqs():
    global _sqs
    if _sqs is None:
        _sqs = boto3.client("sqs", region_name=settings.AWS_REGION)
    return _sqs


def load_topic_vectors() -> dict[str, dict]:
    global _topic_cache, _cache_loaded_at
    if _topic_cache is not None and time.time() - _cache_loaded_at < 3600:
        return _topic_cache

    items, start_key = [], None
    while True:
        kwargs = {"FilterExpression": Key("SK").eq("DEF")}
        # TOPICDEF# partitions are enumerated via scan: ~100 small items, rare.
        scan_kwargs = {}
        if start_key:
            scan_kwargs["ExclusiveStartKey"] = start_key
        resp = content_table().scan(**scan_kwargs)
        items.extend(
            i for i in resp["Items"] if i["PK"].startswith("TOPICDEF#") and i["SK"] == "DEF"
        )
        start_key = resp.get("LastEvaluatedKey")
        if not start_key:
            break

    cache = {}
    for item in items:
        if item.get("status") != "active" or "embedding" not in item:
            continue
        emb = np.frombuffer(bytes(item["embedding"]), dtype=np.float16).astype(np.float32)
        emb /= np.linalg.norm(emb)
        cache[item["PK"].split("#", 1)[1]] = {
            "embedding": emb,
            "aliases": [a.lower() for a in item.get("aliases", [])],
            "matchMode": item.get("matchMode", "semantic-only"),
            "qualifiers": [q.lower() for q in item.get("qualifiers", [])],
            "negativeTerms": [n.lower() for n in item.get("negativeTerms", [])],
            "displayName": item.get("displayName", ""),
        }
    _topic_cache, _cache_loaded_at = cache, time.time()
    return cache


def _token_match(alias: str, text: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", text, re.I) is not None


def alias_candidates(text_lower: str, topics: dict) -> set[str]:
    """Step 1: cheap lexical pre-filter. semantic-only topics always pass
    through to the embedding stage."""
    candidates = set()
    for tid, tv in topics.items():
        mode = tv["matchMode"]
        if mode == "semantic-only":
            candidates.add(tid)
            continue
        if any(n in text_lower for n in tv["negativeTerms"]):
            continue
        if mode == "exact-symbol":
            if any(_token_match(a, text_lower) for a in tv["aliases"]):
                candidates.add(tid)
        else:  # phrase
            alias_hit = any(a in text_lower for a in tv["aliases"])
            qualifier_ok = not tv["qualifiers"] or any(q in text_lower for q in tv["qualifiers"])
            if alias_hit and qualifier_ok:
                candidates.add(tid)
    return candidates


def embed_text(text: str) -> np.ndarray:
    emb = np.array(list(get_model().embed([text[:512]]))[0], dtype=np.float32)
    return emb / np.linalg.norm(emb)


def haiku_confirms(title: str, topic_name: str) -> bool:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key())
    resp = client.messages.create(
        model=settings.HAIKU_MODEL,
        max_tokens=5,
        messages=[
            {
                "role": "user",
                "content": (
                    f'Is this financial news headline about "{topic_name}"? '
                    f"Reply YES or NO only.\n\nHeadline: {title}"
                ),
            }
        ],
    )
    return resp.content[0].text.strip().upper().startswith("YES")


def match_article(article: dict, topics: dict) -> tuple[list[tuple[str, float]], np.ndarray]:
    text = f"{article['title']} {article.get('excerpt', '')}"
    text_lower = text.lower()

    article_emb = embed_text(text)
    candidates = alias_candidates(text_lower, topics)
    if not candidates:
        return [], article_emb
    matches, ambiguous = [], []
    for tid in candidates:
        score = float(np.dot(article_emb, topics[tid]["embedding"]))
        # Lexical hits (exact-symbol/phrase) get context-gated at a lower bar;
        # semantic-only must clear the full threshold.
        is_lexical = topics[tid]["matchMode"] != "semantic-only"
        if score >= SIM_THRESHOLD or (is_lexical and score >= TIE_BREAK_LOW + 0.04):
            matches.append((tid, score))
        elif TIE_BREAK_LOW <= score < SIM_THRESHOLD and not is_lexical:
            ambiguous.append((tid, score))

    ambiguous.sort(key=lambda x: -x[1])
    for tid, score in ambiguous[:MAX_TIE_BREAKS_PER_ARTICLE]:
        if haiku_confirms(article["title"], topics[tid]["displayName"]):
            matches.append((tid, score))

    matches.sort(key=lambda x: -x[1])
    return matches[:MAX_TOPICS_PER_ARTICLE], article_emb


def process_article(article_id: str) -> int:
    resp = content_table().get_item(Key={"PK": f"ART#{article_id}", "SK": "META"})
    article = resp.get("Item")
    if article is None or article.get("matchedTopicIds"):
        return 0  # gone or already matched (idempotent)

    topics = load_topic_vectors()
    matches, article_emb = match_article(article, topics)

    ttl = int(time.time()) + settings.ARTICLE_TTL_DAYS * 86400
    for tid, score in matches:
        content_table().put_item(
            Item={
                "PK": f"TOPIC#{tid}",
                "SK": f"TS#{article['publishedAt']}#{article_id}",
                "title": article["title"],
                "excerpt": article.get("excerpt", ""),
                "source": article.get("source", ""),
                "url": article["url"],
                "score": Decimal(str(round(score, 4))),
                "ttl": ttl,
            }
        )

    content_table().update_item(
        Key={"PK": f"ART#{article_id}", "SK": "META"},
        UpdateExpression="SET matchedTopicIds = :tids, embedding = :emb",
        ExpressionAttributeValues={
            ":tids": [t for t, _ in matches],
            ":emb": article_emb.astype(np.float16).tobytes(),
        },
    )

    if matches:
        sqs().send_message(
            QueueUrl=settings.ABSTRACTION_QUEUE_URL,
            MessageBody=json.dumps({"articleId": article_id}),
        )
    return len(matches)


def handler(event, context):
    matched = 0
    for record in event.get("Records", []):
        body = json.loads(record["body"])
        matched += process_article(body["articleId"])
    print(json.dumps({"level": "INFO", "records": len(event.get("Records", [])), "matches": matched}))
