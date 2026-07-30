"""Graceful truncation: a budget-exhausted answer is trimmed to the last full
sentence (EN + ZH) rather than cut mid-word, and a localized note is appended."""

from app.services.chat import _more_note, _trim_to_sentence


def test_trim_chinese_to_full_sentence():
    assert _trim_to_sentence("句子一。句子二没有说完") == "句子一。"


def test_trim_english_to_full_sentence():
    assert _trim_to_sentence("First point. Second one unfinished") == "First point."


def test_trim_keeps_trailing_close_quote():
    assert _trim_to_sentence('He said "done." Then more') == 'He said "done."'


def test_trim_no_boundary_returns_text():
    assert _trim_to_sentence("no terminator here") == "no terminator here"


def test_more_note_is_localized():
    assert "展开" in _more_note("zh")
    assert "expand" in _more_note("en")
    # unknown language falls back to English
    assert _more_note("fr") == _more_note("en")
