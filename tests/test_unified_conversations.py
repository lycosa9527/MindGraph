"""Tests for unified MindMate + MindBot conversation listing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import main as _main_app

assert _main_app.app.title

from clients.dify_exceptions import DifyConversationNotFoundError
from clients.dify_http_errors import raise_for_dify_http_error
from services.dify.unified_conversations import (
    list_unified_conversations,
    resolve_dify_user_for_conversation,
)
from tests.typing_helpers import as_user


def _web_and_mindbot_targets(user_id: int = 7, org_id: int = 5):
    web_target = SimpleNamespace(
        organization_id=org_id,
        user_id=user_id,
        dify_user=f"mg_user_{user_id}",
        label="Alice",
        channel="web",
    )
    mindbot_target = SimpleNamespace(
        organization_id=org_id,
        user_id=user_id,
        dify_user=f"mindbot_{org_id}_staff42",
        label="Alice · DingTalk",
        channel="mindbot",
    )
    return web_target, mindbot_target


@pytest.mark.asyncio
async def test_list_unified_conversations_merges_web_and_mindbot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bound users see DingTalk MindBot threads alongside web MindMate history."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")

    web_target, mindbot_target = _web_and_mindbot_targets()

    async def _fake_targets(_db, _user):
        return [web_target, mindbot_target]

    class _FakeClient:
        def __init__(self, dify_user: str) -> None:
            self.dify_user = dify_user

        async def get_conversations(self, user_id: str, **kwargs):
            """Return canned conversation pages keyed by dify user id."""
            del kwargs
            assert user_id == self.dify_user
            if user_id == "mg_user_7":
                return {
                    "data": [
                        {
                            "id": "web-1",
                            "name": "Web chat",
                            "created_at": 100,
                            "updated_at": 200,
                        }
                    ],
                    "has_more": False,
                }
            return {
                "data": [
                    {
                        "id": "bot-1",
                        "name": "DingTalk chat",
                        "created_at": 150,
                        "updated_at": 300,
                    }
                ],
                "has_more": False,
            }

    async def _fake_client_for_target(_db, target):
        return _FakeClient(target.dify_user)

    monkeypatch.setattr(
        "services.dify.unified_conversations.build_user_dify_targets",
        _fake_targets,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations.client_for_target",
        _fake_client_for_target,
    )

    rows, has_more = await list_unified_conversations(MagicMock(), as_user(user), limit=10)

    assert has_more is False
    assert [row.id for row in rows] == ["bot-1", "web-1"]
    assert rows[0].channel == "mindbot"
    assert rows[0].dify_user == "mindbot_5_staff42"
    assert rows[1].channel == "web"
    assert rows[1].dify_user == "mg_user_7"


@pytest.mark.asyncio
async def test_resolve_dify_user_probes_mindbot_when_web_has_no_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a hint, resolve probes identities instead of defaulting to web."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")
    web_target, mindbot_target = _web_and_mindbot_targets()

    async def _fake_targets(_db, _user):
        return [web_target, mindbot_target]

    class _FakeClient:
        async def get_messages(self, conversation_id: str, user_id: str, **kwargs):
            """Simulate Dify message lookup for identity probing."""
            del kwargs
            assert conversation_id == "dingtalk-conv"
            if user_id == "mg_user_7":
                raise DifyConversationNotFoundError("Conversation Not Exists")
            if user_id == "mindbot_5_staff42":
                return {"data": [{"id": "msg-1"}]}
            return {"data": []}

    async def _fake_client_for_target(_db, target):
        del target
        return _FakeClient()

    monkeypatch.setattr(
        "services.dify.unified_conversations.build_user_dify_targets",
        _fake_targets,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations.client_for_target",
        _fake_client_for_target,
    )

    dify_user = await resolve_dify_user_for_conversation(
        MagicMock(),
        as_user(user),
        "dingtalk-conv",
    )

    assert dify_user == "mindbot_5_staff42"


@pytest.mark.asyncio
async def test_resolve_dify_user_verifies_hint_before_trusting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A matching hint is returned only after Dify confirms ownership."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")
    web_target, mindbot_target = _web_and_mindbot_targets()

    async def _fake_targets(_db, _user):
        return [web_target, mindbot_target]

    class _FakeClient:
        async def get_messages(self, conversation_id: str, user_id: str, **kwargs):
            """Simulate Dify message lookup for identity probing."""
            del kwargs
            assert conversation_id == "bot-conv"
            if user_id == "mg_user_7":
                raise DifyConversationNotFoundError("Conversation Not Exists")
            if user_id == "mindbot_5_staff42":
                return {"data": [{"id": "msg-1"}]}
            return {"data": []}

    async def _fake_client_for_target(_db, target):
        del target
        return _FakeClient()

    monkeypatch.setattr(
        "services.dify.unified_conversations.build_user_dify_targets",
        _fake_targets,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations.client_for_target",
        _fake_client_for_target,
    )

    dify_user = await resolve_dify_user_for_conversation(
        MagicMock(),
        as_user(user),
        "bot-conv",
        dify_user_hint="mg_user_7",
    )

    assert dify_user == "mindbot_5_staff42"


@pytest.mark.asyncio
async def test_resolve_dify_user_uses_hint_when_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A verified hint avoids probing other identities."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")
    web_target, mindbot_target = _web_and_mindbot_targets()
    probe_calls = {"count": 0}

    async def _fake_targets(_db, _user):
        return [web_target, mindbot_target]

    class _FakeClient:
        async def get_messages(self, conversation_id: str, user_id: str, **kwargs):
            """Simulate Dify message lookup for identity probing."""
            del kwargs, conversation_id
            probe_calls["count"] += 1
            if user_id == "mindbot_5_staff42":
                return {"data": [{"id": "msg-1"}]}
            raise DifyConversationNotFoundError("Conversation Not Exists")

    async def _fake_client_for_target(_db, target):
        del target
        return _FakeClient()

    monkeypatch.setattr(
        "services.dify.unified_conversations.build_user_dify_targets",
        _fake_targets,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations.client_for_target",
        _fake_client_for_target,
    )

    dify_user = await resolve_dify_user_for_conversation(
        MagicMock(),
        as_user(user),
        "bot-conv",
        dify_user_hint="mindbot_5_staff42",
    )

    assert dify_user == "mindbot_5_staff42"
    assert probe_calls["count"] == 1


@pytest.mark.asyncio
async def test_resolve_dify_user_ignores_unknown_hint_and_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale client hints that do not match bound targets fall back to probing."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")
    web_target, mindbot_target = _web_and_mindbot_targets()

    async def _fake_targets(_db, _user):
        return [web_target, mindbot_target]

    class _FakeClient:
        async def get_messages(self, conversation_id: str, user_id: str, **kwargs):
            """Simulate Dify message lookup for identity probing."""
            del kwargs
            assert conversation_id == "dingtalk-conv"
            if user_id == "mg_user_7":
                raise DifyConversationNotFoundError("Conversation Not Exists")
            if user_id == "mindbot_5_staff42":
                return {"data": [{"id": "msg-1"}]}
            return {"data": []}

    async def _fake_client_for_target(_db, target):
        del target
        return _FakeClient()

    monkeypatch.setattr(
        "services.dify.unified_conversations.build_user_dify_targets",
        _fake_targets,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations.client_for_target",
        _fake_client_for_target,
    )

    dify_user = await resolve_dify_user_for_conversation(
        MagicMock(),
        as_user(user),
        "dingtalk-conv",
        dify_user_hint="mg_user_999",
    )

    assert dify_user == "mindbot_5_staff42"


@pytest.mark.asyncio
async def test_resolve_dify_user_raises_when_no_identity_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stale conversation ids surface a typed not-found error."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")
    web_target, mindbot_target = _web_and_mindbot_targets()

    async def _fake_targets(_db, _user):
        return [web_target, mindbot_target]

    class _FakeClient:
        async def get_messages(self, conversation_id: str, user_id: str, **kwargs):
            """Simulate Dify message lookup for identity probing."""
            del conversation_id, user_id, kwargs
            raise DifyConversationNotFoundError("Conversation Not Exists")

    async def _fake_client_for_target(_db, target):
        del target
        return _FakeClient()

    monkeypatch.setattr(
        "services.dify.unified_conversations.build_user_dify_targets",
        _fake_targets,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations.client_for_target",
        _fake_client_for_target,
    )

    with pytest.raises(DifyConversationNotFoundError):
        await resolve_dify_user_for_conversation(
            MagicMock(),
            as_user(user),
            "missing-conv",
        )


def test_raise_for_dify_http_error_maps_conversation_not_exists_message() -> None:
    """Dify sometimes returns conversation-not-found without a structured code."""
    with pytest.raises(DifyConversationNotFoundError):
        raise_for_dify_http_error(
            400,
            "Conversation Not Exists. You have requested this URI [/v1/messages]",
            None,
            "/messages",
        )
