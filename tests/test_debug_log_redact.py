"""Tests for debug log URL redaction."""

from __future__ import annotations

from file_reader.smartedu.debug_log import redact_url_for_log


def test_redact_url_for_log_strips_query() -> None:
    """Signed query parameters are removed from log output."""
    redacted = redact_url_for_log(
        "https://finder.video.qq.com/stodownload?encfilekey=secret&token=abc",
    )
    assert "secret" not in redacted
    assert "token=" not in redacted
    assert redacted.startswith("https://finder.video.qq.com/stodownload")
