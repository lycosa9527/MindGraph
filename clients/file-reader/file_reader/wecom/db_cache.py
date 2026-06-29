"""Decrypt and cache plain WeCom SQLite databases."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Dict, Optional

from file_reader.settings import SETTINGS_DIR
from file_reader.wecom.crypto import (
    WeComCryptoError,
    copy_encrypted_db,
    decrypt_wxwork_database,
    is_plain_sqlite_page,
    is_wxsqlite3_aes128_page1,
    verify_wxsqlite3_aes128_key,
)
from file_reader.wecom.debug_log import log_wecom
from file_reader.wecom.discovery import WeComDataRoot, collect_db_files, is_chat_db_rel, is_session_db_rel

_CACHE_ROOT = SETTINGS_DIR / "wecom-cache"


class WeComDbCache:
    """Copy + decrypt WeCom databases once per account snapshot."""

    def __init__(self, account: WeComDataRoot, keys: Dict[str, str]) -> None:
        self._account = account
        self._keys = keys
        self._cache_root = _cache_root_for(account)

    @property
    def cache_root(self) -> Path:
        """Directory holding decrypted database copies."""
        return self._cache_root

    def ensure_chat_dbs(self) -> Path:
        """Decrypt only session/user/message DBs needed to list conversations."""
        return self._ensure_dbs(chat_only=True)

    def ensure_plain_dbs(self) -> Path:
        """Return cache root with all decryptable databases."""
        return self._ensure_dbs(chat_only=False)

    def _ensure_dbs(self, *, chat_only: bool) -> Path:
        stamp_path = self._cache_root / ".stamp"
        scope = "chat" if chat_only else "all"
        current_stamp = _account_stamp(self._account, self._keys, scope=scope)
        if stamp_path.is_file():
            try:
                saved = stamp_path.read_text(encoding="utf-8").strip()
            except OSError:
                saved = ""
            if saved == current_stamp and _has_session_db(self._cache_root):
                return self._cache_root
        if self._cache_root.exists():
            shutil.rmtree(self._cache_root, ignore_errors=True)
        self._cache_root.mkdir(parents=True, exist_ok=True)
        temp_dir = self._cache_root / "_encrypt_copy"
        decrypted = 0
        for rel, source, _size, _salt, page1 in collect_db_files(self._account.data_dir):
            if chat_only and not is_chat_db_rel(rel):
                continue
            out_path = self._cache_root / rel.replace("/", "\\")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if is_plain_sqlite_page(page1):
                shutil.copy2(source, out_path)
                continue
            if not is_wxsqlite3_aes128_page1(page1):
                continue
            hex_key = self._keys.get(rel)
            if hex_key is None:
                if is_session_db_rel(rel):
                    raise WeComCryptoError(f"missing key for {rel}")
                log_wecom(f"skip decrypt missing key rel={rel}", level="WARN")
                continue
            raw_key = bytes.fromhex(hex_key)
            if not verify_wxsqlite3_aes128_key(raw_key, page1):
                raise WeComCryptoError(f"invalid key for {rel}")
            log_wecom(f"decrypt rel={rel}")
            copied = copy_encrypted_db(source, temp_dir / rel.replace("/", "_"))
            decrypt_wxwork_database(copied, out_path, raw_key)
            decrypted += 1
        shutil.rmtree(temp_dir, ignore_errors=True)
        stamp_path.write_text(current_stamp, encoding="utf-8")
        log_wecom(f"decrypt done scope={scope} files={decrypted}")
        return self._cache_root

    def plain_path(self, rel: str) -> Optional[Path]:
        """Return a cached decrypted database path when present."""
        path = self._cache_root / rel.replace("/", "\\")
        return path if path.is_file() else None


def _cache_root_for(account: WeComDataRoot) -> Path:
    key = hashlib.sha256(str(account.data_dir.resolve()).encode("utf-8")).hexdigest()[:16]
    path = _CACHE_ROOT / key
    path.mkdir(parents=True, exist_ok=True)
    return path


def _account_stamp(account: WeComDataRoot, keys: Dict[str, str], *, scope: str) -> str:
    digest = hashlib.sha256()
    digest.update(str(account.data_dir.resolve()).encode("utf-8"))
    digest.update(scope.encode("ascii"))
    for rel in sorted(keys.keys()):
        if scope == "chat" and not is_chat_db_rel(rel):
            continue
        digest.update(rel.encode("utf-8"))
        digest.update(keys[rel].encode("ascii"))
        source = account.data_dir / rel.replace("/", "\\")
        if source.is_file():
            digest.update(str(source.stat().st_mtime).encode("ascii"))
    return digest.hexdigest()


def _has_session_db(cache_root: Path) -> bool:
    candidates = (
        cache_root / "session" / "session.db",
        cache_root / "session.db",
    )
    return any(path.is_file() for path in candidates)
