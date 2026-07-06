"""Unit tests for WeCom app message client (docs 91039 + 90236)."""

from __future__ import annotations

import pytest

from services.integrations.wecom.app_message_client import (
    clear_access_token_cache,
    format_touser,
    send_app_message,
)
from services.integrations.wecom.config import WeComCorpConfig
from services.integrations.wecom.profiles import WeComNotifyProfile
from services.integrations.wecom.types import WeComMessage
from services.integrations.wecom import app_message_client


@pytest.fixture(autouse=True)
def _clear_token_cache() -> None:
    clear_access_token_cache()


def test_format_touser_joins_with_pipe() -> None:
    """touser uses pipe separator per 90236."""
    assert format_touser(("UserA", "UserB")) == "UserA|UserB"


@pytest.mark.asyncio
async def test_send_app_message_uses_int_agentid(monkeypatch: pytest.MonkeyPatch) -> None:
    """agentid must be serialized as integer."""
    captured: dict[str, object] = {}

    async def _fake_gettoken(_corp: WeComCorpConfig) -> str:
        return "token-abc"

    async def _fake_post(_url: str, payload: dict[str, object]) -> dict[str, object]:
        captured["payload"] = payload
        return {"errcode": 0, "errmsg": "ok"}

    monkeypatch.setattr(app_message_client, "get_access_token", _fake_gettoken)
    monkeypatch.setattr(app_message_client, "_post_json", _fake_post)

    profile = WeComNotifyProfile(profile_id="school_consult", notify_userids=("u1", "u2"))
    corp = WeComCorpConfig(corp_id="corp", agent_id=1000002, agent_secret="secret")
    message = WeComMessage(title="学校版咨询预约", fields={"姓名": "李四"})

    result = await send_app_message(profile, message, corp)

    assert result.ok is True
    payload_obj = captured["payload"]
    assert isinstance(payload_obj, dict)
    assert payload_obj["touser"] == "u1|u2"
    assert payload_obj["msgtype"] == "text"
    assert payload_obj["agentid"] == 1000002
    assert isinstance(payload_obj["agentid"], int)
    text_obj = payload_obj["text"]
    assert isinstance(text_obj, dict)
    assert text_obj["content"]


@pytest.mark.asyncio
async def test_send_app_message_all_invalid_recipients(monkeypatch: pytest.MonkeyPatch) -> None:
    """errcode 81013 when all recipients are invalid."""

    async def _fake_gettoken(_corp: WeComCorpConfig) -> str:
        return "token-abc"

    async def _fake_post(_url: str, _payload: dict[str, object]) -> dict[str, object]:
        return {"errcode": 81013, "errmsg": "user invalid", "invaliduser": "ghost"}

    monkeypatch.setattr(app_message_client, "get_access_token", _fake_gettoken)
    monkeypatch.setattr(app_message_client, "_post_json", _fake_post)

    profile = WeComNotifyProfile(profile_id="school_consult", notify_userids=("ghost",))
    corp = WeComCorpConfig(corp_id="corp", agent_id=1, agent_secret="secret")
    message = WeComMessage(title="Title", fields={"字段": "值"})

    result = await send_app_message(profile, message, corp)

    assert result.ok is False
    assert result.errcode == 81013


@pytest.mark.asyncio
async def test_gettoken_caches_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Second gettoken call reuses cached token within expiry."""
    calls = {"count": 0}

    async def _fake_get_json(_url: str, _params: dict[str, str]) -> dict[str, object]:
        calls["count"] += 1
        return {"errcode": 0, "errmsg": "ok", "access_token": "cached-token", "expires_in": 7200}

    monkeypatch.setattr(app_message_client, "_get_json", _fake_get_json)

    corp = WeComCorpConfig(corp_id="corp", agent_id=1, agent_secret="secret")
    first = await app_message_client.get_access_token(corp)
    second = await app_message_client.get_access_token(corp)

    assert first == "cached-token"
    assert second == "cached-token"
    assert calls["count"] == 1
