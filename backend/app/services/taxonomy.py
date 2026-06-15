"""Taxonomy + asset catalog access. The YAML configs are bundled into the
Lambda package; used for write-path validation (topicIds/assetIds must exist)
and to serve /static JSON at build time."""

from functools import lru_cache
from pathlib import Path

import yaml

CONFIG_DIR = Path(__file__).resolve().parents[3] / "infra" / "config"


@lru_cache(maxsize=1)
def topics() -> dict[str, dict]:
    data = yaml.safe_load((CONFIG_DIR / "taxonomy.yaml").read_text())
    return {t["topicId"]: t for t in data["topics"]}


@lru_cache(maxsize=1)
def assets() -> dict[str, dict]:
    data = yaml.safe_load((CONFIG_DIR / "assets.yaml").read_text())
    return {a["assetId"]: a for a in data["assets"]}


def active_topic_ids() -> set[str]:
    return {tid for tid, t in topics().items() if t.get("status") == "active"}


def validate_topic_ids(topic_ids: list[str]) -> list[str]:
    """Returns unknown/deprecated IDs (empty list = all valid)."""
    valid = active_topic_ids()
    return [t for t in topic_ids if t not in valid]


def validate_asset_ids(asset_ids: list[str]) -> list[str]:
    catalog = assets()
    return [a for a in asset_ids if a not in catalog]


def suggested_assets_for_topics(topic_ids: list[str]) -> list[str]:
    """Union of the topics' default assetIds, order-preserving."""
    out: list[str] = []
    for tid in topic_ids:
        for aid in topics().get(tid, {}).get("assetIds", []):
            if aid not in out:
                out.append(aid)
    return out
