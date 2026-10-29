"""Dify user and conversation ids for one seminar room.

The user id starts with ``MINDMATE_DIFY_USER_PREFIX`` so two MindGraph
installs that share a Dify app do not mix rooms. The stored conversation id
starts with ``s{server}:`` so 主服务器 and 备用服务器 stay distinct after Redis
is rebuilt from Postgres.
"""

from __future__ import annotations

from typing import Optional

from utils.dify_mindmate_user_id import mindmate_dify_user_prefix


def mindmate_seminar_dify_user_id(org_id: Optional[int], session_id: str) -> str:
    """Stable Dify ``user`` for this room on this MindGraph install."""
    org_part = str(org_id) if org_id is not None else "0"
    prefix = mindmate_dify_user_prefix()
    return f"{prefix}_mindmate_seminar_{org_part}_{session_id}"


def read_seminar_dify_conversation(stored: Optional[str]) -> tuple[str, Optional[int]]:
    """Split a stored id into the Dify conversation id and its server number."""
    text = (stored or "").strip()
    if len(text) < 4 or text[0] != "s" or not text[1].isdigit():
        return text, None
    marker, sep, raw = text.partition(":")
    if sep != ":" or not raw or not marker[1:].isdigit():
        return text, None
    server = int(marker[1:])
    if server < 1:
        return text, None
    return raw, server


def seminar_dify_conversation_ref(conversation_id: str, server: Optional[int]) -> str:
    """Store ``s{server}:{id}`` when the owning Dify server is known."""
    raw, existing = read_seminar_dify_conversation(conversation_id)
    body = raw or conversation_id.strip()
    if isinstance(server, int) and server >= 1:
        chosen: Optional[int] = server
    else:
        chosen = existing
    if chosen is None or not body:
        return body
    return f"s{chosen}:{body}"
