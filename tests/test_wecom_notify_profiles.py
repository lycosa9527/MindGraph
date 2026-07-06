"""Unit tests for WeCom notify orchestrator and profiles."""

from __future__ import annotations

import pytest

from services.integrations.wecom.config import WeComCorpConfig
from services.integrations.wecom.orchestrator import notify
from services.integrations.wecom.profiles import WeComNotifyProfile
from services.integrations.wecom.types import WeComChannelResult, WeComMessage

NOTIFY_MODULE = "services.integrations.wecom.orchestrator"


@pytest.mark.asyncio
async def test_notify_returns_not_configured_when_profile_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabled profile returns not_configured without calling WeCom."""
    called = {"webhook": False, "app": False}

    async def _fake_webhook(*_args, **_kwargs) -> WeComChannelResult:
        called["webhook"] = True
        return WeComChannelResult(channel="webhook", ok=True)

    async def _fake_app(*_args, **_kwargs) -> WeComChannelResult:
        called["app"] = True
        return WeComChannelResult(channel="app_message", ok=True)

    monkeypatch.setattr(f"{NOTIFY_MODULE}.send_webhook", _fake_webhook)
    monkeypatch.setattr(f"{NOTIFY_MODULE}.send_app_message", _fake_app)
    monkeypatch.setattr(
        f"{NOTIFY_MODULE}.load_wecom_profile",
        lambda _pid: WeComNotifyProfile(profile_id="school_consult"),
    )

    result = await notify("school_consult", WeComMessage(title="T", fields={"k": "v"}))

    assert result.not_configured is True
    assert result.ok is False
    assert called["webhook"] is False
    assert called["app"] is False


@pytest.mark.asyncio
async def test_notify_success_if_any_channel_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    """Success when at least one channel returns errcode 0."""
    profile = WeComNotifyProfile(
        profile_id="school_consult",
        webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc",
        notify_userids=("u1",),
    )

    async def _fake_webhook(*_args, **_kwargs) -> WeComChannelResult:
        return WeComChannelResult(channel="webhook", ok=False, errcode=93000)

    async def _fake_app(*_args, **_kwargs) -> WeComChannelResult:
        return WeComChannelResult(channel="app_message", ok=True, errcode=0)

    monkeypatch.setattr(f"{NOTIFY_MODULE}.load_wecom_profile", lambda _pid: profile)
    monkeypatch.setattr(f"{NOTIFY_MODULE}.send_webhook", _fake_webhook)
    monkeypatch.setattr(f"{NOTIFY_MODULE}.send_app_message", _fake_app)
    monkeypatch.setattr(
        f"{NOTIFY_MODULE}.load_wecom_corp_config",
        lambda: WeComCorpConfig(corp_id="c", agent_id=1, agent_secret="s"),
    )

    result = await notify("school_consult", WeComMessage(title="T", fields={"k": "v"}))

    assert result.ok is True
    assert result.not_configured is False
    assert len(result.channels) == 2


@pytest.mark.asyncio
async def test_notify_failure_when_all_channels_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    """502 path when every enabled channel fails."""
    profile = WeComNotifyProfile(
        profile_id="school_consult",
        webhook_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=abc",
    )

    async def _fake_webhook(*_args, **_kwargs) -> WeComChannelResult:
        return WeComChannelResult(channel="webhook", ok=False, errcode=93000)

    monkeypatch.setattr(f"{NOTIFY_MODULE}.load_wecom_profile", lambda _pid: profile)
    monkeypatch.setattr(f"{NOTIFY_MODULE}.send_webhook", _fake_webhook)

    result = await notify("school_consult", WeComMessage(title="T", fields={"k": "v"}))

    assert result.ok is False
    assert result.not_configured is False
