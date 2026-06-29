"""Read WeChat 4.x sessions and messages from decrypted local WCDB databases."""

from __future__ import annotations

import hashlib
import re
import sqlite3
import xml.etree.ElementTree as ET
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from file_reader.chat.messages import MAX_EXPORT_MESSAGES, ChatMessage
from file_reader.wechat.key_extract import resolve_db_dir
from file_reader.wechat.version import resolve_crypto_variant
from file_reader.wechat.wcdb import DecryptedDbCache, WeChatKeyError, default_cache_dir

try:
    import zstandard as zstd
except ImportError:
    zstd = None

_MSG_TABLE_RE = re.compile(r"Msg_[0-9a-f]{32}")
_MESSAGE_DB_RE = re.compile(r"message/message_\d+\.db$")
_OFFICIAL_VERIFY_FLAGS = frozenset({8, 24})
_BRAND_SESSION_HOLDERS = frozenset(
    {
        "brandsessionholder",
        "brandservicesessionholder",
    }
)


class WeChatDbError(RuntimeError):
    """Failed to read decrypted WeChat databases."""


@dataclass(frozen=True)
class WeChatSessionPreview:
    """Recent chat session from local WeChat databases."""

    username: str
    display_name: str
    last_timestamp: int
    summary: str
    is_group: bool
    unread_count: int = 0


def _split_msg_type(local_type: int) -> Tuple[int, int]:
    try:
        value = int(local_type)
    except (TypeError, ValueError):
        return 0, 0
    if value > 0xFFFFFFFF:
        return value & 0xFFFFFFFF, value >> 32
    return value, 0


def _zstd_decompress(data: bytes) -> Optional[str]:
    if zstd is None:
        return None
    try:
        return zstd.ZstdDecompressor().decompress(data).decode("utf-8", errors="replace")
    except (OSError, ValueError, RuntimeError):
        return None


def _decompress_content(content: object, compression_type: object) -> Optional[str]:
    if content is None:
        return None
    if compression_type == 4 and isinstance(content, bytes):
        decoded = _zstd_decompress(content)
        if decoded is not None:
            return decoded
    if isinstance(content, bytes):
        return content.decode("utf-8", errors="replace")
    if isinstance(content, str):
        return content
    return str(content)


def _parse_xml_root(content: str) -> Optional[ET.Element]:
    if not content or len(content) > 20000:
        return None
    if "<!DOCTYPE" in content or "<!ENTITY" in content:
        return None
    try:
        return ET.fromstring(content)
    except ET.ParseError:
        return None


def _parse_group_sender(content: str, is_group: bool) -> Tuple[str, str]:
    if not is_group or not content:
        return "", content
    if ":\n" in content:
        sender, text = content.split(":\n", 1)
        return sender, text
    match = re.match(r"^([A-Za-z0-9_\-@.]+):(<\?xml|<msg|<msglist|<voipmsg|<sysmsg)", content)
    if match:
        sender = match.group(1)
        return sender, content[len(sender) + 1 :]
    return "", content


def _app_message_title(content: str) -> str:
    root = _parse_xml_root(content)
    if root is None:
        return ""
    title = (root.findtext(".//title") or "").strip()
    return title


def _format_message_text(
    local_type: int,
    content: Optional[str],
    *,
    is_group: bool,
) -> str:
    if content is None:
        return ""
    sender_from_content, text = _parse_group_sender(content, is_group)
    base_type, _ = _split_msg_type(local_type)
    if base_type == 1:
        return text
    if base_type == 3:
        return "[图片]"
    if base_type == 34:
        return "[语音]"
    if base_type == 43:
        return "[视频]"
    if base_type == 47:
        return "[表情]"
    if base_type == 49:
        title = _app_message_title(text)
        return f"[链接/文件] {title}".strip() if title else "[链接/文件]"
    if base_type == 50:
        return "[通话]"
    if base_type == 10000:
        if "<sysmsg" in text:
            root = _parse_xml_root(text)
            if root is not None:
                inner = root.findtext(".//content")
                if inner and inner.strip():
                    return inner.strip()
        return text or "[系统消息]"
    if base_type == 10002:
        return "[撤回消息]"
    if sender_from_content and text:
        return text
    return text or "[消息]"


def _is_official_account_username(username: str) -> bool:
    """True for WeChat official accounts (公众号) and subscription holders."""
    if not username:
        return True
    lowered = username.lower()
    if lowered.startswith("gh_"):
        return True
    return lowered in _BRAND_SESSION_HOLDERS


@dataclass(frozen=True)
class ContactDirectory:
    """Contact display fields from ``contact.db``."""

    display_names: Dict[str, str]
    remarks: Dict[str, str]
    nick_names: Dict[str, str]


def _load_contact_directory(contact_db: Path) -> ContactDirectory:
    display_names: Dict[str, str] = {}
    remarks: Dict[str, str] = {}
    nick_names: Dict[str, str] = {}
    with closing(sqlite3.connect(contact_db)) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(contact)").fetchall()}
        has_local_type = "local_type" in columns
        has_verify_flag = "verify_flag" in columns
        select_cols = "username, nick_name, remark"
        if has_verify_flag:
            select_cols += ", verify_flag"
        sql = f"SELECT {select_cols} FROM contact"
        if has_local_type:
            sql += " WHERE local_type != 3"
        rows = conn.execute(sql).fetchall()
    for row in rows:
        username = row[0]
        nick_name = row[1]
        remark = row[2]
        verify_flag = int(row[3] or 0) if has_verify_flag and len(row) > 3 else 0
        if not username:
            continue
        if _is_official_account_username(username):
            continue
        if verify_flag in _OFFICIAL_VERIFY_FLAGS:
            continue
        cleaned_remark = (remark or "").strip()
        cleaned_nick = (nick_name or "").strip()
        if cleaned_remark:
            remarks[username] = cleaned_remark
        if cleaned_nick:
            nick_names[username] = cleaned_nick
        display_names[username] = cleaned_remark or cleaned_nick or username
    return ContactDirectory(display_names=display_names, remarks=remarks, nick_names=nick_names)


def _load_contact_names(contact_db: Path) -> Dict[str, str]:
    return _load_contact_directory(contact_db).display_names


def _self_username(account_dir: Path, names: Dict[str, str]) -> str:
    label = account_dir.name
    candidates = [label]
    match = re.fullmatch(r"(.+)_([0-9a-fA-F]{4,})", label)
    if match:
        candidates.insert(0, match.group(1))
    for candidate in candidates:
        if candidate in names:
            return candidate
    return ""


def _self_display_name(
    account_dir: Path,
    contacts: ContactDirectory,
    self_username: str,
) -> str:
    """Display name for the signed-in account — prefer contact ``remark`` (备注)."""
    if self_username and self_username in contacts.remarks:
        return contacts.remarks[self_username]
    if self_username and self_username in contacts.nick_names:
        return contacts.nick_names[self_username]
    label = account_dir.name
    match = re.fullmatch(r"(.+)_([0-9a-fA-F]{4,})", label)
    if match:
        prefix = match.group(1)
        if prefix in contacts.remarks:
            return contacts.remarks[prefix]
        if prefix in contacts.nick_names:
            return contacts.nick_names[prefix]
        return prefix
    if self_username:
        return self_username
    return label


def _display_name_for_username(
    username: str,
    *,
    self_username: str,
    self_display_name: str,
    contacts: ContactDirectory,
) -> str:
    if not username:
        return ""
    if username == self_username:
        return self_display_name
    if username in contacts.remarks:
        return contacts.remarks[username]
    return contacts.display_names.get(username, username)


def _resolve_sender_label(
    real_sender_id: int,
    sender_from_content: str,
    *,
    is_group: bool,
    chat_username: str,
    chat_display_name: str,
    self_username: str,
    self_display_name: str,
    contacts: ContactDirectory,
    id_to_username: Dict[int, str],
) -> str:
    sender_username = id_to_username.get(real_sender_id, "")
    if is_group:
        if sender_username and sender_username != chat_username:
            return _display_name_for_username(
                sender_username,
                self_username=self_username,
                self_display_name=self_display_name,
                contacts=contacts,
            )
        if sender_from_content:
            return _display_name_for_username(
                sender_from_content,
                self_username=self_username,
                self_display_name=self_display_name,
                contacts=contacts,
            )
        return ""
    if sender_username == chat_username:
        if chat_username in contacts.remarks:
            return contacts.remarks[chat_username]
        return chat_display_name
    if sender_username:
        return _display_name_for_username(
            sender_username,
            self_username=self_username,
            self_display_name=self_display_name,
            contacts=contacts,
        )
    if sender_from_content:
        return _display_name_for_username(
            sender_from_content,
            self_username=self_username,
            self_display_name=self_display_name,
            contacts=contacts,
        )
    if self_username:
        return self_display_name
    return ""


def _decode_summary(summary: object, is_group: bool) -> str:
    if summary is None:
        return ""
    if isinstance(summary, bytes):
        decoded = _zstd_decompress(summary)
        if decoded is None:
            decoded = summary.decode("utf-8", errors="replace")
        summary = decoded
    text = str(summary)
    if is_group and ":\n" in text:
        return text.split(":\n", 1)[1]
    return text


class WeChatDbReader:
    """Load recent chats and messages from a WeChat v3/v4 account directory."""

    def __init__(
        self,
        account_dir: Path,
        cache: Optional[DecryptedDbCache] = None,
        *,
        client_variant: Optional[str] = None,
    ) -> None:
        variant = client_variant or ("v4" if (account_dir / "db_storage").is_dir() else "v3")
        if variant == "v4":
            variant = resolve_crypto_variant("v4")
        db_dir = resolve_db_dir(account_dir, variant)
        if not db_dir.is_dir():
            raise WeChatDbError(f"WeChat database folder not found under {account_dir}")
        if variant in {"v4", "v4.1"}:
            self._require_v4_layout(db_dir)
        self._account_dir = account_dir
        self._client_variant = variant
        self._db_dir = db_dir
        self._cache = cache or DecryptedDbCache(
            db_dir,
            default_cache_dir(account_dir),
            client_variant=variant,
            account_dir=account_dir,
        )

    @staticmethod
    def _require_v4_layout(db_dir: Path) -> None:
        session_db = db_dir / "session" / "session.db"
        if not session_db.is_file():
            raise WeChatDbError("WeChat 4.x session database not found — use export folder mode")

    def list_sessions(self, limit: int = 500) -> List[WeChatSessionPreview]:
        """Return chat sessions sorted by last activity (session table + message shards)."""
        try:
            session_db = self._cache.plain_path("session/session.db")
            contact_db = self._cache.plain_path("contact/contact.db")
        except (WeChatKeyError, OSError, ValueError) as exc:
            raise WeChatDbError(str(exc)) from exc

        names = _load_contact_names(contact_db)
        msg_index = self._index_message_tables()
        by_username: Dict[str, WeChatSessionPreview] = {}

        with closing(sqlite3.connect(session_db)) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(SessionTable)").fetchall()}
            has_sort = "sort_timestamp" in columns
            has_hidden = "is_hidden" in columns
            select_cols = "username, unread_count, summary, last_timestamp"
            if has_sort:
                select_cols += ", sort_timestamp"
            else:
                select_cols += ", 0 AS sort_timestamp"
            hidden_clause = " AND COALESCE(is_hidden, 0) = 0" if has_hidden else ""
            if has_sort:
                time_clause = "last_timestamp > 0 OR sort_timestamp > 0"
                order_expr = "COALESCE(NULLIF(sort_timestamp, 0), last_timestamp)"
            else:
                time_clause = "last_timestamp > 0"
                order_expr = "last_timestamp"
            rows = conn.execute(
                f"""
                SELECT {select_cols}
                FROM SessionTable
                WHERE ({time_clause}){hidden_clause}
                ORDER BY {order_expr} DESC
                """,
            ).fetchall()

        for row in rows:
            username, unread, summary, last_timestamp, sort_timestamp = row
            if not username or _is_official_account_username(username):
                continue
            is_group = "@chatroom" in username
            activity_ts = _session_sort_timestamp(
                int(last_timestamp or 0),
                int(sort_timestamp or 0),
            )
            table_name = _username_to_msg_table(username)
            msg_stats = msg_index.get(table_name)
            if msg_stats is not None:
                _count, msg_ts = msg_stats
                activity_ts = max(activity_ts, msg_ts)
            by_username[username] = WeChatSessionPreview(
                username=username,
                display_name=names.get(username, username),
                last_timestamp=activity_ts,
                summary=_decode_summary(summary, is_group),
                is_group=is_group,
                unread_count=int(unread or 0),
            )

        for username, display in names.items():
            if username in by_username:
                continue
            if _is_official_account_username(username):
                continue
            table_name = _username_to_msg_table(username)
            msg_stats = msg_index.get(table_name)
            if msg_stats is None:
                continue
            _count, msg_ts = msg_stats
            by_username[username] = WeChatSessionPreview(
                username=username,
                display_name=display,
                last_timestamp=msg_ts,
                summary="",
                is_group="@chatroom" in username,
                unread_count=0,
            )

        previews = sorted(by_username.values(), key=lambda item: item.last_timestamp, reverse=True)
        return previews[:limit]

    def _index_message_tables(self) -> Dict[str, Tuple[int, int]]:
        """Map Msg_<md5> table names to (row_count, max_create_time)."""
        index: Dict[str, Tuple[int, int]] = {}
        for rel in sorted(self._cache.keys.keys()):
            normalized = rel.replace("\\", "/")
            if not _MESSAGE_DB_RE.fullmatch(normalized):
                continue
            db_path = self._cache.plain_path(rel)
            with closing(sqlite3.connect(db_path)) as conn:
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'",
                ).fetchall()
                for (table_name,) in tables:
                    if not _MSG_TABLE_RE.fullmatch(table_name):
                        continue
                    row = conn.execute(
                        f"SELECT COUNT(*), MAX(create_time) FROM [{table_name}]",
                    ).fetchone()
                    count = int(row[0] or 0)
                    max_ts = int(row[1] or 0)
                    if count <= 0:
                        continue
                    previous = index.get(table_name)
                    if previous is None:
                        index[table_name] = (count, max_ts)
                    else:
                        index[table_name] = (previous[0] + count, max(previous[1], max_ts))
        return index

    def load_messages(
        self,
        username: str,
        *,
        max_messages: int = MAX_EXPORT_MESSAGES,
    ) -> List[ChatMessage]:
        """Load chat messages for a username across message DB shards."""
        try:
            contact_db = self._cache.plain_path("contact/contact.db")
        except (WeChatKeyError, OSError, ValueError) as exc:
            raise WeChatDbError(str(exc)) from exc

        contacts = _load_contact_directory(contact_db)
        names = contacts.display_names
        self_username = _self_username(self._account_dir, names)
        self_display_name = _self_display_name(self._account_dir, contacts, self_username)
        is_group = "@chatroom" in username
        table_name = _username_to_msg_table(username)
        if not _MSG_TABLE_RE.fullmatch(table_name):
            raise WeChatDbError("invalid message table name")

        shard_paths = self._message_db_paths(table_name)
        if not shard_paths:
            return []

        collected: List[Tuple[int, int, Dict[int, str], Tuple[object, ...]]] = []
        try:
            for db_path in shard_paths:
                with closing(sqlite3.connect(db_path)) as conn:
                    exists = conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (table_name,),
                    ).fetchone()
                    if not exists:
                        continue
                    id_to_username = self._load_name2id(conn)
                    select_sql = self._message_select_sql(conn, table_name)
                    rows = conn.execute(select_sql).fetchall()
                    for row in rows:
                        create_time = int(row[2] or 0)
                        local_id = int(row[0] or 0)
                        collected.append((create_time, local_id, id_to_username, row))

            if not collected:
                return []

            collected.sort(key=lambda item: (item[0], item[1]))
            if len(collected) > max_messages:
                collected = collected[-max_messages:]

            messages: List[ChatMessage] = []
            for create_time, _local_id, id_to_username, row in collected:
                _local_id_val, local_type, _create_time, real_sender_id, content, ct = row
                decoded = _decompress_content(content, ct)
                sender_from_content, _ = _parse_group_sender(decoded or "", is_group)
                sender = _resolve_sender_label(
                    int(real_sender_id or 0),
                    sender_from_content,
                    is_group=is_group,
                    chat_username=username,
                    chat_display_name=names.get(username, username),
                    self_username=self_username,
                    self_display_name=self_display_name,
                    contacts=contacts,
                    id_to_username=id_to_username,
                )
                if not sender:
                    sender = "Unknown"
                text = _format_message_text(int(local_type or 0), decoded, is_group=is_group)
                timestamp = None
                if create_time:
                    timestamp = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M:%S")
                if text:
                    messages.append(ChatMessage(sender=sender, text=text, timestamp=timestamp))
            return messages
        except sqlite3.Error as exc:
            raise WeChatDbError(str(exc)) from exc

    def _message_db_paths(self, table_name: str) -> List[Path]:
        paths: List[Path] = []
        for rel in sorted(self._cache.keys.keys()):
            if not _MESSAGE_DB_RE.fullmatch(rel.replace("\\", "/")):
                continue
            db_path = self._cache.plain_path(rel)
            with closing(sqlite3.connect(db_path)) as conn:
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                ).fetchone()
            if exists:
                paths.append(db_path)
        return paths

    @staticmethod
    def _message_select_sql(conn: sqlite3.Connection, table_name: str) -> str:
        columns = {row[1] for row in conn.execute(f"PRAGMA table_info([{table_name}])").fetchall()}
        content_col = "message_content"
        if content_col not in columns and "compress_content" in columns:
            content_col = "compress_content"
        ct_col = "NULL"
        for candidate in ("WCDB_CT_message_content", "compress_type"):
            if candidate in columns:
                ct_col = candidate
                break
        return (
            f"SELECT local_id, local_type, create_time, real_sender_id, "
            f"{content_col}, {ct_col} "
            f"FROM [{table_name}] ORDER BY create_time ASC"
        )

    @staticmethod
    def _load_name2id(conn: sqlite3.Connection) -> Dict[int, str]:
        mapping: Dict[int, str] = {}
        try:
            rows = conn.execute("SELECT rowid, user_name FROM Name2Id").fetchall()
        except sqlite3.Error:
            return mapping
        for rowid, user_name in rows:
            if user_name:
                mapping[int(rowid)] = user_name
        return mapping


def _username_to_msg_table(username: str) -> str:
    return f"Msg_{hashlib.md5(username.encode()).hexdigest()}"


def _session_sort_timestamp(last_timestamp: int, sort_timestamp: int) -> int:
    return max(last_timestamp, sort_timestamp)


def format_chat_preview(messages: List[ChatMessage], *, max_lines: int = 40) -> str:
    """Format recent messages for the live-chat preview panel."""
    if not messages:
        return ""
    tail = messages[-max_lines:]
    lines: List[str] = []
    for message in tail:
        prefix = message.timestamp or ""
        if prefix:
            lines.append(f"[{prefix}] {message.sender}: {message.text}")
        else:
            lines.append(f"{message.sender}: {message.text}")
    return "\n".join(lines)


def format_session_time(timestamp: int) -> str:
    """Compact timestamp label for list rows."""
    if timestamp <= 0:
        return ""
    return datetime.fromtimestamp(timestamp).strftime("%m-%d %H:%M")
