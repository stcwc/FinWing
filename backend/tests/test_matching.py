"""Matching logic — alias pre-filter and disambiguation (no model needed)."""

import numpy as np

from workers.matching import alias_candidates, _token_match


def _topic(mode, aliases, qualifiers=(), negative=()):
    return {
        "matchMode": mode,
        "aliases": [a.lower() for a in aliases],
        "qualifiers": [q.lower() for q in qualifiers],
        "negativeTerms": [n.lower() for n in negative],
        "embedding": np.zeros(4, dtype=np.float32),
        "displayName": "x",
    }


def test_exact_symbol_token_boundary():
    topics = {"nvda": _topic("exact-symbol", ["NVDA"])}
    assert "nvda" in alias_candidates("nvda beats earnings estimates", topics)
    # Substring inside another word must NOT match
    assert "nvda" not in alias_candidates("convdance is a word", topics)


def test_phrase_requires_qualifier():
    topics = {
        "fed": _topic("phrase", ["the Fed"], qualifiers=["rate", "policy", "inflation"]),
    }
    assert "fed" in alias_candidates("the fed signals rate cuts ahead", topics)
    assert "fed" not in alias_candidates("the fed building was repainted", topics)


def test_negative_terms_disqualify():
    topics = {
        "avax": _topic("phrase", ["avalanche"], negative=["snow avalanche", "ski"]),
    }
    assert "avax" in alias_candidates("avalanche network upgrade ships", topics)
    assert "avax" not in alias_candidates("ski resort closed after snow avalanche", topics)


def test_semantic_only_always_candidates():
    topics = {"ai": _topic("semantic-only", [])}
    # No lexical signal needed — embedding stage decides
    assert "ai" in alias_candidates("totally unrelated text", topics)


def test_token_match_case_insensitive():
    assert _token_match("nvda", "NVDA rallies 5%".lower())
    assert _token_match("o", "shares of o gained")
    assert not _token_match("o", "shares of oracle gained")
