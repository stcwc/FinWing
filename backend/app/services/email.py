"""Summary-email delivery via Amazon SES.

The daily summary generator calls send_summary_email() after writing a summary.
Sending is best-effort: any failure (sandbox restriction, unverified recipient,
throttling) is logged and swallowed so it never blocks summary generation.

Summaries are markdown; we render the small subset the summary prompt emits
(## headers, **bold**, `- ` bullets, paragraphs) to lightweight inline-styled
HTML, plus a plain-text alternative.
"""

import html
import json
import re

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app import settings
from app.services import unsubscribe

_ses = None


def _client():
    global _ses
    if _ses is None:
        _ses = boto3.client("sesv2", region_name=settings.AWS_REGION)
    return _ses


def _md_inline(text: str) -> str:
    """Escape HTML, then apply inline markdown (**bold**, *italic*)."""
    out = html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", out)
    return out


def _markdown_to_html(md: str) -> str:
    """Render the summary markdown subset to inline-styled HTML blocks."""
    lines = md.splitlines()
    blocks: list[str] = []
    para: list[str] = []
    bullets: list[str] = []

    def flush_para():
        if para:
            blocks.append(
                f'<p style="margin:0 0 12px;line-height:1.6;color:#1f2933;">'
                f'{"<br>".join(_md_inline(l) for l in para)}</p>'
            )
            para.clear()

    def flush_bullets():
        if bullets:
            items = "".join(
                f'<li style="margin:0 0 4px;line-height:1.5;color:#1f2933;">{_md_inline(b)}</li>'
                for b in bullets
            )
            blocks.append(f'<ul style="margin:0 0 12px;padding-left:20px;">{items}</ul>')
            bullets.clear()

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_para()
            flush_bullets()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para()
            flush_bullets()
            level = min(len(m.group(1)), 3)
            size = {1: 18, 2: 16, 3: 14}[level]
            blocks.append(
                f'<h{level} style="margin:18px 0 8px;font-size:{size}px;'
                f'font-weight:600;color:#0b3d2e;">{_md_inline(m.group(2))}</h{level}>'
            )
            continue
        bm = re.match(r"^[-*]\s+(.*)$", line)
        if bm:
            flush_para()
            bullets.append(bm.group(1))
            continue
        flush_bullets()
        para.append(line)

    flush_para()
    flush_bullets()
    return "\n".join(blocks)


def _moves_html(asset_moves: list[dict]) -> str:
    if not asset_moves:
        return ""
    chips = []
    for m in asset_moves:
        up = float(m["move"]) >= 0
        color = "#0b8457" if up else "#c0392b"
        arrow = "▲" if up else "▼"
        # Yields move in percentage points (small, 2dp); everything else in % change.
        is_yield = m.get("kind") == "yield"
        amount = f'{abs(float(m["move"])):.2f}pp' if is_yield else f'{abs(float(m["move"])):.1f}%'
        chips.append(
            f'<span style="display:inline-block;margin:0 6px 6px 0;padding:2px 8px;'
            f'border-radius:9999px;background:{color}1a;color:{color};font-size:12px;'
            f'font-weight:600;">{html.escape(str(m["symbol"]))} {arrow} '
            f'{amount}</span>'
        )
    return f'<div style="margin:0 0 16px;">{"".join(chips)}</div>'


def _strings(language: str, n: int) -> dict:
    if language == "zh":
        return {
            "subject": (f"{n} 个透镜的每日摘要 · {{date}}" if n > 1 else "每日摘要 · {date}"),
            "intro": "您关注主题的今日摘要：",
            "view": "在 FinWing 中查看",
            "footer": "您收到此邮件是因为已开启每日摘要推送。",
            "unsub": "退订",
        }
    return {
        "subject": (f"Your daily summary · {n} lenses · {{date}}" if n > 1
                    else "Your daily summary · {date}"),
        "intro": "Today's summary for the topics you follow:",
        "view": "View in FinWing",
        "footer": "You're receiving this because daily-summary emails are on.",
        "unsub": "Unsubscribe",
    }


def _section_html(section: dict, date: str) -> str:
    """One lens block inside the digest."""
    return (
        '<div style="margin:0 0 8px;padding:18px 20px;background:#ffffff;'
        'border:1px solid #e5e7eb;border-radius:12px;">'
        f'<div style="font-size:16px;font-weight:600;color:#0b3d2e;margin-bottom:12px;">'
        f'{html.escape(section["lensName"])}</div>'
        f'{_moves_html(section.get("assetMoves", []))}'
        f'{_markdown_to_html(section["body"])}'
        "</div>"
    )


def _render_digest(date: str, sections: list[dict], language: str,
                   unsubscribe_url: str | None) -> tuple[str, str, str]:
    s = _strings(language, len(sections))
    subject = s["subject"].format(date=date)

    cta = ""
    if settings.APP_URL:
        cta = (
            f'<a href="{html.escape(settings.APP_URL)}/summaries" '
            f'style="display:inline-block;margin:4px 0 0;padding:10px 18px;'
            f'background:#0b8457;color:#ffffff;border-radius:8px;text-decoration:none;'
            f'font-weight:600;font-size:14px;">{s["view"]}</a>'
        )

    unsub_html = ""
    if unsubscribe_url:
        unsub_html = (
            f' · <a href="{html.escape(unsubscribe_url)}" '
            f'style="color:#6b7280;text-decoration:underline;">{s["unsub"]}</a>'
        )

    blocks = "\n".join(_section_html(sec, date) for sec in sections)
    html_body = f"""<!DOCTYPE html>
<html><body style="margin:0;padding:0;background:#f4f5f7;">
  <div style="max-width:600px;margin:0 auto;padding:24px;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
    <div style="font-size:20px;font-weight:700;color:#0b3d2e;margin-bottom:4px;">FinWing</div>
    <div style="font-size:13px;color:#6b7280;margin-bottom:20px;">{html.escape(s["intro"])} · {html.escape(date)}</div>
    {blocks}
    <div style="margin-top:16px;">{cta}</div>
    <div style="font-size:11px;color:#9ca3af;margin-top:16px;line-height:1.5;">{html.escape(s["footer"])}{unsub_html}</div>
  </div>
</body></html>"""

    text_parts = [f"FinWing — daily summary · {date}\n"]
    for sec in sections:
        text_parts.append(f"\n=== {sec['lensName']} ===\n{sec['body']}\n")
    text_parts.append(f"\n{s['footer']}")
    if unsubscribe_url:
        text_parts.append(f"\n{s['unsub']}: {unsubscribe_url}")
    return subject, html_body, "".join(text_parts)


def send_digest_email(to_email: str, user_id: str, date: str, sections: list[dict],
                      language: str = "en") -> bool:
    """Send one digest email per user covering every lens with a fresh summary.
    Returns True on success, False on any failure (logged, never raised).

    Includes a one-click unsubscribe link + List-Unsubscribe headers so users can
    opt out without signing in (also satisfies SES/RFC 8058 bulk-sender norms)."""
    if not settings.EMAIL_SENDER:
        print(json.dumps({"level": "WARN", "msg": "EMAIL_SENDER unset; skipping digest email"}))
        return False
    if not sections:
        return False

    unsubscribe_url = unsubscribe.link_for(user_id)
    subject, html_body, text_body = _render_digest(date, sections, language, unsubscribe_url)
    source = f"{settings.EMAIL_SENDER_NAME} <{settings.EMAIL_SENDER}>"

    headers = []
    if unsubscribe_url:
        # RFC 2369 / RFC 8058 one-click unsubscribe.
        headers = [
            {"Name": "List-Unsubscribe", "Value": f"<{unsubscribe_url}>"},
            {"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"},
        ]

    params = {
        "FromEmailAddress": source,
        "Destination": {"ToAddresses": [to_email]},
        "Content": {
            "Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {"Data": text_body, "Charset": "UTF-8"},
                    "Html": {"Data": html_body, "Charset": "UTF-8"},
                },
                **({"Headers": headers} if headers else {}),
            }
        },
    }
    # Track bounces/complaints (→ SNS → auto-suppression) when a config set is set.
    if settings.EMAIL_CONFIG_SET:
        params["ConfigurationSetName"] = settings.EMAIL_CONFIG_SET

    try:
        _client().send_email(**params)
        print(json.dumps({"level": "INFO", "msg": "digest email sent", "to": to_email,
                          "date": date, "lenses": len(sections)}))
        return True
    except (ClientError, BotoCoreError) as e:
        print(json.dumps({"level": "ERROR", "msg": "digest email failed",
                          "to": to_email, "error": str(e)}))
        return False
