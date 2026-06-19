"""Transaction & consistency invariants (LLD §5)."""

import pytest

from app.services import db


def test_create_user_idempotent(tables):
    assert db.create_user("u1", "a@b.com", "google") is True
    assert db.create_user("u1", "a@b.com", "google") is False  # returning user
    metrics = db.admin_metrics()
    assert metrics["userCount"] == 1  # counter not double-incremented


def test_email_summaries_default_on_and_toggle(tables):
    db.create_user("u1", "a@b.com", "google")
    assert db.get_user("u1")["emailSummaries"] is True  # default opt-in
    db.update_user("u1", {"emailSummaries": False})
    assert db.get_user("u1")["emailSummaries"] is False  # opt-out persists
    db.update_user("u1", {"emailSummaries": True})
    assert db.get_user("u1")["emailSummaries"] is True


def test_user_cap(tables, monkeypatch):
    monkeypatch.setattr(db.settings, "MAX_USERS", 2)
    db.create_user("u1", "a@b.com", "google")
    db.create_user("u2", "b@b.com", "google")
    with pytest.raises(db.CapExceeded):
        db.create_user("u3", "c@b.com", "google")
    assert db.admin_metrics()["userCount"] == 2


def test_lens_cap(tables):
    db.create_user("u1", "a@b.com", "google")
    for i in range(5):
        db.create_lens("u1", f"lens{i}", ["macro-fed"], [])
    with pytest.raises(db.CapExceeded):
        db.create_lens("u1", "lens5", ["macro-fed"], [])
    assert len(db.list_lenses("u1")) == 5


def test_lens_delete_decrements(tables):
    db.create_user("u1", "a@b.com", "google")
    lens = db.create_lens("u1", "L", ["macro-fed"], ["NVDA"])
    db.delete_lens("u1", lens["lensId"])
    assert db.list_lenses("u1") == []
    # Counter back to 0 → can create 5 again
    for i in range(5):
        db.create_lens("u1", f"l{i}", ["macro-fed"], [])


def test_delete_missing_lens_raises(tables):
    db.create_user("u1", "a@b.com", "google")
    with pytest.raises(db.Conflict):
        db.delete_lens("u1", "nonexistent")
    # lensCount must not go negative
    profile = db.get_user("u1")
    assert int(profile["lensCount"]) == 0


def test_generated_summary_never_clobbers_user_edit(tables):
    db.create_user("u1", "a@b.com", "google")
    assert db.put_generated_summary("u1", "lens1", "2026-06-12", "v1", [], "r1") is True
    # User edits
    new_version = db.save_user_summary_edit("u1", "lens1", "2026-06-12", "my edit", 1)
    assert new_version == 2
    # Regeneration is skipped
    assert db.put_generated_summary("u1", "lens1", "2026-06-12", "v2", [], "r2") is False
    assert db.get_summary("u1", "lens1", "2026-06-12")["body"] == "my edit"


def test_summary_edit_version_conflict(tables):
    db.create_user("u1", "a@b.com", "google")
    db.put_generated_summary("u1", "lens1", "2026-06-12", "v1", [], "")
    db.save_user_summary_edit("u1", "lens1", "2026-06-12", "edit A", 1)
    with pytest.raises(db.Conflict):
        db.save_user_summary_edit("u1", "lens1", "2026-06-12", "edit B", 1)  # stale


def test_summary_regeneration_overwrites_unedited(tables):
    db.create_user("u1", "a@b.com", "google")
    db.put_generated_summary("u1", "lens1", "2026-06-12", "v1", [], "")
    assert db.put_generated_summary("u1", "lens1", "2026-06-12", "v2", [], "") is True
    assert db.get_summary("u1", "lens1", "2026-06-12")["body"] == "v2"


def test_signin_events_and_metrics(tables):
    db.create_user("u1", "a@b.com", "google")
    db.record_signin("u1", "google")
    db.record_signin("u1", "google")
    m = db.admin_metrics()
    assert m["signinsToday"] == 2
    assert m["activeToday"] == 1


def test_feedback_gsi(tables):
    db.create_user("u1", "a@b.com", "google")
    db.put_feedback("u1", "great app", None)
    db.put_feedback("u1", "found a bug", "lens page")
    items = db.list_feedback()
    assert len(items) == 2
    assert items[0]["text"] == "found a bug"  # newest first
