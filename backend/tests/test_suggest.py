"""Interest -> topic/asset suggestion (Claude call mocked)."""

from types import SimpleNamespace

import pytest

from app.services import suggest


class _FakeMessages:
    def __init__(self, text):
        self._text = text

    def create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(text=self._text)])


class _FakeClient:
    def __init__(self, text):
        self.messages = _FakeMessages(text)


@pytest.fixture(autouse=True)
def _no_key(monkeypatch):
    monkeypatch.setattr(suggest.settings, "anthropic_api_key", lambda: "test")


def _patch_response(monkeypatch, text):
    monkeypatch.setattr(suggest.anthropic, "Anthropic", lambda api_key: _FakeClient(text))


def test_suggest_filters_to_known_ids(monkeypatch):
    _patch_response(
        monkeypatch,
        '{"topicIds": ["macro-fed", "fx-theme-usd", "not-a-topic"], "assetIds": ["DXY", "FAKE"]}',
    )
    out = suggest.suggest("US national debt and the US dollar")
    assert out["topicIds"] == ["macro-fed", "fx-theme-usd"]  # invalid dropped
    assert out["assetIds"] == ["DXY"]  # invalid dropped


def test_suggest_handles_code_fences(monkeypatch):
    _patch_response(
        monkeypatch,
        '```json\n{"topicIds": ["bond-us10y"], "assetIds": []}\n```',
    )
    out = suggest.suggest("treasuries")
    assert out["topicIds"] == ["bond-us10y"]


def test_suggest_handles_surrounding_prose(monkeypatch):
    _patch_response(
        monkeypatch,
        'Here are the topics:\n{"topicIds": ["crypto-btc"], "assetIds": ["BTC"]}\nHope this helps!',
    )
    out = suggest.suggest("bitcoin")
    assert out["topicIds"] == ["crypto-btc"]
    assert out["assetIds"] == ["BTC"]


def test_suggest_dedupes_and_caps(monkeypatch):
    dupes = ", ".join('"macro-fed"' for _ in range(15))
    _patch_response(monkeypatch, f'{{"topicIds": [{dupes}], "assetIds": []}}')
    out = suggest.suggest("fed")
    assert out["topicIds"] == ["macro-fed"]  # deduped


def test_suggest_bad_json_returns_empty(monkeypatch):
    _patch_response(monkeypatch, "I cannot help with that.")
    out = suggest.suggest("???")
    assert out == {"topicIds": [], "assetIds": []}
