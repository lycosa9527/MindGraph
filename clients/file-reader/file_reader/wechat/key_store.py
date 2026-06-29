"""Persist extracted WeChat DB keys per MindGraph user and local WeChat account."""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from file_reader.dpapi_store import DpapiError, dpapi_available, protect_bytes, unprotect_bytes
from file_reader.settings import SETTINGS_DIR
from file_reader.wechat.crypto import collect_db_files, verify_enc_key
from file_reader.wechat.debug_log import log_wechat
from file_reader.wechat.version import cached_weixin_version_matches

WECHAT_KEYS_DIR = SETTINGS_DIR / "wechat-keys"
_CACHE_VERSION = 1


@dataclass(frozen=True)
class WeChatKeyCacheRecord:
    """Decrypted WeChat DB keys linked to a MindGraph user and WeChat account."""

    keys: Dict[str, str]
    method: str
    crypto_variant: str
    wxid: str
    account_dir: str
    mindgraph_user_id: int
    mindgraph_phone: str
    weixin_version: str
    saved_at: float


@dataclass(frozen=True)
class WeChatKeyPersistContext:
    """MindGraph user binding for incremental WeChat key persistence."""

    mindgraph_user_id: int
    mindgraph_phone: str
    wxid: str
    method: str = "memory_scan"
    crypto_variant: str = ""
    weixin_version: str = ""


def filter_valid_wechat_keys(db_dir: Path, keys: Dict[str, str]) -> Dict[str, str]:
    """Return cached rel-path keys that still decrypt their on-disk databases."""
    if not keys:
        return {}
    db_files, _salt_to_rels = collect_db_files(db_dir)
    rel_to_page1 = {rel: page1 for rel, _path, _size, _salt, page1 in db_files}
    valid: Dict[str, str] = {}
    for rel, hex_key in keys.items():
        page1 = rel_to_page1.get(rel)
        if page1 is None:
            continue
        try:
            enc_key = bytes.fromhex(hex_key)
        except ValueError:
            continue
        if verify_enc_key(enc_key, page1):
            valid[rel] = hex_key
    return valid


def _slug(value: str, *, max_len: int = 32) -> str:
    cleaned = re.sub(r"[^\w.-]", "_", value.strip())
    return cleaned[:max_len] or "unknown"


def build_cache_key(
    *,
    mindgraph_user_id: int,
    wxid: str,
    account_dir: Path,
) -> str:
    """Stable filename stem for a MindGraph user + WeChat account pair."""
    account_digest = hashlib.sha256(str(account_dir.resolve()).encode()).hexdigest()[:16]
    return f"mg{mindgraph_user_id}_{_slug(wxid)}_{account_digest}"


def cache_file_path(cache_key: str) -> Path:
    """DPAPI-protected cache file for one user/account binding."""
    return WECHAT_KEYS_DIR / f"{cache_key}.dpapi"


def cache_entry_exists(
    *,
    mindgraph_user_id: int,
    wxid: str,
    account_dir: Path,
) -> bool:
    """True when a cache file exists for this MindGraph user and WeChat account."""
    path = cache_file_path(
        build_cache_key(
            mindgraph_user_id=mindgraph_user_id,
            wxid=wxid,
            account_dir=account_dir,
        )
    )
    return path.is_file()


def validate_cached_keys(db_dir: Path, keys: Dict[str, str]) -> bool:
    """True when cached keys still decrypt the current on-disk databases."""
    valid = filter_valid_wechat_keys(db_dir, keys)
    if not valid:
        return False
    db_files, _salt_to_rels = collect_db_files(db_dir)
    if not db_files:
        return False
    return len(valid) >= len(db_files)


def load_wechat_key_cache(
    account_dir: Path,
    db_dir: Path,
    *,
    mindgraph_user_id: int,
    wxid: str,
    current_weixin_version: Optional[str] = None,
) -> Optional[WeChatKeyCacheRecord]:
    """Load and validate cached keys for the current user/account, if present."""
    if not dpapi_available():
        return None
    cache_key = build_cache_key(
        mindgraph_user_id=mindgraph_user_id,
        wxid=wxid,
        account_dir=account_dir,
    )
    path = cache_file_path(cache_key)
    if not path.is_file():
        return None
    try:
        payload = json.loads(unprotect_bytes(path.read_bytes()).decode("utf-8"))
    except (OSError, DpapiError, json.JSONDecodeError, ValueError, UnicodeDecodeError):
        log_wechat(f"wechat key cache unreadable path={path}", level="WARN")
        clear_wechat_key_cache(
            mindgraph_user_id=mindgraph_user_id,
            wxid=wxid,
            account_dir=account_dir,
        )
        return None
    if not isinstance(payload, dict) or payload.get("version") != _CACHE_VERSION:
        return None
    keys_raw = payload.get("keys")
    if not isinstance(keys_raw, dict):
        return None
    keys = {str(rel): str(hex_key) for rel, hex_key in keys_raw.items() if hex_key}
    record = WeChatKeyCacheRecord(
        keys=keys,
        method=str(payload.get("method") or "cached"),
        crypto_variant=str(payload.get("crypto_variant") or ""),
        wxid=str(payload.get("wxid") or wxid),
        account_dir=str(payload.get("account_dir") or str(account_dir)),
        mindgraph_user_id=int(payload.get("mindgraph_user_id") or mindgraph_user_id),
        mindgraph_phone=str(payload.get("mindgraph_phone") or ""),
        weixin_version=str(payload.get("weixin_version") or ""),
        saved_at=float(payload.get("saved_at") or 0.0),
    )
    if current_weixin_version is not None and not cached_weixin_version_matches(
        record.weixin_version,
        current_weixin_version,
    ):
        log_wechat(
            f"wechat key cache version mismatch saved={record.weixin_version!r} "
            f"current={current_weixin_version!r} path={path}",
            level="WARN",
        )
        clear_wechat_key_cache(
            mindgraph_user_id=mindgraph_user_id,
            wxid=wxid,
            account_dir=account_dir,
        )
        return None
    if not validate_cached_keys(db_dir, record.keys):
        log_wechat(
            f"wechat key cache stale path={path} keys={len(record.keys)}",
            level="WARN",
        )
        clear_wechat_key_cache(
            mindgraph_user_id=mindgraph_user_id,
            wxid=wxid,
            account_dir=account_dir,
        )
        return None
    log_wechat(f"wechat key cache hit user={mindgraph_user_id} wxid={wxid} keys={len(record.keys)}")
    return record


def save_wechat_key_cache(
    account_dir: Path,
    *,
    keys: Dict[str, str],
    method: str,
    crypto_variant: str,
    mindgraph_user_id: int,
    mindgraph_phone: str,
    wxid: str,
    weixin_version: str,
) -> None:
    """Persist validated DB keys for reuse on later app launches."""
    if not keys or not dpapi_available():
        return
    cache_key = build_cache_key(
        mindgraph_user_id=mindgraph_user_id,
        wxid=wxid,
        account_dir=account_dir,
    )
    WECHAT_KEYS_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _CACHE_VERSION,
        "keys": keys,
        "method": method,
        "crypto_variant": crypto_variant,
        "wxid": wxid,
        "account_dir": str(account_dir.resolve()),
        "mindgraph_user_id": mindgraph_user_id,
        "mindgraph_phone": mindgraph_phone,
        "weixin_version": weixin_version,
        "saved_at": time.time(),
    }
    blob = protect_bytes(
        json.dumps(payload, separators=(",", ":")).encode("utf-8"),
    )
    path = cache_file_path(cache_key)
    path.write_bytes(blob)
    log_wechat(f"wechat key cache saved user={mindgraph_user_id} wxid={wxid} keys={len(keys)} path={path}")


def clear_wechat_key_cache(
    *,
    mindgraph_user_id: int,
    wxid: str,
    account_dir: Path,
) -> None:
    """Remove cached keys for one MindGraph user and WeChat account."""
    path = cache_file_path(
        build_cache_key(
            mindgraph_user_id=mindgraph_user_id,
            wxid=wxid,
            account_dir=account_dir,
        )
    )
    if path.is_file():
        path.unlink()
        log_wechat(f"wechat key cache cleared path={path}")


class WeChatIncrementalKeyStore:
    """Merge per-database keys into DPAPI cache as each salt is discovered."""

    def __init__(
        self,
        account_dir: Path,
        db_dir: Path,
        context: WeChatKeyPersistContext,
    ) -> None:
        self._account_dir = account_dir
        self._db_dir = db_dir
        self._context = context
        record = _read_cache_payload(
            account_dir,
            mindgraph_user_id=context.mindgraph_user_id,
            wxid=context.wxid,
        )
        cached = record.keys if record is not None else {}
        self._rel_keys = filter_valid_wechat_keys(db_dir, cached)

    def seed_key_map(
        self,
        db_files: List[Tuple[str, Path, int, str, bytes]],
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
                enc_key = bytes.fromhex(hex_key)
            except ValueError:
                continue
            if verify_enc_key(enc_key, page1):
                key_map[salt_hex] = hex_key
                remaining_salts.discard(salt_hex)
                seeded += 1
        return seeded

    def on_salt_found(self, salt_hex: str, key_hex: str, salt_to_rels: Dict[str, List[str]]) -> None:
        """Persist one newly discovered salt/key for all databases sharing that salt."""
        changed = False
        for rel in salt_to_rels.get(salt_hex, []):
            if self._rel_keys.get(rel) == key_hex:
                continue
            self._rel_keys[rel] = key_hex
            changed = True
        if changed:
            self._flush()

    def merge_rel_keys(self, rel_keys: Dict[str, str]) -> None:
        """Persist a batch of rel-path keys (v3/v4.1 single-shot derive)."""
        changed = False
        for rel, key_hex in rel_keys.items():
            if self._rel_keys.get(rel) == key_hex:
                continue
            self._rel_keys[rel] = key_hex
            changed = True
        if changed:
            self._flush()

    def _flush(self) -> None:
        save_wechat_key_cache(
            self._account_dir,
            keys=self._rel_keys,
            method=self._context.method,
            crypto_variant=self._context.crypto_variant,
            mindgraph_user_id=self._context.mindgraph_user_id,
            mindgraph_phone=self._context.mindgraph_phone,
            wxid=self._context.wxid,
            weixin_version=self._context.weixin_version,
        )
        log_wechat(f"wechat key cache incremental keys={len(self._rel_keys)}")

    @property
    def rel_keys(self) -> Dict[str, str]:
        """Latest merged rel-path → hex-key mapping."""
        return dict(self._rel_keys)

    @property
    def cached_count(self) -> int:
        """Number of validated keys loaded from disk at startup."""
        return len(self._rel_keys)


def _read_cache_payload(
    account_dir: Path,
    *,
    mindgraph_user_id: int,
    wxid: str,
) -> Optional[WeChatKeyCacheRecord]:
    if not dpapi_available():
        return None
    cache_key = build_cache_key(
        mindgraph_user_id=mindgraph_user_id,
        wxid=wxid,
        account_dir=account_dir,
    )
    path = cache_file_path(cache_key)
    if not path.is_file():
        return None
    try:
        payload = json.loads(unprotect_bytes(path.read_bytes()).decode("utf-8"))
    except (OSError, DpapiError, json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != _CACHE_VERSION:
        return None
    keys_raw = payload.get("keys")
    if not isinstance(keys_raw, dict):
        return None
    keys = {str(rel): str(hex_key) for rel, hex_key in keys_raw.items() if hex_key}
    return WeChatKeyCacheRecord(
        keys=keys,
        method=str(payload.get("method") or "cached"),
        crypto_variant=str(payload.get("crypto_variant") or ""),
        wxid=str(payload.get("wxid") or wxid),
        account_dir=str(payload.get("account_dir") or str(account_dir)),
        mindgraph_user_id=int(payload.get("mindgraph_user_id") or mindgraph_user_id),
        mindgraph_phone=str(payload.get("mindgraph_phone") or ""),
        weixin_version=str(payload.get("weixin_version") or ""),
        saved_at=float(payload.get("saved_at") or 0.0),
    )
