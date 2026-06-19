"""Daily-summary email send gate (workers/summary_generator.generate)."""

import types

import pytest

from workers import summary_generator as sg


class _FakeResp:
    def __init__(self, text):
        self.content = [types.SimpleNamespace(type="text", text=text)]


@pytest.fixture
def wired(monkeypatch):
    """Stub everything generate() touches; record email sends."""
    sent = []

    monkeypatch.setattr(sg.db, "get_summary", lambda *a, **k: None)
    monkeypatch.setattr(
        sg.db, "get_lens",
        lambda *a, **k: {"name": "Tech", "topicIds": ["t1"], "trackedAssetIds": []},
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
        sg.email, "send_summary_email",
        lambda *a, **k: sent.append((a, k)) or True,
    )
    return sent


def _profile(email="a@b.com", opt=True):
    return {"email": email, "language": "en", "emailSummaries": opt}


def test_daily_run_emails_when_opted_in(wired, monkeypatch):
    monkeypatch.setattr(sg.db, "get_user", lambda *a, **k: _profile(opt=True))
    sg.generate("u1", "l1", "2026-06-18", "UTC", notify_email=True)
    assert len(wired) == 1


def test_daily_run_skips_when_opted_out(wired, monkeypatch):
    monkeypatch.setattr(sg.db, "get_user", lambda *a, **k: _profile(opt=False))
    sg.generate("u1", "l1", "2026-06-18", "UTC", notify_email=True)
    assert wired == []


def test_backfill_never_emails(wired, monkeypatch):
    monkeypatch.setattr(sg.db, "get_user", lambda *a, **k: _profile(opt=True))
    # Backfill passes language explicitly and leaves notify_email at its default.
    sg.generate("u1", "l1", "2026-06-18", "UTC", language="en")
    assert wired == []


def test_no_email_when_write_was_noop(wired, monkeypatch):
    monkeypatch.setattr(sg.db, "get_user", lambda *a, **k: _profile(opt=True))
    monkeypatch.setattr(sg.db, "put_generated_summary", lambda *a, **k: False)
    sg.generate("u1", "l1", "2026-06-18", "UTC", notify_email=True)
    assert wired == []
