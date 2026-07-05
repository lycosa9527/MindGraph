"""Tests for DingTalk unlock cache helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from file_reader.dingtalk.discovery import DingTalkAccountCandidate
from file_reader.dingtalk.key_store import (
    build_unlock_cache_key,
    load_dingtalk_unlock_cache,
    unlock_cache_file_path,
)


def _account(tmp_path: Path) -> DingTalkAccountCandidate:
    data_dir = tmp_path / "5523c1a1639fc6261770_v3"
    db_path = data_dir / "DBFiles" / "dingtalk.db"
    db_path.parent.mkdir(parents=True)
    db_path.write_bytes(b"encrypted")
    return DingTalkAccountCandidate(
        data_dir=data_dir,
        folder_id="5523c1a1639fc6261770",
        version="v3",
        db_path=db_path,
        user_config_path=data_dir / "user_config",
        db_mtime=db_path.stat().st_mtime,
    )


def test_build_unlock_cache_key_separates_accounts_and_users(tmp_path: Path) -> None:
    """Unlock cache keys differ by user id, folder id, and data directory."""
    account = _account(tmp_path)
    other_dir = tmp_path / "other_v3"
    other_dir.mkdir()
    first = build_unlock_cache_key(
        mindgraph_user_id=1,
        account_folder_id=account.folder_id,
        data_dir=account.data_dir,
    )
    assert first == build_unlock_cache_key(
        mindgraph_user_id=1,
        account_folder_id=account.folder_id,
        data_dir=account.data_dir,
    )
    assert (
        build_unlock_cache_key(
            mindgraph_user_id=2,
            account_folder_id=account.folder_id,
            data_dir=account.data_dir,
        )
        != first
    )
    assert (
        build_unlock_cache_key(
            mindgraph_user_id=1,
            account_folder_id="other",
            data_dir=other_dir,
        )
        != first
    )


def test_load_dingtalk_unlock_cache_clears_stale_mtime(tmp_path: Path) -> None:
    """Stale db_mtime in unlock cache triggers load failure and file removal."""
    account = _account(tmp_path)
    cache_key = build_unlock_cache_key(
        mindgraph_user_id=9,
        account_folder_id=account.folder_id,
        data_dir=account.data_dir,
    )
    cache_path = unlock_cache_file_path(cache_key)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "storage_version": "v3",
        "key_uid": "1770236698",
        "salt_hex": "abc",
        "db_mtime": account.db_mtime + 999.0,
        "account_folder_id": account.folder_id,
        "data_dir": str(account.data_dir),
        "mindgraph_user_id": 9,
        "mindgraph_phone": "",
        "saved_at": 1.0,
    }
    with (
        patch("file_reader.dingtalk.key_store.dpapi_available", return_value=True),
        patch(
            "file_reader.dingtalk.key_store.unprotect_bytes",
            return_value=json.dumps(payload).encode(),
        ),
    ):
        cache_path.write_bytes(b"stub")
        record = load_dingtalk_unlock_cache(
            account,
            mindgraph_user_id=9,
            account_folder_id=account.folder_id,
        )
    assert record is None
    assert not cache_path.is_file()
