"""Unit tests for WeCom config URL validation and profile loading."""

from __future__ import annotations

import pytest

from services.integrations.wecom.config import (
    build_webhook_upload_media_url,
    load_wecom_profile,
    validate_wecom_webhook_url,
)


VALID_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=693a91f6-7xxx-4bc4-97a0-0ec2sifa5aaa"


def test_validate_wecom_webhook_url_accepts_official_shape() -> None:
    """Official webhook URL host/path/key passes validation."""
    assert validate_wecom_webhook_url(VALID_WEBHOOK_URL) == VALID_WEBHOOK_URL


@pytest.mark.parametrize(
    "url",
    [
        "http://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc",
        "https://evil.example.com/cgi-bin/webhook/send?key=abc",
        "https://qyapi.weixin.qq.com/cgi-bin/other/send?key=abc",
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send",
    ],
)
def test_validate_wecom_webhook_url_rejects_invalid(url: str) -> None:
    """SSRF guard rejects non-official webhook URLs."""
    assert validate_wecom_webhook_url(url) is None


def test_build_webhook_upload_media_url() -> None:
    """upload_media URL uses key from webhook URL (99110)."""
    url = build_webhook_upload_media_url(VALID_WEBHOOK_URL, "file")
    assert url is not None
    assert "upload_media" in url
    assert "type=file" in url


def test_load_profile_parses_userid_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    """Profile env vars parse comma-separated userids."""
    monkeypatch.setenv(
        "WECOM_PROFILE_SCHOOL_CONSULT_WEBHOOK_URL",
        VALID_WEBHOOK_URL,
    )
    monkeypatch.setenv(
        "WECOM_PROFILE_SCHOOL_CONSULT_WEBHOOK_MENTION_USERIDS",
        "alice, bob",
    )
    monkeypatch.setenv(
        "WECOM_PROFILE_SCHOOL_CONSULT_NOTIFY_USERIDS",
        "carol",
    )

    profile = load_wecom_profile("school_consult")
    assert profile.webhook_url == VALID_WEBHOOK_URL
    assert profile.webhook_mention_userids == ("alice", "bob")
    assert profile.notify_userids == ("carol",)
    assert profile.is_enabled is True
