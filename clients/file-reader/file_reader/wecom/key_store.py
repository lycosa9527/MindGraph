"""Persist extracted WeCom DB keys per MindGraph user and local account."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from file_reader.dpapi_store import DpapiError, dpapi_available, protect_bytes, unprotect_bytes
from file_reader.settings import SETTINGS_DIR
from file_reader.wecom.crypto import is_wxsqlite3_aes128_page1, verify_wxsqlite3_aes128_key
from file_reader.wecom.debug_log import log_wecom
from file_reader.wecom.discovery import DbFileEntry, collect_db_files, is_session_db_rel

WECOM_KEYS_DIR = SETTINGS_DIR / "wecom-keys"
_CACHE_VERSION = 1


@dataclass(frozen=True)
class WeComKeyCacheRecord:
    """Decrypted WeCom DB keys linked to a MindGraph user and local account."""

    keys: Dict[str, str]
    method: str
    account_label: str
    data_dir: str
    mindgraph_user_id: int
    mindgraph_phone: str
    saved_at: float


@dataclass(frozen=True)
class WeComKeyPersistContext:
    """MindGraph user binding for incremental WeCom key persistence."""

    mindgraph_user_id: int
    mindgraph_phone: str
    account_label: str
    method: str = "memory_scan"


def _slug(value: str, *, max_len: int = 32) -> str:
    cleaned = re.sub(r"[^\w.-]", "_", value.strip())
    return cleaned[:max_len] or "unknown"


def build_cache_key(
    *,
    mindgraph_user_id: int,
    account_label: str,
    data_dir: Path,
) -> str:
    """Stable filename stem for a MindGraph user + WeCom account pair."""
    account_digest = hashlib.sha256(str(data_dir.resolve()).encode("utf-8")).hexdigest()[:16]
    return f"mg{mindgraph_user_id}_{_slug(account_label)}_{account_digest}"


def cache_file_path(cache_key: str) -> Path:
    """DPAPI-protected cache file for one user/account binding."""
    return WECOM_KEYS_DIR / f"{cache_key}.dpapi"


def cache_entry_exists(
    *,
    mindgraph_user_id: int,
    account_label: str,
    data_dir: Path,
) -> bool:
    """True when a cache file exists for this MindGraph user and WeCom account."""
    path = cache_file_path(
        build_cache_key(
            mindgraph_user_id=mindgraph_user_id,
            account_label=account_label,
            data_dir=data_dir,
        )
    )
    return path.is_file()


def filter_valid_wecom_keys(data_dir: Path, keys: Dict[str, str]) -> Dict[str, str]:
    """Return cached rel-path keys that still decrypt their on-disk databases."""
    if not keys:
        return {}
    db_files = [entry for entry in collect_db_files(data_dir) if is_wxsqlite3_aes128_page1(entry[4])]
    rel_to_page1 = {rel: page1 for rel, _path, _size, _salt, page1 in db_files}
    valid: Dict[str, str] = {}
    for rel, hex_key in keys.items():
        page1 = rel_to_page1.get(rel)
        if page1 is None:
            continue
        try:
            raw_key = bytes.fromhex(hex_key)
        except ValueError:
            continue
        if verify_wxsqlite3_aes128_key(raw_key, page1):
            valid[rel] = hex_key
    return valid


def _session_key_ready(data_dir: Path, keys: Dict[str, str]) -> bool:
    for rel, _path, _size, _salt, page1 in collect_db_files(data_dir):
        if not is_session_db_rel(rel):
            continue
        if not is_wxsqlite3_aes128_page1(page1):
            return True
        hex_key = keys.get(rel)
        if hex_key is None:
            return False
        try:
            raw_key = bytes.fromhex(hex_key)
        except ValueError:
            return False
        return verify_wxsqlite3_aes128_key(raw_key, page1)
    return bool(keys)


def validate_cached_keys(data_dir: Path, keys: Dict[str, str]) -> bool:
    """True when cached keys can unlock the current WeCom chat databases."""
    valid = filter_valid_wecom_keys(data_dir, keys)
    if not valid:
        return False
    return _session_key_ready(data_dir, valid)


def _read_cache_payload(
    data_dir: Path,
    *,
    mindgraph_user_id: int,
    account_label: str,
) -> Optional[WeComKeyCacheRecord]:
    if not dpapi_available():
        return None
    cache_key = build_cache_key(
        mindgraph_user_id=mindgraph_user_id,
        account_label=account_label,
        data_dir=data_dir,
    )
    path = cache_file_path(cache_key)
    if not path.is_file():
        return None
    try:
        payload = json.loads(unprotect_bytes(path.read_bytes()).decode("utf-8"))
    except (OSError, DpapiError, json.JSONDecodeError, ValueError, UnicodeDecodeError):
        log_wecom(f"wecom key cache unreadable path={path}", level="WARN")
        clear_wecom_key_cache(
            mindgraph_user_id=mindgraph_user_id,
            account_label=account_label,
            data_dir=data_dir,
        )
        return None
    if not isinstance(payload, dict) or payload.get("version") != _CACHE_VERSION:
        return None
    keys_raw = payload.get("keys")
    if not isinstance(keys_raw, dict):
        return None
    keys = {str(rel): str(hex_key) for rel, hex_key in keys_raw.items() if hex_key}
    return WeComKeyCacheRecord(
        keys=keys,
        method=str(payload.get("method") or "cached"),
        account_label=str(payload.get("account_label") or account_label),
        data_dir=str(payload.get("data_dir") or str(data_dir)),
        mindgraph_user_id=int(payload.get("mindgraph_user_id") or mindgraph_user_id),
        mindgraph_phone=str(payload.get("mindgraph_phone") or ""),
        saved_at=float(payload.get("saved_at") or 0.0),
    )


def load_wecom_key_cache(
    data_dir: Path,
    *,
    mindgraph_user_id: int,
    account_label: str,
) -> Optional[WeComKeyCacheRecord]:
    """Load and validate cached keys for the current user/account, if present."""
    record = _read_cache_payload(
        data_dir,
        mindgraph_user_id=mindgraph_user_id,
        account_label=account_label,
    )
    if record is None:
        return None
    valid = filter_valid_wecom_keys(data_dir, record.keys)
    if not validate_cached_keys(data_dir, valid):
        log_wecom(
            f"wecom key cache stale user={mindgraph_user_id} keys={len(record.keys)}",
            level="WARN",
        )
        clear_wecom_key_cache(
            mindgraph_user_id=mindgraph_user_id,
            account_label=account_label,
            data_dir=data_dir,
        )
        return None
    log_wecom(f"wecom key cache hit user={mindgraph_user_id} keys={len(valid)}")
    return WeComKeyCacheRecord(
        keys=valid,
        method=record.method,
        account_label=record.account_label,
        data_dir=record.data_dir,
        mindgraph_user_id=record.mindgraph_user_id,
        mindgraph_phone=record.mindgraph_phone,
        saved_at=record.saved_at,
    )


def save_wecom_key_cache(
    data_dir: Path,
    *,
    keys: Dict[str, str],
    method: str,
    mindgraph_user_id: int,
    mindgraph_phone: str,
    account_label: str,
) -> None:
    """Persist validated DB keys for reuse on later app launches."""
    if not keys or not dpapi_available():
        return
    cache_key = build_cache_key(
        mindgraph_user_id=mindgraph_user_id,
        account_label=account_label,
        data_dir=data_dir,
    )
    WECOM_KEYS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _CACHE_VERSION,
        "keys": keys,
        "method": method,
        "account_label": account_label,
        "data_dir": str(data_dir.resolve()),
        "mindgraph_user_id": mindgraph_user_id,
        "mindgraph_phone": mindgraph_phone,
        "saved_at": time.time(),
    }
    blob = protect_bytes(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    path = cache_file_path(cache_key)
    path.write_bytes(blob)
    log_wecom(f"wecom key cache saved user={mindgraph_user_id} keys={len(keys)} path={path}")


def clear_wecom_key_cache(
    *,
    mindgraph_user_id: int,
    account_label: str,
    data_dir: Path,
) -> None:
    """Remove cached keys for one MindGraph user and WeCom account."""
    path = cache_file_path(
        build_cache_key(
            mindgraph_user_id=mindgraph_user_id,
            account_label=account_label,
            data_dir=data_dir,
        )
    )
    if path.is_file():
        path.unlink()
        log_wecom(f"wecom key cache cleared path={path}")


class WeComIncrementalKeyStore:
    """Merge per-database keys into DPAPI cache as each salt is discovered."""

    def __init__(self, data_dir: Path, context: WeComKeyPersistContext) -> None:
        self._data_dir = data_dir
        self._context = context
        record = _read_cache_payload(
            data_dir,
            mindgraph_user_id=context.mindgraph_user_id,
            account_label=context.account_label,
        )
        cached = record.keys if record is not None else {}
        self._rel_keys = filter_valid_wecom_keys(data_dir, cached)

    def seed_key_map(
        self,
        db_files: List[DbFileEntry],
        key_map: Dict[str, str],
        remaining_salts: Set[str],
    ) -> int:
        """Apply cached rel-path keys to the in-memory salt map."""
        seeded = 0
        for rel, _path, _size, salt_hex, page1 in db_files:
            if salt_hex not in remaining_salts:
                continue
            hex_key = self._rel_keys.get(rel)
            if hex_key is None:
                continue
            try:
                raw_key = bytes.fromhex(hex_key)
            except ValueError:
                continue
            if verify_wxsqlite3_aes128_key(raw_key, page1):
                key_map[salt_hex] = hex_key
                remaining_salts.discard(salt_hex)
                seeded += 1
        return seeded

    def on_salt_found(
        self,
        salt_hex: str,
        key_hex: str,
        salt_map: Dict[str, List[str]],
    ) -> None:
        """Persist one newly discovered salt/key for all databases sharing that salt."""
        changed = False
        for rel in salt_map.get(salt_hex, []):
            if self._rel_keys.get(rel) == key_hex:
                continue
            self._rel_keys[rel] = key_hex
            changed = True
        if changed:
            self._flush()

    def _flush(self) -> None:
        save_wecom_key_cache(
            self._data_dir,
            keys=self._rel_keys,
            method=self._context.method,
            mindgraph_user_id=self._context.mindgraph_user_id,
            mindgraph_phone=self._context.mindgraph_phone,
            account_label=self._context.account_label,
        )
        log_wecom(f"wecom key cache incremental keys={len(self._rel_keys)}")

    @property
    def rel_keys(self) -> Dict[str, str]:
        """Latest merged rel-path → hex-key mapping."""
        return dict(self._rel_keys)

    @property
    def cached_count(self) -> int:
        """Number of validated keys loaded from disk at startup."""
        return len(self._rel_keys)
