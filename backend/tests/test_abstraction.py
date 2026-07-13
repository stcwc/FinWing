"""Abstraction JSON parsing (bilingual output)."""

from workers.abstraction import ABSTRACTION_KEYS, _parse_json, parse_fields


def test_parse_plain_json():
    out = _parse_json('{"abstraction_en": "A", "abstraction_zh": "甲", "title_zh": "标题"}')
    assert out["abstraction_en"] == "A"
    assert out["abstraction_zh"] == "甲"
    assert out["title_zh"] == "标题"


def test_parse_code_fenced():
    out = _parse_json('```json\n{"abstraction_en": "x", "abstraction_zh": "", "title_zh": ""}\n```')
    assert out["abstraction_en"] == "x"


def test_parse_with_surrounding_prose():
    out = _parse_json('Sure:\n{"abstraction_en": "y", "abstraction_zh": "乙", "title_zh": "t"}\nDone')
    assert out["abstraction_zh"] == "乙"


def test_parse_garbage_returns_empty():
    assert _parse_json("not json at all") == {}


def test_parse_fields_strict_path():
    raw = '{"abstraction_en": "A", "abstraction_zh": "甲", "title_zh": "标题"}'
    out = parse_fields(raw, ABSTRACTION_KEYS)
    assert out == {"abstraction_en": "A", "abstraction_zh": "甲", "title_zh": "标题"}


def test_parse_fields_recovers_unescaped_inner_quotes():
    # Real failure mode: Haiku emits a Chinese term in raw double-quotes, which
    # breaks json.loads — strict parse returns {}, tolerant extraction recovers it.
    raw = (
        '```json\n{"abstraction_en": "Altcoins rallied in what traders call "altseason".",'
        ' "abstraction_zh": "山寨币在交易员所称的"山寨季"中上涨。",'
        ' "title_zh": "山寨季来临"}\n```'
    )
    assert _parse_json(raw) == {}  # strict json can't handle it
    out = parse_fields(raw, ABSTRACTION_KEYS)
    assert out["abstraction_en"].startswith("Altcoins rallied")
    assert "山寨季" in out["abstraction_zh"]
    assert out["title_zh"] == "山寨季来临"
