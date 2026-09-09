"""Token-usage cost estimation + best-effort logging."""

import json

from app import settings
from app.services import usage


class _Usage:
    def __init__(self, i, o, cr=0, cw=0):
        self.input_tokens = i
        self.output_tokens = o
        self.cache_read_input_tokens = cr
        self.cache_creation_input_tokens = cw


class _Resp:
    def __init__(self, u):
        self.usage = u


def test_cost_haiku_plain():
    # 1M input + 1M output on Haiku = $1 + $5
    assert usage._cost(settings.HAIKU_MODEL, 1_000_000, 1_000_000, 0, 0) == 6.0


def test_cost_sonnet_plain():
    assert usage._cost(settings.SONNET_MODEL, 1_000_000, 1_000_000, 0, 0) == 18.0


def test_cost_cache_discounts():
    # cache read at 0.1x input, cache write at 1.25x input
    c = usage._cost(settings.HAIKU_MODEL, 0, 0, 1_000_000, 1_000_000)
    assert round(c, 4) == round(0.1 + 1.25, 4)


def test_unknown_model_is_zero_cost():
    assert usage._cost("some-future-model", 1_000_000, 1_000_000, 0, 0) == 0.0


def test_log_usage_emits_json(capsys):
    usage.log_usage("summary", settings.HAIKU_MODEL, _Resp(_Usage(1000, 200)), userId="u1")
    line = capsys.readouterr().out.strip().splitlines()[-1]
    rec = json.loads(line)
    assert rec["event"] == "llm_usage"
    assert rec["call"] == "summary"
    assert rec["inputTokens"] == 1000 and rec["outputTokens"] == 200
    assert rec["userId"] == "u1"
    assert rec["estCostUsd"] == round((1000 * 1.0 + 200 * 5.0) / 1_000_000, 6)


def test_log_usage_missing_usage_is_noop(capsys):
    usage.log_usage("chat", settings.HAIKU_MODEL, object())
    assert capsys.readouterr().out.strip() == ""
