"""Structured token-usage logging for Claude calls.

The app otherwise logs no token counts, so per-workload spend is invisible.
`log_usage` emits one JSON line per model call — filter CloudWatch Logs Insights
on `event="llm_usage"` and sum `estCostUsd` to total spend by `call`/`model`.

Pricing is $ per 1M tokens (input, output). Cache reads bill at 0.1x input and
cache writes at 1.25x input (Anthropic standard). `usage.input_tokens` from the
API already excludes cached tokens, so the three input buckets are additive.
Keep these rates in sync with the Anthropic Console."""

import json

from app import settings

_PRICING = {
    settings.SONNET_MODEL: (3.0, 15.0),
    settings.HAIKU_MODEL: (1.0, 5.0),
}


def _cost(model: str, in_tok: int, out_tok: int, cache_read: int, cache_write: int) -> float:
    p_in, p_out = _PRICING.get(model, (0.0, 0.0))
    return (
        in_tok * p_in
        + cache_read * p_in * 0.1
        + cache_write * p_in * 1.25
        + out_tok * p_out
    ) / 1_000_000


def log_usage(call: str, model: str, resp, **extra) -> None:
    """Log token usage + estimated cost for one Claude response. Best-effort:
    never raises (a logging failure must not break the caller)."""
    try:
        u = getattr(resp, "usage", None)
        if u is None:
            return
        in_tok = getattr(u, "input_tokens", 0) or 0
        out_tok = getattr(u, "output_tokens", 0) or 0
        cache_read = getattr(u, "cache_read_input_tokens", 0) or 0
        cache_write = getattr(u, "cache_creation_input_tokens", 0) or 0
        cost = _cost(model, in_tok, out_tok, cache_read, cache_write)
        print(json.dumps({
            "level": "INFO", "event": "llm_usage", "call": call, "model": model,
            "inputTokens": in_tok, "outputTokens": out_tok,
            "cacheReadTokens": cache_read, "cacheWriteTokens": cache_write,
            "estCostUsd": round(cost, 6), **extra,
        }))
    except Exception as e:  # noqa: BLE001 — logging must never break the request
        print(json.dumps({"level": "WARN", "event": "llm_usage_error", "error": str(e)}))
