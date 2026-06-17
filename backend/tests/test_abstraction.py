"""Abstraction JSON parsing (bilingual output)."""

from workers.abstraction import _parse_json


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
