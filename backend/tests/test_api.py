"""API route tests with auth dependency overridden."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import auth, db

USER = {"userId": "u1", "email": "a@b.com", "isAdmin": False, "authProvider": "google"}
ADMIN = {"userId": "adm", "email": "adm@b.com", "isAdmin": True, "authProvider": "email"}


@pytest.fixture
def client(tables):
    app.dependency_overrides[auth.current_user] = lambda: USER
    app.dependency_overrides[auth.require_admin] = lambda: ADMIN
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_signup_and_profile(client):
    resp = client.post("/users/me")
    assert resp.status_code == 200
    assert resp.json()["firstSignIn"] is True
    resp = client.post("/users/me")
    assert resp.json()["firstSignIn"] is False


def test_lens_crud_and_validation(client):
    client.post("/users/me")
    resp = client.post(
        "/lenses",
        json={"name": "Macro", "topicIds": ["macro-fed"], "trackedAssetIds": ["XAUUSD"]},
    )
    assert resp.status_code == 200
    lens_id = resp.json()["lensId"]

    # Unknown topic rejected
    resp = client.post("/lenses", json={"name": "Bad", "topicIds": ["nope"]})
    assert resp.status_code == 400

    # Topic count over limit rejected by Pydantic
    resp = client.post("/lenses", json={"name": "Big", "topicIds": ["macro-fed"] * 11})
    assert resp.status_code == 422

    resp = client.patch(f"/lenses/{lens_id}", json={"trackedAssetIds": ["XAUUSD", "BTC"]})
    assert resp.status_code == 200
    assert client.get(f"/lenses/{lens_id}").json()["trackedAssetIds"] == ["XAUUSD", "BTC"]

    assert client.delete(f"/lenses/{lens_id}").json()["ok"] is True
    assert client.get(f"/lenses/{lens_id}").status_code == 404


def test_lens_cap_returns_409(client):
    client.post("/users/me")
    for i in range(5):
        client.post("/lenses", json={"name": f"l{i}", "topicIds": ["macro-fed"]})
    resp = client.post("/lenses", json={"name": "l5", "topicIds": ["macro-fed"]})
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "LENS_CAP"


def test_feed_returns_merged_items(client):
    client.post("/users/me")
    lens_id = client.post(
        "/lenses", json={"name": "Macro", "topicIds": ["macro-fed"]}
    ).json()["lensId"]

    db.content_table().put_item(
        Item={
            "PK": "TOPIC#macro-fed",
            "SK": "TS#2026-06-12T10:00:00+00:00#a1",
            "title": "Fed news",
            "excerpt": "ex",
            "source": "Reuters",
            "url": "https://example.com",
        }
    )
    resp = client.get(f"/lenses/{lens_id}/feed")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["abstraction"] is None  # not yet abstracted → card shows excerpt


def test_summary_edit_flow(client):
    client.post("/users/me")
    db.put_generated_summary("u1", "lens1", "2026-06-12", "generated", [], "")
    resp = client.put(
        "/lenses/lens1/summaries/2026-06-12", json={"body": "my edit", "version": 1}
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == 2

    # Stale version → 409
    resp = client.put(
        "/lenses/lens1/summaries/2026-06-12", json={"body": "again", "version": 1}
    )
    assert resp.status_code == 409

    got = client.get("/lenses/lens1/summaries/2026-06-12").json()
    assert got["body"] == "my edit"
    assert got["editedByUser"] is True


def test_feedback_and_admin(client):
    client.post("/users/me")
    assert client.post("/feedback", json={"text": "nice"}).status_code == 200
    resp = client.get("/admin/feedback")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["text"] == "nice"
    metrics = client.get("/admin/metrics").json()
    assert metrics["userCount"] == 1


def test_language_preference(client):
    client.post("/users/me")
    assert client.get("/users/me").json()["language"] == "en"  # default
    assert client.patch("/users/me", json={"language": "zh"}).status_code == 200
    assert client.get("/users/me").json()["language"] == "zh"
    # invalid language rejected by validation
    assert client.patch("/users/me", json={"language": "fr"}).status_code == 422


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"
