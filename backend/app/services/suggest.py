"""Map a user's free-form interests to taxonomy topics + assets via Claude.

Used by onboarding: the user types something like "US national debt and the
US dollar" and Claude returns the relevant topic/asset IDs (including related
drivers), which the frontend pre-selects in the lens editor."""

import json
import re

import anthropic

from app import settings
from app.prompts import SUGGEST_SYSTEM
from app.services import taxonomy


def _build_catalogs() -> tuple[str, str]:
    topics = taxonomy.topics()
    assets = taxonomy.assets()
    topic_lines = [
        f"{tid}: {t['displayName']} ({t['category']} / {t['subgroup']})"
        for tid, t in topics.items()
        if t.get("status") == "active"
    ]
    asset_lines = [f"{aid}: {a['name']} [{a['symbol']}]" for aid, a in assets.items()]
    return "\n".join(topic_lines), "\n".join(asset_lines)


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    # Strip ``` or ```json fences if present.
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    # Fall back to the first {...} block.
    if not raw.startswith("{"):
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            raw = m.group(0)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def suggest(text: str) -> dict:
    topic_catalog, asset_catalog = _build_catalogs()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key())
    resp = client.messages.create(
        model=settings.HAIKU_MODEL,
        max_tokens=400,
        system=[
            {"type": "text", "text": SUGGEST_SYSTEM, "cache_control": {"type": "ephemeral"}},
            {
                "type": "text",
                "text": f"TOPIC CATALOG:\n{topic_catalog}\n\nASSET CATALOG:\n{asset_catalog}",
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[{"role": "user", "content": f"User interests: {text}\n\nReturn the JSON object."}],
    )
    data = _parse_json(resp.content[0].text)

    topics = taxonomy.topics()
    assets = taxonomy.assets()
    topic_ids, seen = [], set()
    for t in data.get("topicIds", []):
        if t in topics and topics[t].get("status") == "active" and t not in seen:
            topic_ids.append(t)
            seen.add(t)
    asset_ids, seen_a = [], set()
    for a in data.get("assetIds", []):
        if a in assets and a not in seen_a:
            asset_ids.append(a)
            seen_a.add(a)

    return {
        "topicIds": topic_ids[: settings.MAX_TOPICS_PER_LENS],
        "assetIds": asset_ids[: settings.MAX_ASSETS_PER_LENS],
    }
