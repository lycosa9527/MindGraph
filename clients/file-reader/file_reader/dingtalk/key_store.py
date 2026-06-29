"""Persist DingTalk unlock state per MindGraph user and local account."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from file_reader.dpapi_store import DpapiError, dpapi_available, protect_bytes, unprotect_bytes
from file_reader.dingtalk.discovery import DingTalkAccountCandidate
from file_reader.settings import SETTINGS_DIR

DINGTALK_UNLOCK_DIR = SETTINGS_DIR / "dingtalk-unlock"
_CACHE_VERSION = 1


@dataclass(frozen=True)
class DingTalkUnlockPersistContext:
    """MindGraph user binding for incremental DingTalk unlock persistence."""

    mindgraph_user_id: int
    mindgraph_phone: str
    account_folder_id: str


@dataclass(frozen=True)
class DingTalkUnlockCacheRecord:
    """Cached DingTalk decrypt parameters for one account."""

    storage_version: str
    key_uid: str
    salt_hex: str
    db_mtime: float
    account_folder_id: str
    data_dir: str
    mindgraph_user_id: int
    mindgraph_phone: str
    saved_at: float


def _slug(value: str, *, max_len: int = 32) -> str:
    cleaned = re.sub(r"[^\w.-]", "_", value.strip())
    return cleaned[:max_len] or "unknown"


def build_unlock_cache_key(
    *,
    mindgraph_user_id: int,
    account_folder_id: str,
    data_dir: Path,
) -> str:
    """Stable filename stem for a MindGraph user + DingTalk account pair."""
    account_digest = hashlib.sha256(str(data_dir.resolve()).encode("utf-8")).hexdigest()[:16]
    return f"mg{mindgraph_user_id}_{_slug(account_folder_id)}_{account_digest}"


def unlock_cache_file_path(cache_key: str) -> Path:
    """DPAPI-protected unlock cache file."""
    return DINGTALK_UNLOCK_DIR / f"{cache_key}.dpapi"


def cache_entry_exists(
    *,
    mindgraph_user_id: int,
    account_folder_id: str,
    data_dir: Path,
) -> bool:
    """True when an unlock cache file exists for this binding."""
    path = unlock_cache_file_path(
        build_unlock_cache_key(
            mindgraph_user_id=mindgraph_user_id,
            account_folder_id=account_folder_id,
            data_dir=data_dir,
        )
    )
    return path.is_file()


def save_dingtalk_unlock_cache(
    account: DingTalkAccountCandidate,
    *,
    key_uid: str,
    salt_hex: Optional[str],
    db_mtime: float,
    context: DingTalkUnlockPersistContext,
) -> None:
    """Persist unlock parameters immediately after a successful decrypt."""
    if not dpapi_available():
        return
    cache_key = build_unlock_cache_key(
        mindgraph_user_id=context.mindgraph_user_id,
        account_folder_id=context.account_folder_id,
        data_dir=account.data_dir,
    )
    DINGTALK_UNLOCK_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _CACHE_VERSION,
        "storage_version": account.version,
        "key_uid": key_uid,
        "salt_hex": salt_hex or "",
        "db_mtime": db_mtime,
        "account_folder_id": context.account_folder_id,
        "data_dir": str(account.data_dir.resolve()),
        "mindgraph_user_id": context.mindgraph_user_id,
        "mindgraph_phone": context.mindgraph_phone,
        "saved_at": time.time(),
    }
    path = unlock_cache_file_path(cache_key)
    path.write_bytes(protect_bytes(json.dumps(payload, separators=(",", ":")).encode("utf-8")))


def clear_dingtalk_unlock_cache(
    *,
    mindgraph_user_id: int,
    account_folder_id: str,
    data_dir: Path,
) -> None:
    """Remove cached unlock parameters for one MindGraph user and DingTalk account."""
    path = unlock_cache_file_path(
        build_unlock_cache_key(
            mindgraph_user_id=mindgraph_user_id,
            account_folder_id=account_folder_id,
            data_dir=data_dir,
        )
    )
    if path.is_file():
        path.unlink()


def load_dingtalk_unlock_cache(
    account: DingTalkAccountCandidate,
    *,
    mindgraph_user_id: int,
    account_folder_id: str,
) -> Optional[DingTalkUnlockCacheRecord]:
    """Load unlock cache when the encrypted database mtime still matches."""
    if not dpapi_available():
        return None
    cache_key = build_unlock_cache_key(
        mindgraph_user_id=mindgraph_user_id,
        account_folder_id=account_folder_id,
        data_dir=account.data_dir,
    )
    path = unlock_cache_file_path(cache_key)
    if not path.is_file():
        return None

    def _invalidate() -> None:
        clear_dingtalk_unlock_cache(
            mindgraph_user_id=mindgraph_user_id,
            account_folder_id=account_folder_id,
            data_dir=account.data_dir,
        )

    try:
        payload = json.loads(unprotect_bytes(path.read_bytes()).decode("utf-8"))
    except (OSError, DpapiError, json.JSONDecodeError, ValueError, UnicodeDecodeError):
        _invalidate()
        return None
    if not isinstance(payload, dict) or payload.get("version") != _CACHE_VERSION:
        _invalidate()
        return None
    try:
        db_mtime = float(payload.get("db_mtime") or 0.0)
    except (TypeError, ValueError):
        _invalidate()
        return None
    current_mtime = account.db_path.stat().st_mtime
    if db_mtime != current_mtime:
        _invalidate()
        return None
    key_uid = str(payload.get("key_uid") or "")
    if not key_uid:
        _invalidate()
        return None
    return DingTalkUnlockCacheRecord(
        storage_version=str(payload.get("storage_version") or account.version),
        key_uid=key_uid,
        salt_hex=str(payload.get("salt_hex") or ""),
        db_mtime=db_mtime,
        account_folder_id=str(payload.get("account_folder_id") or account_folder_id),
        data_dir=str(payload.get("data_dir") or str(account.data_dir)),
        mindgraph_user_id=int(payload.get("mindgraph_user_id") or mindgraph_user_id),
        mindgraph_phone=str(payload.get("mindgraph_phone") or ""),
        saved_at=float(payload.get("saved_at") or 0.0),
    )
