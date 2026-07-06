"""Unit tests for WeCom webhook client (doc 99110 payload shape)."""

from __future__ import annotations

import pytest

from services.integrations.wecom.profiles import WeComNotifyProfile
from services.integrations.wecom.types import WeComMessage
from services.integrations.wecom import webhook_client, webhook_http


VALID_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=693a91f6-7xxx-4bc4-97a0-0ec2sifa5aaa"


@pytest.mark.asyncio
async def test_send_webhook_uses_markdown_content_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    """Webhook payload must use markdown.content (not DingTalk title/text)."""
    captured: dict[str, object] = {}

    async def _fake_post(url: str, payload: dict[str, object]) -> tuple[dict[str, object], None]:
        captured["url"] = url
        captured["payload"] = payload
        return {"errcode": 0, "errmsg": "ok"}, None

    async def _fake_post_safe(url: str, payload: dict[str, object], **_kwargs) -> tuple[dict[str, object], None]:
        return await _fake_post(url, payload)

    monkeypatch.setattr(webhook_http, "post_json_safe", _fake_post_safe)

    profile = WeComNotifyProfile(profile_id="school_consult", webhook_url=VALID_WEBHOOK_URL)
    message = WeComMessage(title="学校版咨询预约", fields={"姓名": "张三"})
    result = await webhook_client.send_webhook(profile, message)

    assert result.ok is True
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["msgtype"] == "markdown"
    markdown = payload["markdown"]
    assert isinstance(markdown, dict)
    assert "content" in markdown
    assert "title" not in markdown
    assert "text" not in markdown
    assert "张三" in str(markdown["content"])


@pytest.mark.asyncio
async def test_send_webhook_appends_userid_mentions(monkeypatch: pytest.MonkeyPatch) -> None:
    """@ mentions in webhook markdown use <@userid> syntax."""
    captured: dict[str, object] = {}

    async def _fake_post_safe(_url: str, payload: dict[str, object], **_kwargs) -> tuple[dict[str, object], None]:
        captured["payload"] = payload
        return {"errcode": 0, "errmsg": "ok"}, None

    monkeypatch.setattr(webhook_http, "post_json_safe", _fake_post_safe)

    profile = WeComNotifyProfile(
        profile_id="school_consult",
        webhook_url=VALID_WEBHOOK_URL,
        webhook_mention_userids=("sales_lead",),
    )
    message = WeComMessage(title="Title", fields={"字段": "值"})
    await webhook_client.send_webhook(profile, message)

    payload_obj = captured["payload"]
    assert isinstance(payload_obj, dict)
    markdown_obj = payload_obj["markdown"]
    assert isinstance(markdown_obj, dict)
    assert "<@sales_lead>" in str(markdown_obj["content"])


@pytest.mark.asyncio
async def test_send_webhook_non_zero_errcode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-zero errcode is treated as failure."""

    async def _fake_post_safe(_url: str, _payload: dict[str, object], **_kwargs) -> tuple[dict[str, object], None]:
        return {"errcode": 93000, "errmsg": "invalid webhook"}, None

    monkeypatch.setattr(webhook_http, "post_json_safe", _fake_post_safe)

    profile = WeComNotifyProfile(profile_id="school_consult", webhook_url=VALID_WEBHOOK_URL)
    message = WeComMessage(title="Title", fields={"字段": "值"})
    result = await webhook_client.send_webhook(profile, message)

    assert result.ok is False
    assert result.errcode == 93000
