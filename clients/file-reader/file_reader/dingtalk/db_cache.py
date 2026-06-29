"""Decrypt and cache plain DingTalk SQLite databases."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Optional

from file_reader.dingtalk.crypto import (
    DingTalkCryptoError,
    copy_encrypted_db,
    decrypt_database_file,
)
from file_reader.dingtalk.discovery import DingTalkAccountCandidate, read_v3_salt, resolve_key_uid
from file_reader.dingtalk.key_store import (
    DingTalkUnlockPersistContext,
    clear_dingtalk_unlock_cache,
    load_dingtalk_unlock_cache,
    save_dingtalk_unlock_cache,
)
from file_reader.settings import SETTINGS_DIR

_CACHE_ROOT = SETTINGS_DIR / "dingtalk-cache"


class DingTalkDbCache:
    """Copy + decrypt ``dingtalk.db`` once per account snapshot."""

    def __init__(
        self,
        account: DingTalkAccountCandidate,
        *,
        persist: Optional[DingTalkUnlockPersistContext] = None,
    ) -> None:
        self._account = account
        self._persist = persist
        self._plain_path = _cache_root_for(account) / "dingtalk.db"

    @property
    def plain_db_path(self) -> Path:
        """Path to the cached decrypted ``dingtalk.db``."""
        return self._plain_path

    def ensure_plain_db(self) -> Path:
        """Return path to decrypted DB, rebuilding when the encrypted file changed."""
        encrypted_mtime = self._account.db_path.stat().st_mtime
        stamp_path = self._plain_path.with_suffix(".mtime")
        if self._plain_path.is_file() and stamp_path.is_file():
            try:
                saved = float(stamp_path.read_text(encoding="utf-8").strip())
            except ValueError:
                saved = -1.0
            if saved == encrypted_mtime:
                return self._plain_path
        temp_dir = self._plain_path.parent / "_encrypt_copy"
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        copied = copy_encrypted_db(self._account.db_path, temp_dir)
        uid: Optional[str] = None
        salt: Optional[str] = None
        if self._persist is not None:
            cached = load_dingtalk_unlock_cache(
                self._account,
                mindgraph_user_id=self._persist.mindgraph_user_id,
                account_folder_id=self._persist.account_folder_id,
            )
            if cached is not None:
                uid = cached.key_uid
                salt = cached.salt_hex or None
        if uid is None:
            uid, _source = resolve_key_uid(
                self._account,
                log_dir=self._account.data_dir.parent / "log",
            )
            salt = read_v3_salt(self._account.user_config_path) if self._account.version == "v3" else None
        try:
            decrypt_database_file(
                copied,
                self._plain_path,
                uid=uid,
                version=self._account.version,
                salt_hex=salt,
            )
        except DingTalkCryptoError:
            if self._persist is not None:
                clear_dingtalk_unlock_cache(
                    mindgraph_user_id=self._persist.mindgraph_user_id,
                    account_folder_id=self._persist.account_folder_id,
                    data_dir=self._account.data_dir,
                )
            raise
        shutil.rmtree(temp_dir, ignore_errors=True)
        stamp_path.write_text(str(encrypted_mtime), encoding="utf-8")
        if self._persist is not None:
            save_dingtalk_unlock_cache(
                self._account,
                key_uid=uid,
                salt_hex=salt,
                db_mtime=encrypted_mtime,
                context=self._persist,
            )
        return self._plain_path


def _cache_root_for(account: DingTalkAccountCandidate) -> Path:
    key = hashlib.sha256(str(account.data_dir.resolve()).encode("utf-8")).hexdigest()[:16]
    path = _CACHE_ROOT / key
    path.mkdir(parents=True, exist_ok=True)
    return path
