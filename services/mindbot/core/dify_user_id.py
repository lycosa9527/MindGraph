"""Dify ``user`` id and Redis scope for MindBot (per staff; group chats isolated per user)."""

from __future__ import annotations

from typing import Any

from services.mindbot.education.metrics import dingtalk_chat_scope


def mindbot_is_group_dingtalk_chat(body: dict[str, Any], chat_type: str) -> bool:
    """True when the conversation is a DingTalk group (not 1:1)."""
    return chat_type == "group" or dingtalk_chat_scope(body) == "group"


def mindbot_dify_user_id_for_chat(organization_id: int, sender_staff_id: str) -> str:
    """
    Return the Dify API ``user`` string for this callback.

    One Dify user per DingTalk staff member; group and 1:1 use the same pattern so
    ``conversation_id`` is always valid for that Redis binding and ``user`` pair.
    """
    staff = (sender_staff_id or "").strip() or "unknown"
    return f"mindbot_{organization_id}_{staff}"


def mindbot_dify_conv_redis_suffix(
    organization_id: int,
    conversation_id_dt: str,
    sender_staff_id: str,
    body: dict[str, Any],
    chat_type: str,
) -> str:
    """
    Return the suffix after ``mindbot:dify_conv:`` for Redis.

    In group chats, include ``sender_staff_id`` so each member has their own Dify
    conversation binding; 1:1 uses only org + open conversation id.
    """
    cid = conversation_id_dt.strip()
    staff = (sender_staff_id or "").strip()
    if mindbot_is_group_dingtalk_chat(body, chat_type) and cid and staff:
        return f"{organization_id}:{cid}:{staff}"
    return f"{organization_id}:{cid}"


def mindbot_conv_gate_scope_id(
    conversation_id_dt: str,
    sender_staff_id: str,
    body: dict[str, Any],
    chat_type: str,
) -> str:
    """
    Return the conversation id string used for the single-flight conv gate key.

    Must match the Redis ``conv_key`` scope: group chats include staff so
    parallel members do not share one gate.
    """
    cid = conversation_id_dt.strip()
    staff = (sender_staff_id or "").strip()
    if mindbot_is_group_dingtalk_chat(body, chat_type) and cid and staff:
        return f"{cid}:{staff}"
    return cid
