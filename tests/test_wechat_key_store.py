"""Unit tests for WeChat key cache helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from file_reader.wechat.key_store import (
    WeChatKeyCacheRecord,
    build_cache_key,
    load_wechat_key_cache,
    validate_cached_keys,
)
from file_reader.wechat.wcdb import PAGE_SZ


def test_build_cache_key_stable() -> None:
    account = Path("C:/Users/demo/xwechat_files/user_ab12")
    first = build_cache_key(mindgraph_user_id=42, wxid="user", account_dir=account)
    second = build_cache_key(mindgraph_user_id=42, wxid="user", account_dir=account)
    assert first == second
    different_user = build_cache_key(mindgraph_user_id=99, wxid="user", account_dir=account)
    assert different_user != first


def test_validate_cached_keys_rejects_garbage(tmp_path: Path) -> None:
    db_dir = tmp_path / "db_storage"
    session_dir = db_dir / "session"
    session_dir.mkdir(parents=True)
    db_path = session_dir / "session.db"
    page1 = b"\x00" * PAGE_SZ
    db_path.write_bytes(page1)
    keys = {"session/session.db": "00" * 64}
    assert validate_cached_keys(db_dir, keys) is False


def test_validate_cached_keys_requires_full_coverage(tmp_path: Path) -> None:
    db_dir = tmp_path / "db_storage"
    session_dir = db_dir / "session"
    session_dir.mkdir(parents=True)
    db_path = session_dir / "session.db"
    db_path.write_bytes(b"\x00" * PAGE_SZ)
    assert validate_cached_keys(db_dir, {}) is False


def test_load_wechat_key_cache_rejects_version_mismatch(tmp_path: Path) -> None:
    account_dir = tmp_path / "account"
    db_dir = account_dir / "db_storage"
    session_dir = db_dir / "session"
    session_dir.mkdir(parents=True)
    db_path = session_dir / "session.db"
    page1 = b"\x00" * PAGE_SZ
    db_path.write_bytes(page1)
    keys = {"session/session.db": "00" * 32}
    payload = {
        "version": 1,
        "keys": keys,
        "method": "cached",
        "crypto_variant": "v4.1",
        "wxid": "demo_user",
        "account_dir": str(account_dir),
        "mindgraph_user_id": 7,
        "mindgraph_phone": "",
        "weixin_version": "4.1.10.31",
        "saved_at": 1.0,
    }
    cache_path = tmp_path / "cache.bin"
    with (
        patch("file_reader.wechat.key_store.dpapi_available", return_value=True),
        patch(
            "file_reader.wechat.key_store.cache_file_path",
            return_value=cache_path,
        ),
        patch("file_reader.wechat.key_store.unprotect_bytes", return_value=json.dumps(payload).encode()),
        patch(
            "file_reader.wechat.key_store.validate_cached_keys",
            return_value=True,
        ),
        patch(
            "file_reader.wechat.key_store.clear_wechat_key_cache",
        ) as mock_clear,
    ):
        cache_path.write_bytes(b"stub")
        record = load_wechat_key_cache(
            account_dir,
            db_dir,
            mindgraph_user_id=7,
            wxid="demo_user",
            current_weixin_version="4.1.10.53",
        )
    assert record is None
    mock_clear.assert_called_once()


def test_load_wechat_key_cache_accepts_matching_version(tmp_path: Path) -> None:
    account_dir = tmp_path / "account"
    db_dir = account_dir / "db_storage"
    session_dir = db_dir / "session"
    session_dir.mkdir(parents=True)
    db_path = session_dir / "session.db"
    page1 = b"\x00" * PAGE_SZ
    db_path.write_bytes(page1)
    keys = {"session/session.db": "00" * 32}
    payload = {
        "version": 1,
        "keys": keys,
        "method": "cached",
        "crypto_variant": "v4.1",
        "wxid": "demo_user",
        "account_dir": str(account_dir),
        "mindgraph_user_id": 7,
        "mindgraph_phone": "",
        "weixin_version": "4.1.10.53",
        "saved_at": 1.0,
    }
    cache_path = tmp_path / "cache.bin"
    with (
        patch("file_reader.wechat.key_store.dpapi_available", return_value=True),
        patch(
            "file_reader.wechat.key_store.cache_file_path",
            return_value=cache_path,
        ),
        patch("file_reader.wechat.key_store.unprotect_bytes", return_value=json.dumps(payload).encode()),
        patch(
            "file_reader.wechat.key_store.validate_cached_keys",
            return_value=True,
        ),
    ):
        cache_path.write_bytes(b"stub")
        record = load_wechat_key_cache(
            account_dir,
            db_dir,
            mindgraph_user_id=7,
            wxid="demo_user",
            current_weixin_version="4.1.10.53",
        )
    assert isinstance(record, WeChatKeyCacheRecord)
    assert record.weixin_version == "4.1.10.53"
