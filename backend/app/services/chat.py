"""Chat side panel (HLD §3.7, LLD §7.6): single persistent conversation,
financial context injected fresh + prompt-cached every turn, history bounded
by a rolling window + running summary."""

import json
import time

import anthropic

from app import settings
from app.prompts import CHAT_SYSTEM, chat_language_line
from app.services import db

# Anthropic server-side web search, executed on Anthropic's infrastructure.
#
# We deliberately pin the OLDER web_search_20250305. The newer _20260209 version
# has "dynamic filtering" built in — it spins up a code-execution sandbox and
# runs code to filter results (surfacing code_execution_tool_result /
# bash_code_execution_tool_result blocks even though only web_search is
# declared). That sandbox is NOT bounded by max_uses and routinely ran 60–180s,
# blowing past the API Gateway / Lambda 30s request ceiling and timing the chat
# out. The 20250305 version does plain search with no code execution.
#
# max_uses bounds latency: each search round is ~10s, and the whole request must
# finish under 30s, so we cap at 2. web_fetch (full-page reads) is omitted — it's
# the slowest path and rarely needed, since attached articles already carry their
# content.
WEB_TOOLS = [
    {"type": "web_search_20250305", "name": "web_search", "max_uses": 2},
]

# Hard wall on the server tool-loop continuation (each iteration is another
# multi-second model call); 1 continuation is plenty within the 30s budget.
_MAX_TURNS = 2


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


def _format_attachments(attachments: list[dict]) -> str:
    lines = ["The user dragged in these news items as context for this question:"]
    for a in attachments[:10]:
        src = a.get("source") or "source unknown"
        lines.append(f"- [{src}] {a.get('title', '')}")
        if a.get("content"):
            lines.append(f"  {a['content']}")
        if a.get("url"):
            lines.append(f"  {a['url']}")
    return "\n".join(lines)


def respond(user_id: str, message: str, attachments: list[dict] | None = None) -> str:
    state = db.get_chat_state(user_id)
    window = db.recent_chat_turns(user_id, settings.CHAT_WINDOW_TURNS)

    # Store the human-typed message in history (keeps the transcript clean); the
    # attached article content is injected into this turn only.
    db.append_chat_turn(user_id, "user", message)

    language = (db.get_user(user_id) or {}).get("language", "en")
    system_blocks = [
        {"type": "text", "text": CHAT_SYSTEM, "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": chat_language_line(language)},
        {"type": "text", "text": _financial_context(user_id)},
    ]
    if state.get("runningSummary"):
        system_blocks.append(
            {"type": "text", "text": f"Earlier conversation summary:\n{state['runningSummary']}"}
        )

    turn_content = message
    if attachments:
        turn_content = f"{_format_attachments(attachments)}\n\nQuestion: {message}"
    messages: list = window + [{"role": "user", "content": turn_content}]

    client = _client()
    # The server runs its own loop for web search; if it hits the internal
    # iteration limit it returns stop_reason="pause_turn" — re-send to continue.
    t0 = time.time()
    resp = None
    for _ in range(_MAX_TURNS):
        resp = client.messages.create(
            model=settings.SONNET_MODEL,
            max_tokens=1500,
            system=system_blocks,
            tools=WEB_TOOLS,
            messages=messages,
        )
        if resp.stop_reason != "pause_turn":
            break
        messages.append({"role": "assistant", "content": resp.content})
    print(json.dumps({"level": "INFO", "event": "chat", "userId": user_id,
                      "elapsedMs": int((time.time() - t0) * 1000),
                      "stopReason": resp.stop_reason}))

    # Final answer is the text block(s); other blocks are server tool use/results.
    answer = "".join(b.text for b in resp.content if b.type == "text").strip()
    if not answer:
        answer = "I couldn't find an answer to that. Please try rephrasing."
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
