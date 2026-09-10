"""Tests for Redis persist of armed Kitty clarify options."""

from __future__ import annotations

from typing import Any, Dict, Optional
from unittest.mock import patch

import pytest

from services.kitty.infra.redis.kitty_redis_keys import (
    kitty_pending_clarify_key,
    kitty_pending_intent_slot_key,
)
from services.kitty.routing.pending_clarify_store import (
    delete_pending_clarify_payload,
    load_pending_clarify_payload,
    load_pending_intent_slot_payload,
    migrate_pending_kitty_keys,
    persist_pending_clarify_payload,
    persist_pending_intent_slot_payload,
    sanitize_pending_clarify,
    sanitize_pending_intent_slot,
)


def test_pending_keys_are_scope_hash_tagged() -> None:
    """Cluster slot stays with the diagram scope, matching other Kitty Redis keys."""
    assert kitty_pending_clarify_key(7, "diagram-abc") == "{diagram-abc}kitty:pending_clarify:7"
    assert kitty_pending_intent_slot_key(7, "diagram-abc") == "{diagram-abc}kitty:pending_intent_slot:7"


class _FakeRedis:
    """In-memory stand-in for the async Redis client."""

    def __init__(self) -> None:
        self.values: Dict[str, str] = {}

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        """Store ``value`` under ``key``; TTL is unused in the mock."""
        _ = ex
        self.values[key] = value

    async def get(self, key: str) -> Optional[str]:
        """Return the stored string, or None."""
        return self.values.get(key)

    async def delete(self, key: str) -> None:
        """Remove ``key`` if present."""
        self.values.pop(key, None)


def test_sanitize_pending_clarify_keeps_followup_slots() -> None:
    """Ask-followup option commands keep slot_action after a reconnect restore."""
    raw: Dict[str, Any] = {
        "question": "想怎么改这张图？",
        "options": ["改主题", "添加分支"],
        "option_commands": [
            {"action": "ask_followup", "slot_action": "update_center", "followup": "主题想改成什么？"},
            {"action": "add_node", "target": "品牌", "side": "right"},
        ],
        "seed_target": "品牌",
    }
    cleaned = sanitize_pending_clarify(raw)
    assert cleaned is not None
    assert cleaned["options"] == ["改主题", "添加分支"]
    first = cleaned["option_commands"][0]
    assert first["action"] == "ask_followup"
    assert first["slot_action"] == "update_center"
    assert first["followup"] == "主题想改成什么？"
    assert cleaned["option_commands"][1]["target"] == "品牌"
    assert cleaned["seed_target"] == "品牌"


def test_sanitize_pending_clarify_rejects_one_command() -> None:
    """A single option is not a choice menu."""
    assert sanitize_pending_clarify({"option_commands": [{"action": "add_node", "target": "A"}]}) is None


def test_sanitize_pending_clarify_drops_unknown_actions() -> None:
    """Restored option commands cannot carry arbitrary router actions."""
    cleaned = sanitize_pending_clarify(
        {
            "options": ["打开面板", "添加分支"],
            "option_commands": [
                {"action": "open_thinkguide"},
                {"action": "add_node", "target": "品牌"},
            ],
        }
    )
    assert cleaned is None


def test_sanitize_pending_intent_slot_keeps_add() -> None:
    """Follow-up slots persist only value-slot edits."""
    slot = sanitize_pending_intent_slot(
        {"action": "add_node", "parent_ref": "n1", "side": "right", "followup": "要添加哪条分支？"}
    )
    assert slot == {
        "action": "add_node",
        "parent_ref": "n1",
        "side": "right",
        "followup": "要添加哪条分支？",
    }
    assert sanitize_pending_intent_slot({"action": "open_thinkguide"}) is None


@pytest.mark.asyncio
async def test_persist_load_delete_pending_clarify_roundtrip() -> None:
    """Armed options survive a process-local Redis mock round-trip."""
    fake = _FakeRedis()
    session = {"user_id": "7", "diagram_session_id": "diagram-abc"}
    pending = {
        "question": "想怎么改这张图？",
        "options": ["改主题", "添加分支"],
        "option_commands": [
            {"action": "ask_followup", "slot_action": "update_center"},
            {"action": "add_node", "target": "品牌"},
        ],
    }
    with patch(
        "services.kitty.routing.pending_clarify_store.get_async_redis",
        return_value=fake,
    ):
        await persist_pending_clarify_payload(session, pending)
        loaded = await load_pending_clarify_payload(session)
        assert loaded is not None
        assert loaded["options"] == ["改主题", "添加分支"]
        assert loaded["option_commands"][1]["target"] == "品牌"
        await delete_pending_clarify_payload(session)
        assert await load_pending_clarify_payload(session) is None


@pytest.mark.asyncio
async def test_persist_intent_slot_and_migrate_scope() -> None:
    """Follow-up slots survive persist and move with a diagram scope remap."""
    fake = _FakeRedis()
    session = {"user_id": "7", "diagram_session_id": "ephemeral-1"}
    slot = {"action": "add_node", "followup": "要添加哪条分支？"}
    with patch(
        "services.kitty.routing.pending_clarify_store.get_async_redis",
        return_value=fake,
    ):
        await persist_pending_intent_slot_payload(session, slot)
        loaded = await load_pending_intent_slot_payload(session)
        assert loaded is not None
        assert loaded["action"] == "add_node"
        await migrate_pending_kitty_keys(7, "ephemeral-1", "diagram-library")
        session["diagram_session_id"] = "diagram-library"
        moved = await load_pending_intent_slot_payload(session)
        assert moved is not None
        assert moved["action"] == "add_node"
        session["diagram_session_id"] = "ephemeral-1"
        assert await load_pending_intent_slot_payload(session) is None
