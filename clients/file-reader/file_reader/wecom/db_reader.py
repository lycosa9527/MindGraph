"""Read WeCom sessions and messages from decrypted local databases."""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from file_reader.chat.messages import MAX_EXPORT_MESSAGES, ChatMessage
from file_reader.wecom.db_cache import WeComDbCache
from file_reader.wecom.debug_log import log_wecom
from file_reader.wecom.local import WeComLocalStatus, account_from_status, detect_wecom_local

_MESSAGE_TABLES = ("message_table", "message_small_table", "kf_message_tableV1")
_MSG_TYPE_TEXT = {0, 2}


class WeComDbError(RuntimeError):
    """Failed to read decrypted WeCom databases."""


@dataclass(frozen=True)
class WeComSessionPreview:
    """Conversation row for the UI."""

    conversation_id: str
    display_name: str
    last_timestamp: int
    is_group: bool


@dataclass(frozen=True)
class WeComUserDirectory:
    """Contact display fields from ``user.db`` (remark preferred like WeChat)."""

    remarks: Dict[int, str]
    display_names: Dict[int, str]

    def label_for_user(self, user_id: int) -> str:
        """Return remark-first display label for a user id."""
        if user_id in self.remarks:
            return self.remarks[user_id]
        return self.display_names.get(user_id, str(user_id))

    def sender_label(
        self,
        user_id: int,
        conversation_id: str,
        member_names: Dict[str, Dict[int, str]],
    ) -> str:
        """Prefer contact remark, then group nickname, then profile name."""
        if user_id in self.remarks:
            return self.remarks[user_id]
        nick = member_names.get(conversation_id, {}).get(user_id)
        if nick:
            return nick
        return self.display_names.get(user_id, str(user_id) if user_id else "系统")


def format_session_time(timestamp: int) -> str:
    """Format a second or millisecond epoch timestamp for list rows."""
    if timestamp <= 0:
        return ""
    value = timestamp
    if value > 20_000_000_000:
        value = value // 1000
    try:
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
    except (OSError, OverflowError, ValueError):
        return ""


def format_chat_preview(messages: List[ChatMessage], *, limit: int = 40) -> str:
    """Build a short multi-line preview from recent messages."""
    lines: List[str] = []
    for msg in messages[-limit:]:
        stamp = f"[{msg.timestamp}] " if msg.timestamp else ""
        lines.append(f"{stamp}{msg.sender}: {msg.text}")
    return "\n".join(lines)


class WeComDbReader:
    """Query decrypted WeCom SQLite for sessions and messages."""

    def __init__(self, cache: WeComDbCache, *, self_id: Optional[int] = None) -> None:
        self._cache = cache
        self._self_id = self_id

    @classmethod
    def from_local_detection(cls, keys: Dict[str, str]) -> "WeComDbReader":
        """Build a reader from the best local WeCom account and supplied keys."""
        status = detect_wecom_local()
        account = account_from_status(status)
        if account is None:
            raise WeComDbError("No WeCom account database found on this PC")
        return cls(WeComDbCache(account, keys), self_id=status.user_id)

    def list_sessions(self) -> List[WeComSessionPreview]:
        """Return active conversations sorted by recency."""
        cache_root = self._cache.ensure_chat_dbs()
        session_db = _find_session_db(cache_root)
        if session_db is None:
            raise WeComDbError("session database not found after decrypt")
        user_dir = _load_user_directory(cache_root)
        counts, last_times = _load_message_counts(cache_root)
        conversations: Dict[str, WeComSessionPreview] = {}
        has_conversation_table = False
        with closing(sqlite3.connect(str(session_db))) as conn:
            conn.row_factory = sqlite3.Row
            if _table_exists(conn, "conversation_table"):
                has_conversation_table = True
                for row in conn.execute(
                    """
                    SELECT id, name, roomname_remark, last_message_time
                    FROM conversation_table
                    """
                ):
                    conversation_id = str(row["id"] or "")
                    if not conversation_id:
                        continue
                    display = _conversation_display_name(
                        conversation_id,
                        str(row["name"] or ""),
                        str(row["roomname_remark"] or ""),
                        user_dir,
                        self._self_id,
                    )
                    last_time = max(
                        int(row["last_message_time"] or 0),
                        last_times.get(conversation_id, 0),
                    )
                    conversations[conversation_id] = WeComSessionPreview(
                        conversation_id=conversation_id,
                        display_name=display,
                        last_timestamp=last_time,
                        is_group=conversation_id.startswith("R:"),
                    )
        for conversation_id, count in counts.items():
            if conversation_id in conversations:
                continue
            if count <= 0:
                continue
            conversations[conversation_id] = WeComSessionPreview(
                conversation_id=conversation_id,
                display_name=_name_from_conversation_id(conversation_id, user_dir, self._self_id),
                last_timestamp=last_times.get(conversation_id, 0),
                is_group=conversation_id.startswith("R:"),
            )
        result = [
            item
            for item in conversations.values()
            if item.last_timestamp > 0 or counts.get(item.conversation_id, 0) > 0
        ]
        result.sort(key=lambda item: (item.last_timestamp, item.display_name), reverse=True)
        log_wecom(
            "list_sessions "
            f"table={'conversation_table' if has_conversation_table else 'missing'} "
            f"rows={len(conversations)} filtered={len(result)} "
            f"message_conversations={len(counts)}",
        )
        return result

    def load_messages(
        self,
        conversation_id: str,
        max_messages: int = MAX_EXPORT_MESSAGES,
    ) -> List[ChatMessage]:
        """Load text-capable messages for one conversation."""
        cache_root = self._cache.ensure_chat_dbs()
        user_dir = _load_user_directory(cache_root)
        member_names = _load_group_member_names(cache_root)
        is_group = conversation_id.startswith("R:")
        messages: List[ChatMessage] = []
        for message_db in _iter_message_dbs(cache_root):
            with closing(sqlite3.connect(str(message_db))) as conn:
                conn.row_factory = sqlite3.Row
                for table in _MESSAGE_TABLES:
                    if not _table_exists(conn, table):
                        continue
                    rows = conn.execute(
                        f"""
                        SELECT sender_id, content_type, send_time, content, extra_content, local_extra_content
                        FROM "{table}"
                        WHERE conversation_id = ?
                        ORDER BY send_time ASC, message_id ASC
                        LIMIT ?
                        """,
                        (conversation_id, max_messages),
                    ).fetchall()
                    for row in rows:
                        text = _display_message_content(
                            int(row["content_type"] or 0),
                            row["content"],
                            row["extra_content"],
                            row["local_extra_content"],
                        )
                        if not text:
                            continue
                        sender_id = int(row["sender_id"] or 0)
                        if self._self_id is not None and sender_id == self._self_id:
                            sender = "我"
                        elif is_group:
                            sender = user_dir.sender_label(sender_id, conversation_id, member_names)
                        else:
                            sender = user_dir.label_for_user(sender_id)
                        if not sender:
                            sender = str(sender_id) if sender_id else "系统"
                        messages.append(
                            ChatMessage(
                                sender=str(sender),
                                text=text,
                                timestamp=format_session_time(int(row["send_time"] or 0)),
                            )
                        )
        messages.sort(key=lambda item: item.timestamp)
        return messages[-max_messages:]


def _find_session_db(cache_root: Path) -> Optional[Path]:
    for rel in ("session/session.db", "session.db"):
        path = cache_root / rel.replace("/", "\\")
        if path.is_file():
            return path
    return None


def _iter_message_dbs(cache_root: Path) -> List[Path]:
    message_dir = cache_root / "message"
    paths: List[Path] = []
    seen: set[Path] = set()
    if message_dir.is_dir():
        for path in sorted(message_dir.glob("*.db")):
            if path not in seen:
                seen.add(path)
                paths.append(path)
    flat = cache_root / "message.db"
    if flat.is_file() and flat not in seen:
        seen.add(flat)
        paths.append(flat)
    for path in sorted(cache_root.glob("message_*.db")):
        if path not in seen:
            seen.add(path)
            paths.append(path)
    return paths


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return row is not None


def _load_user_directory(cache_root: Path) -> WeComUserDirectory:
    remarks: Dict[int, str] = {}
    display_names: Dict[int, str] = {}
    user_db = cache_root / "user" / "user.db"
    if not user_db.is_file():
        user_db = cache_root / "user.db"
    if not user_db.is_file():
        return WeComUserDirectory(remarks=remarks, display_names=display_names)
    with closing(sqlite3.connect(str(user_db))) as conn:
        conn.row_factory = sqlite3.Row
        if _table_exists(conn, "user_table"):
            for row in conn.execute("SELECT id, name, real_name, account, external_corp_name FROM user_table"):
                name = str(row["real_name"] or row["name"] or row["account"] or "").strip()
                corp = str(row["external_corp_name"] or "").strip()
                if corp and corp not in name:
                    name = f"{name} ({corp})" if name else corp
                if name:
                    display_names[int(row["id"])] = name
        if _table_exists(conn, "external_user_relation_v3"):
            for row in conn.execute(
                "SELECT user_id, remarks, real_remarks, corp_remark FROM external_user_relation_v3"
            ):
                remark = str(row["real_remarks"] or row["remarks"] or row["corp_remark"] or "").strip()
                if remark:
                    remarks[int(row["user_id"])] = remark
    return WeComUserDirectory(remarks=remarks, display_names=display_names)


def _load_user_map(cache_root: Path) -> Dict[int, str]:
    directory = _load_user_directory(cache_root)
    merged: Dict[int, str] = dict(directory.display_names)
    merged.update(directory.remarks)
    return merged


def _load_group_member_names(cache_root: Path) -> Dict[str, Dict[int, str]]:
    members: Dict[str, Dict[int, str]] = defaultdict(dict)
    session_db = _find_session_db(cache_root)
    if session_db is None:
        return members
    with closing(sqlite3.connect(str(session_db))) as conn:
        conn.row_factory = sqlite3.Row
        if _table_exists(conn, "conversation_user_table"):
            for row in conn.execute("SELECT conversation_id, user_id, nick_name FROM conversation_user_table"):
                nick = str(row["nick_name"] or "").strip()
                if nick:
                    members[str(row["conversation_id"])][int(row["user_id"])] = nick
        if _table_exists(conn, "conversation_member_nickname_table"):
            room_map: Dict[int, str] = {}
            if _table_exists(conn, "conversation_table"):
                for row in conn.execute("SELECT con_numeric_id, id FROM conversation_table"):
                    room_map[int(row["con_numeric_id"])] = str(row["id"])
            for row in conn.execute("SELECT room_id, userid, nickname FROM conversation_member_nickname_table"):
                conversation_id = room_map.get(int(row["room_id"] or 0))
                nick = str(row["nickname"] or "").strip()
                if conversation_id and nick:
                    members[conversation_id][int(row["userid"])] = nick
    return members


def _conversation_display_name(
    conversation_id: str,
    name: str,
    roomname_remark: str,
    user_dir: WeComUserDirectory,
    self_id: Optional[int],
) -> str:
    if conversation_id.startswith("R:"):
        remark = roomname_remark.strip()
        if remark:
            return remark
        group_name = name.strip()
        if group_name:
            return group_name
        return conversation_id
    derived = _name_from_conversation_id(conversation_id, user_dir, self_id)
    if derived != conversation_id:
        return derived
    fallback = roomname_remark.strip() or name.strip()
    return fallback or conversation_id


def _name_from_conversation_id(
    conversation_id: str,
    user_dir: WeComUserDirectory,
    self_id: Optional[int],
) -> str:
    if conversation_id.startswith("S:"):
        ids: List[int] = []
        for value in conversation_id[2:].split("_"):
            if value.isdigit():
                ids.append(int(value))
        other_ids = [uid for uid in ids if self_id is None or uid != self_id]
        for uid in other_ids or ids:
            if uid in user_dir.remarks:
                return user_dir.remarks[uid]
            if uid in user_dir.display_names:
                return user_dir.display_names[uid]
    if ":" in conversation_id:
        tail = conversation_id.split(":", 1)[1]
        if tail.isdigit():
            user_id = int(tail)
            if user_id in user_dir.remarks:
                return user_dir.remarks[user_id]
            if user_id in user_dir.display_names:
                return user_dir.display_names[user_id]
    return conversation_id


def _load_message_counts(cache_root: Path) -> tuple[Dict[str, int], Dict[str, int]]:
    counts: Dict[str, int] = defaultdict(int)
    last_times: Dict[str, int] = defaultdict(int)
    for message_db in _iter_message_dbs(cache_root):
        with closing(sqlite3.connect(str(message_db))) as conn:
            conn.row_factory = sqlite3.Row
            for table in _MESSAGE_TABLES:
                if not _table_exists(conn, table):
                    continue
                for row in conn.execute(
                    f"""
                    SELECT conversation_id, COUNT(*) AS total, MAX(send_time) AS last_time
                    FROM "{table}"
                    GROUP BY conversation_id
                    """
                ):
                    conversation_id = str(row["conversation_id"] or "")
                    if not conversation_id:
                        continue
                    counts[conversation_id] += int(row["total"] or 0)
                    last_times[conversation_id] = max(
                        last_times[conversation_id],
                        int(row["last_time"] or 0),
                    )
    return counts, last_times


def _clean_text(text: str) -> str:
    cleaned = "".join(ch if ch in "\n\t" or (ch.isprintable() and ch not in "\x0b\x0c") else " " for ch in text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _decode_content(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return _clean_text(raw)
    data = bytes(raw)
    if not data:
        return ""
    for encoding in ("utf-8", "gbk"):
        try:
            text = _clean_text(data.decode(encoding))
            if text:
                return text[:2000]
        except UnicodeDecodeError:
            continue
    return f"[binary {len(data)} bytes]"


def _display_message_content(
    content_type: int,
    content: object,
    extra_content: object,
    local_extra_content: object,
) -> str:
    if content_type not in _MSG_TYPE_TEXT and content_type not in (0, 2, 38):
        if content_type in (4, 7, 15):
            return "[media]"
    body = _decode_content(content)
    extra = _decode_content(extra_content)
    local_extra = _decode_content(local_extra_content)
    text = body or extra or local_extra
    if text:
        return text
    if content_type in (4, 7, 15):
        return "[media]"
    return ""


def account_for_cache(status: WeComLocalStatus, keys: Dict[str, str]) -> WeComDbReader:
    """Build a reader from a status snapshot and extracted keys."""
    account = account_from_status(status)
    if account is None:
        raise WeComDbError("No WeCom account database found")
    return WeComDbReader(WeComDbCache(account, keys), self_id=status.user_id)
