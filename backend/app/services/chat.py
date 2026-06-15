"""Chat side panel (HLD §3.7, LLD §7.6): single persistent conversation,
financial context injected fresh + prompt-cached every turn, history bounded
by a rolling window + running summary."""

import anthropic

from app import settings
from app.services import db

CHAT_SYSTEM = """You are FinWing's financial assistant. The user's investment context is below.
You may discuss news, market dynamics, and financial topics freely.
Never give buy/sell recommendations or financial advice.
Keep answers concise and grounded in the provided context where relevant."""


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key())


def _financial_context(user_id: str) -> str:
    lenses = db.list_lenses(user_id)
    from app.services import taxonomy

    topic_names = taxonomy.topics()
    lines = ["<user_context>", "Lenses:"]
    for lens in lenses:
        names = [topic_names.get(t, {}).get("displayName", t) for t in lens["topicIds"]]
        lines.append(f"- {lens['name']}: topics [{', '.join(names)}]")
        # Last 3 daily summaries per lens, truncated
        today = db.utcnow()[:10]
        summaries = db.list_summaries(user_id, lens["lensId"], "0000-00-00", today)[-3:]
        for s in summaries:
            lines.append(f"  {s['date']}: {s['body'][:200]}")
    lines.append("</user_context>")
    return "\n".join(lines)


def respond(user_id: str, message: str) -> str:
    state = db.get_chat_state(user_id)
    window = db.recent_chat_turns(user_id, settings.CHAT_WINDOW_TURNS)

    db.append_chat_turn(user_id, "user", message)

    system_blocks = [
        {"type": "text", "text": CHAT_SYSTEM, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": _financial_context(user_id)},
    ]
    if state.get("runningSummary"):
        system_blocks.append(
            {"type": "text", "text": f"Earlier conversation summary:\n{state['runningSummary']}"}
        )

    messages = window + [{"role": "user", "content": message}]
    resp = _client().messages.create(
        model=settings.HAIKU_MODEL,
        max_tokens=1024,
        system=system_blocks,
        messages=messages,
    )
    answer = resp.content[0].text.strip()
    db.append_chat_turn(user_id, "assistant", answer)

    total = int(state.get("totalTurns", 0)) + 2
    if total % (settings.CHAT_WINDOW_TURNS * 2) == 0:
        _compact(user_id, state, window)
    db.update_chat_state(user_id, state.get("runningSummary", ""), total)
    return answer


def _compact(user_id: str, state: dict, window: list[dict]) -> None:
    """Fold the oldest half of the window into the running summary."""
    if len(window) < 4:
        return
    older = window[: len(window) // 2]
    transcript = "\n".join(f"{t['role']}: {t['content'][:300]}" for t in older)
    resp = _client().messages.create(
        model=settings.HAIKU_MODEL,
        max_tokens=300,
        messages=[
            {
                "role": "user",
                "content": (
                    "Summarize this conversation segment in one short paragraph, "
                    "keeping any user preferences or open questions:\n\n"
                    f"{state.get('runningSummary', '')}\n\n{transcript}"
                ),
            }
        ],
    )
    db.update_chat_state(
        user_id, resp.content[0].text.strip(), int(state.get("totalTurns", 0))
    )
