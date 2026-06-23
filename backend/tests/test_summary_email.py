"""Daily digest email: one compacted email per user, opt-out, and tokens."""

import types

import pytest

from app.services import email, unsubscribe
from workers import summary_generator as sg


class _FakeResp:
    def __init__(self, text):
        self.content = [types.SimpleNamespace(type="text", text=text)]


@pytest.fixture
def wired(monkeypatch):
    """Stub everything the per-user handler touches; record digest sends."""
    sent = []

    monkeypatch.setattr(
        sg.db, "list_lenses",  # real DTO shape: lensId is pre-stripped (no "SK")
        lambda uid: [{"lensId": "a"}, {"lensId": "b"}],
    )
    monkeypatch.setattr(sg.db, "get_summary", lambda *a, **k: None)
    monkeypatch.setattr(
        sg.db, "get_lens",
        lambda uid, lid: {"name": f"Lens {lid}", "topicIds": ["t1"], "trackedAssetIds": []},
    )
    monkeypatch.setattr(
        sg, "fetch_articles_window",
        lambda *a, **k: [{"title": "x", "source": "Reuters", "abstraction": "y"}],
    )
    monkeypatch.setattr(sg.db, "list_summaries", lambda *a, **k: [])
    monkeypatch.setattr(sg.taxonomy, "topics", lambda: {"t1": {"displayName": "T1"}})
    monkeypatch.setattr(sg.prices, "move_for_date", lambda *a, **k: None)
    monkeypatch.setattr(sg, "client", lambda: types.SimpleNamespace(
        messages=types.SimpleNamespace(create=lambda **k: _FakeResp("## News\n\n- a"))
    ))
    monkeypatch.setattr(sg.db, "put_generated_summary", lambda *a, **k: True)
    monkeypatch.setattr(
        sg.email, "send_digest_email",
        lambda *a, **k: sent.append((a, k)) or True,
    )
    return sent


def _profile(opt=True, email="a@b.com"):
    return {"email": email, "language": "en", "emailSummaries": opt}


def test_one_digest_email_per_user_covers_all_lenses(wired, monkeypatch):
    monkeypatch.setattr(sg.db, "get_user", lambda *a, **k: _profile(opt=True))
    sg.handler({"userId": "u1", "date": "2026-06-18", "timezone": "UTC"}, None)
    assert len(wired) == 1                    # exactly one email, not one per lens
    sections = wired[0][0][3]                 # send_digest_email(email, uid, date, sections, lang)
    assert len(sections) == 2                 # both lenses compacted in
    assert {s["lensName"] for s in sections} == {"Lens a", "Lens b"}


def test_opt_out_sends_nothing(wired, monkeypatch):
    monkeypatch.setattr(sg.db, "get_user", lambda *a, **k: _profile(opt=False))
    sg.handler({"userId": "u1", "date": "2026-06-18", "timezone": "UTC"}, None)
    assert wired == []


def test_backfill_generate_never_emails(wired, monkeypatch):
    monkeypatch.setattr(sg.db, "get_user", lambda *a, **k: _profile(opt=True))
    # Backfill calls generate() per lens directly — it returns data but sends no email.
    section = sg.generate("u1", "a", "2026-06-18", "UTC", language="en")
    assert section and section["lensName"] == "Lens a"
    assert wired == []


def test_noop_write_excluded_from_digest(wired, monkeypatch):
    monkeypatch.setattr(sg.db, "get_user", lambda *a, **k: _profile(opt=True))
    monkeypatch.setattr(sg.db, "put_generated_summary", lambda *a, **k: False)
    sg.handler({"userId": "u1", "date": "2026-06-18", "timezone": "UTC"}, None)
    assert wired == []                        # no fresh sections → no email


def test_unsubscribe_token_roundtrip():
    tok = unsubscribe.make_token("user-123")
    assert unsubscribe.parse_token(tok) == "user-123"
    assert unsubscribe.parse_token("garbage") is None
    assert unsubscribe.parse_token(tok + "x") is None  # tampered


def test_digest_render_includes_unsubscribe_and_sections():
    sections = [
        {"lensName": "Tech", "body": "## News\n\n- **A**", "assetMoves": [{"symbol": "NVDA", "move": 1.2}]},
        {"lensName": "Macro", "body": "## Watch\n\n- B", "assetMoves": []},
    ]
    subj, html_body, text = email._render_digest("2026-06-18", sections, "en", "https://x/api/unsubscribe?token=t")
    assert "2 lenses" in subj
    assert "Tech" in html_body and "Macro" in html_body
    assert "NVDA" in html_body
    assert "unsubscribe" in html_body.lower()
