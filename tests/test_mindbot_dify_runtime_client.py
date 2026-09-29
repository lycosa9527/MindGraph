"""MindBot Dify client and Start variables match web MindMate."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from clients.dify import AsyncDifyClient
from models.domain.mindbot_config import OrganizationMindbotConfig
from services.dify.org_mindmate_client import MindmateDifyNotConfiguredError
from services.mindbot.dify.runtime_client import mindbot_dify_chat_inputs, open_mindbot_dify_client
from tests.typing_helpers import as_type

_AVATAR = "/static/org_mindmate_avatars/2/avatar.png"


def _cfg(**overrides: object) -> OrganizationMindbotConfig:
    """MindBot config stand-in."""
    base: dict[str, object] = {
        "id": 11,
        "organization_id": 5,
        "use_org_dify_settings": True,
        "dify_api_base_url": "https://stored.example/v1",
        "dify_api_key": "stored-key",
        "dify_timeout_seconds": 300,
        "dify_inputs_json": None,
    }
    base.update(overrides)
    return as_type(SimpleNamespace(**base), OrganizationMindbotConfig)


class _Session:
    """Stand-in for system_rls_session."""

    def __init__(self, db: object) -> None:
        self._db = db

    async def __aenter__(self) -> object:
        return self._db

    async def __aexit__(self, *_exc: object) -> None:
        return None


@pytest.mark.asyncio
async def test_org_linked_bot_uses_web_mindmate_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """School-default bots call the same live resolver as web MindMate."""
    live = AsyncDifyClient(api_key="live-key", api_url="https://live.example/v1", timeout=90)
    db_sentinel = object()
    seen: dict[str, object] = {}

    async def _resolve(db: object, org_id: int) -> AsyncDifyClient:
        seen["db"] = db
        seen["org_id"] = org_id
        return live

    monkeypatch.setattr(
        "services.mindbot.dify.runtime_client.system_rls_session",
        lambda: _Session(db_sentinel),
    )
    monkeypatch.setattr(
        "services.mindbot.dify.runtime_client.resolve_mindmate_dify_client",
        _resolve,
    )
    client = await open_mindbot_dify_client(_cfg(use_org_dify_settings=True))
    assert client is live
    assert seen["db"] is db_sentinel
    assert seen["org_id"] == 5


@pytest.mark.asyncio
async def test_org_linked_bot_surfaces_missing_mindmate_dify(monkeypatch: pytest.MonkeyPatch) -> None:
    """A school with no MindMate Dify credentials fails the same way as web chat."""

    async def _resolve(_db: object, _org_id: int) -> AsyncDifyClient:
        raise MindmateDifyNotConfiguredError()

    monkeypatch.setattr(
        "services.mindbot.dify.runtime_client.system_rls_session",
        lambda: _Session(object()),
    )
    monkeypatch.setattr(
        "services.mindbot.dify.runtime_client.resolve_mindmate_dify_client",
        _resolve,
    )
    with pytest.raises(MindmateDifyNotConfiguredError):
        await open_mindbot_dify_client(_cfg(use_org_dify_settings=True))


@pytest.mark.asyncio
async def test_custom_bot_keeps_stored_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """A custom Dify app is not replaced by the school MindMate client."""

    def _forbid_session() -> None:
        raise AssertionError("custom bots must not open the MindMate resolver")

    monkeypatch.setattr(
        "services.mindbot.dify.runtime_client.system_rls_session",
        _forbid_session,
    )
    client = await open_mindbot_dify_client(
        _cfg(
            use_org_dify_settings=False,
            dify_api_key=" custom-key ",
            dify_api_base_url="https://custom.example/v1/",
            dify_timeout_seconds=42,
        )
    )
    assert client.api_key == "custom-key"
    assert client.api_url == "https://custom.example/v1"
    assert client.timeout == 42


@pytest.mark.asyncio
async def test_chat_inputs_send_three_start_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """MindBot overwrites persona keys the same way web chat does."""

    async def _load(_organization_id: int) -> SimpleNamespace:
        return SimpleNamespace(
            name="八一",
            display_name="北京市八一学校附属玉泉中学",
            mindmate_agent_name="八一思行者",
            mindmate_agent_alias="小思",
            mindmate_agent_avatar_url=_AVATAR,
            dify_api_base_url="https://dify.example/v1",
            dify_api_key="key",
        )

    monkeypatch.setattr("services.dify.org_dify_inputs._organization_for_persona", _load)
    inputs = await mindbot_dify_chat_inputs(
        _cfg(
            dify_inputs_json=(
                '{"grade":"7","mg_agent_name":"spoof","mg_agent_alias":"spoof",'
                '"mg_school_name":"spoof","mg_school_blurb":"nope"}'
            )
        ),
        dify_user_id="mindbot_5_staff",
        dify_conversation_id="conv-1",
    )
    assert inputs["grade"] == "7"
    assert inputs["mg_dify_user"] == "mindbot_5_staff"
    assert inputs["mg_conversation_id"] == "conv-1"
    assert inputs["mg_agent_name"] == "八一思行者"
    assert inputs["mg_agent_alias"] == "小思"
    assert inputs["mg_school_name"] == "北京市八一学校附属玉泉中学"
    assert "mg_school_blurb" not in inputs


@pytest.mark.asyncio
async def test_chat_inputs_ignore_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bad extra inputs do not block the three Start variables."""

    async def _load(_organization_id: int) -> None:
        return None

    monkeypatch.setattr("services.dify.org_dify_inputs._organization_for_persona", _load)
    inputs = await mindbot_dify_chat_inputs(
        _cfg(dify_inputs_json="[1, 2]"),
        dify_user_id="mindbot_5_staff",
        dify_conversation_id=None,
    )
    assert inputs["mg_agent_name"] == "MindMate"
    assert inputs["mg_agent_alias"] == "MindMate"
    assert inputs["mg_school_name"] == ""
    assert "mg_conversation_id" not in inputs
