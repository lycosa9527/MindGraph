"""Tests for unified MindMate + MindBot conversation listing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import main as _main_app

assert _main_app.app.title

from services.dify.unified_conversations import list_unified_conversations
from tests.typing_helpers import as_user


@pytest.mark.asyncio
async def test_list_unified_conversations_merges_web_and_mindbot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bound users see DingTalk MindBot threads alongside web MindMate history."""
    user = SimpleNamespace(id=7, organization_id=5, name="Alice", phone="", email="")

    web_target = SimpleNamespace(
        organization_id=5,
        user_id=7,
        dify_user="mg_user_7",
        label="Alice",
        channel="web",
    )
    mindbot_target = SimpleNamespace(
        organization_id=5,
        user_id=7,
        dify_user="mindbot_5_staff42",
        label="Alice · DingTalk",
        channel="mindbot",
    )

    async def _fake_targets(_db, _user):
        return [web_target, mindbot_target]

    class _FakeClient:
        def __init__(self, dify_user: str) -> None:
            self.dify_user = dify_user

        async def get_conversations(self, user_id: str, **kwargs):
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
