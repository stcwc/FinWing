"""Chat attachment formatting (drag-a-tile-to-chat context)."""

from app.services.chat import _format_attachments


def test_format_attachments_includes_title_source_content_url():
    out = _format_attachments(
        [{"title": "Fed holds rates", "source": "Reuters", "content": "The Fed kept rates steady.", "url": "https://x/1"}]
    )
    assert "Reuters" in out
    assert "Fed holds rates" in out
    assert "The Fed kept rates steady." in out
    assert "https://x/1" in out


def test_format_attachments_handles_missing_fields():
    out = _format_attachments([{"title": "Headline only"}])
    assert "Headline only" in out
    assert "source unknown" in out


def test_format_attachments_caps_at_ten():
    items = [{"title": f"t{i}", "source": "s", "content": "c", "url": "u"} for i in range(15)]
    out = _format_attachments(items)
    assert "t9" in out
    assert "t10" not in out
