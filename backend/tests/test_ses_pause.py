"""SES reputation kill-switch: an ALARM notification disables config-set sending;
OK/INSUFFICIENT_DATA transitions are ignored."""

import json

from app import settings
from workers import ses_pause


def _sns(message: dict) -> dict:
    return {"Records": [{"Sns": {"Message": json.dumps(message)}}]}


def _capture(monkeypatch):
    calls = []
    monkeypatch.setattr(ses_pause, "_ses_client",
                        lambda: type("C", (), {"put_configuration_set_sending_options":
                            staticmethod(lambda **k: calls.append(k))})())
    monkeypatch.setattr(settings, "EMAIL_CONFIG_SET", "finwing-beta")
    return calls


def test_alarm_pauses_sending(monkeypatch):
    calls = _capture(monkeypatch)
    ses_pause.handler(_sns({
        "NewStateValue": "ALARM",
        "AlarmName": "finwing-ses-bounce-rate-beta",
    }), None)
    assert calls == [{"ConfigurationSetName": "finwing-beta", "SendingEnabled": False}]


def test_ok_transition_is_ignored(monkeypatch):
    calls = _capture(monkeypatch)
    ses_pause.handler(_sns({"NewStateValue": "OK", "AlarmName": "x"}), None)
    assert calls == []


def test_unset_config_set_is_a_noop(monkeypatch):
    calls = _capture(monkeypatch)
    monkeypatch.setattr(settings, "EMAIL_CONFIG_SET", "")
    ses_pause.handler(_sns({"NewStateValue": "ALARM", "AlarmName": "x"}), None)
    assert calls == []
