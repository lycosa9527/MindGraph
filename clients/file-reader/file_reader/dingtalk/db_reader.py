"""Read DingTalk sessions and messages from a decrypted local database."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from file_reader.chat.messages import MAX_EXPORT_MESSAGES, ChatMessage
from file_reader.dingtalk.db_cache import DingTalkDbCache
from file_reader.dingtalk.local import account_from_status, detect_dingtalk_local

_MSG_TYPE_TEXT = 1
_MSG_TYPE_IMAGE = 2
_MSG_TYPE_VOICE = 300
_MSG_TYPE_FILE = 501
_MSG_TYPE_RICH_TEXT = 1200
_MSG_TYPE_QUOTE = 3100
# System / platform noise — join invites, tips, DING-adjacent cards (not user chat).
_SKIP_CONTENT_TYPES = frozenset({102, 104, 1202})


class DingTalkDbError(RuntimeError):
    """Failed to read decrypted DingTalk databases."""


@dataclass(frozen=True)
class DingTalkSessionPreview:
    """Conversation row from ``tbconversation``."""

    cid: str
    display_name: str
    last_timestamp: int
    is_group: bool


def format_session_time(timestamp_ms: int) -> str:
    """Format a millisecond epoch timestamp for list rows."""
    if timestamp_ms <= 0:
        return ""
    try:
        return datetime.fromtimestamp(timestamp_ms / 1000.0).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return ""


def format_chat_preview(messages: List[ChatMessage], *, limit: int = 40) -> str:
    """Build a short multi-line preview from recent messages."""
    lines: List[str] = []
    for msg in messages[-limit:]:
        stamp = f"[{msg.timestamp}] " if msg.timestamp else ""
        lines.append(f"{stamp}{msg.sender}: {msg.text}")
    return "\n".join(lines)


class DingTalkDbReader:
    """Query decrypted DingTalk SQLite for sessions and messages."""

    def __init__(self, cache: DingTalkDbCache) -> None:
        self._cache = cache

    @classmethod
    def from_local_detection(cls) -> "DingTalkDbReader":
        """Build a reader from the best local DingTalk account."""
        status = detect_dingtalk_local()
        account = account_from_status(status)
        if account is None:
            raise DingTalkDbError("No DingTalk account database found on this PC")
        return cls(DingTalkDbCache(account))

    def list_sessions(self) -> List[DingTalkSessionPreview]:
        """Return active conversations sorted by recency."""
        db_path = self._cache.ensure_plain_db()
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT cid, type, title, lastModify
                FROM tbconversation
                WHERE status = 1
                ORDER BY top DESC, lastModify DESC
                """
            ).fetchall()
            profiles = _load_profile_map(conn)
            sessions: List[DingTalkSessionPreview] = []
            for row in rows:
                cid = str(row["cid"] or "")
                conv_type = int(row["type"] or 0)
                title = str(row["title"] or "").strip()
                if conv_type == 1 and ":" in cid:
                    title = _single_chat_title(cid, profiles, title)
                sessions.append(
                    DingTalkSessionPreview(
                        cid=cid,
                        display_name=title or cid,
                        last_timestamp=int(row["lastModify"] or 0),
                        is_group=conv_type != 1,
                    )
                )
            return sessions

    def load_messages(self, cid: str, max_messages: int = MAX_EXPORT_MESSAGES) -> List[ChatMessage]:
        """Load text-capable messages for one conversation."""
        db_path = self._cache.ensure_plain_db()
        with closing(sqlite3.connect(str(db_path))) as conn:
            conn.row_factory = sqlite3.Row
            table = _find_msg_table(conn, cid)
            if table is None:
                return []
            profiles = _load_profile_map(conn)
            rows = conn.execute(
                f"""
                SELECT senderId, contentType, content, createdAt, recallStatus
                FROM "{table}"
                WHERE cid = ? AND recallStatus = 0
                ORDER BY createdAt ASC
                LIMIT ?
                """,
                (cid, max_messages),
            ).fetchall()
            messages: List[ChatMessage] = []
            for row in rows:
                text = _message_text(int(row["contentType"] or 0), row["content"])
                if not text:
                    continue
                sender_id = int(row["senderId"] or 0)
                sender = profiles.get(sender_id, str(sender_id))
                messages.append(
                    ChatMessage(
                        sender=sender,
                        text=text,
                        timestamp=format_session_time(int(row["createdAt"] or 0)),
                    )
                )
            return messages


def _load_profile_map(conn: sqlite3.Connection) -> dict[int, str]:
    mapping: dict[int, str] = {}
    try:
        rows = conn.execute("SELECT uid, nick, realName FROM tbuser_profile_v2").fetchall()
    except sqlite3.Error:
        return mapping
    for row in rows:
        uid = int(row["uid"])
        nick = str(row["nick"] or "").strip()
        real_name = str(row["realName"] or "").strip()
        mapping[uid] = real_name or nick or str(uid)
    return mapping


def _single_chat_title(
    cid: str,
    profiles: dict[int, str],
    fallback: str,
) -> str:
    parts = cid.split(":", 1)
    if len(parts) != 2:
        return fallback
    for token in parts:
        if token.isdigit():
            uid = int(token)
            name = profiles.get(uid)
            if name:
                return name
    return fallback


def _find_msg_table(conn: sqlite3.Connection, cid: str) -> Optional[str]:
    for index in range(128):
        table = f"tbmsg_{index:03d}"
        try:
            row = conn.execute(
                f'SELECT 1 FROM "{table}" WHERE cid = ? LIMIT 1',
                (cid,),
            ).fetchone()
        except sqlite3.OperationalError:
            continue
        if row:
            return table
    return None


def _message_text(content_type: int, content_raw: object) -> str:
    if content_type in _SKIP_CONTENT_TYPES:
        return ""
    content_data = _parse_content_json(content_raw)
    if content_type == _MSG_TYPE_TEXT:
        return str(content_data.get("text") or "").strip()
    if content_type == _MSG_TYPE_IMAGE:
        return "[图片]"
    if content_type == _MSG_TYPE_VOICE:
        return "[语音]"
    if content_type == _MSG_TYPE_FILE:
        return "[文件]"
    if content_type in (_MSG_TYPE_RICH_TEXT, 1201):
        return _extract_rich_text(content_data)
    if content_type == _MSG_TYPE_QUOTE:
        return _extract_quote_text(content_data)
    if content_type in (2900, 2950):
        return str(content_data.get("title") or content_data.get("text") or "[卡片]").strip()
    return str(content_data.get("text") or "").strip()


def _parse_content_json(content_raw: object) -> dict:
    if content_raw is None:
        return {}
    if isinstance(content_raw, bytes):
        text = content_raw.decode("utf-8", errors="replace")
    else:
        text = str(content_raw)
    if not text.strip():
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}
    return parsed if isinstance(parsed, dict) else {"text": text}


def _extract_rich_text(content_data: dict) -> str:
    parts = content_data.get("items") or content_data.get("contents") or []
    if not isinstance(parts, list):
        return str(content_data.get("text") or "").strip()
    texts: List[str] = []
    for item in parts:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("content") or "").strip()
        if text:
            texts.append(text)
    if texts:
        return "\n".join(texts)
    return str(content_data.get("text") or "").strip()


def _extract_quote_text(content_data: dict) -> str:
    quote = content_data.get("quoteContent") or content_data.get("quote") or {}
    body = ""
    if isinstance(quote, dict):
        body = str(quote.get("text") or quote.get("content") or "").strip()
    main = str(content_data.get("text") or "").strip()
    if body and main:
        return f"{main}\n> {body}"
    return main or body
