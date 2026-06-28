"""Tests for unified MindMate + MindBot conversation listing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import main as _main_app

assert _main_app.app.title

from clients.dify_exceptions import DifyConversationNotFoundError
from clients.dify_http_errors import raise_for_dify_http_error
from services.dify.export.endpoints import ExportDifyEndpoint
from services.dify.export.transcript import ExportConversationSummary
from services.dify.unified_conversations import (
    list_unified_conversations,
    resolve_dify_user_for_conversation,
)
from tests.typing_helpers import as_user

_FAKE_ENDPOINT = ExportDifyEndpoint(
    organization_id=5,
    source="org_server",
    server=1,
    mindbot_config_id=None,
    api_key="test-key",
    api_url="https://dify.example/v1",
)


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


def _web_summary() -> ExportConversationSummary:
    return ExportConversationSummary(
        conversation_id="web-1",
        name="Web chat",
        server=1,
        organization_id=5,
        dify_user="mg_user_7",
        user_id=7,
        user_label="Alice",
        channel="web",
        created_at=100,
        updated_at=200,
    )


def _mindbot_summary() -> ExportConversationSummary:
    return ExportConversationSummary(
        conversation_id="bot-1",
        name="DingTalk chat",
        server=1,
        organization_id=5,
        dify_user="mindbot_5_staff42",
        user_id=7,
        user_label="Alice · DingTalk",
        channel="mindbot",
        created_at=150,
        updated_at=300,
    )


@pytest.mark.asyncio
async def test_list_unified_conversations_merges_web_and_mindbot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bound users see DingTalk MindBot threads alongside web MindMate history."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")
    web_target, mindbot_target = _web_and_mindbot_targets()

    async def _fake_targets(_db, _user):
        return [web_target, mindbot_target]

    async def _fake_fetch_page(_db, target, _org_by_id, *, limit):
        del limit
        if target.channel == "web":
            return [_web_summary()]
        return [_mindbot_summary()]

    async def _fake_supplement(_db, _targets, summaries, **_kwargs):
        return summaries, []

    monkeypatch.setattr(
        "services.dify.unified_conversations.build_user_dify_targets",
        _fake_targets,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations._fetch_target_summaries_page",
        _fake_fetch_page,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations.supplement_mindbot_summaries_from_usage",
        _fake_supplement,
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

    async def _fake_resolve(_db, target, conversation_id, dify_user, **_kwargs):
        del _db, conversation_id, _kwargs
        if target.channel == "mindbot" and dify_user == "mindbot_5_staff42":
            return _FAKE_ENDPOINT
        return None

    monkeypatch.setattr(
        "services.dify.unified_conversations.build_user_dify_targets",
        _fake_targets,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations._resolve_endpoint_for_conversation",
        _fake_resolve,
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

    async def _fake_resolve(_db, target, conversation_id, dify_user, **_kwargs):
        del _db, conversation_id
        if target.channel == "mindbot" and dify_user == "mindbot_5_staff42":
            return _FAKE_ENDPOINT
        return None

    monkeypatch.setattr(
        "services.dify.unified_conversations.build_user_dify_targets",
        _fake_targets,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations._resolve_endpoint_for_conversation",
        _fake_resolve,
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

    async def _fake_resolve(_db, target, conversation_id, dify_user, **_kwargs):
        del _db, conversation_id, _kwargs
        probe_calls["count"] += 1
        if target.channel == "mindbot" and dify_user == "mindbot_5_staff42":
            return _FAKE_ENDPOINT
        return None

    monkeypatch.setattr(
        "services.dify.unified_conversations.build_user_dify_targets",
        _fake_targets,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations._resolve_endpoint_for_conversation",
        _fake_resolve,
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

    async def _fake_resolve(_db, target, conversation_id, dify_user, **_kwargs):
        del _db, conversation_id
        if target.channel == "mindbot" and dify_user == "mindbot_5_staff42":
            return _FAKE_ENDPOINT
        return None

    monkeypatch.setattr(
        "services.dify.unified_conversations.build_user_dify_targets",
        _fake_targets,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations._resolve_endpoint_for_conversation",
        _fake_resolve,
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

    async def _fake_resolve(_db, target, conversation_id, dify_user, **_kwargs):
        del _db, target, conversation_id, dify_user, _kwargs
        return None

    monkeypatch.setattr(
        "services.dify.unified_conversations.build_user_dify_targets",
        _fake_targets,
    )
    monkeypatch.setattr(
        "services.dify.unified_conversations._resolve_endpoint_for_conversation",
        _fake_resolve,
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
