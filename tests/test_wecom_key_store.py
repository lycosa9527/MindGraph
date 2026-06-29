"""Tests for WeCom incremental key cache helpers."""

from __future__ import annotations

from pathlib import Path

from file_reader.wecom.key_store import (
    WeComIncrementalKeyStore,
    build_cache_key,
)


def test_build_cache_key_separates_accounts_and_users() -> None:
    account_a = Path("C:/Users/demo/Documents/WXWork/1688")
    account_b = Path("C:/Users/demo/Documents/WXWork/9999")
    same = build_cache_key(mindgraph_user_id=1, account_label="corp_a", data_dir=account_a)
    assert same == build_cache_key(mindgraph_user_id=1, account_label="corp_a", data_dir=account_a)
    assert build_cache_key(mindgraph_user_id=2, account_label="corp_a", data_dir=account_a) != same
    assert build_cache_key(mindgraph_user_id=1, account_label="corp_b", data_dir=account_a) != same
    assert build_cache_key(mindgraph_user_id=1, account_label="corp_a", data_dir=account_b) != same


class _FakeIncrementalStore:
    """Exercise merge logic without DPAPI or disk writes."""

    def __init__(self) -> None:
        self._rel_keys: dict[str, str] = {}
        self.flush_count = 0

    def on_salt_found(
        self,
        salt_hex: str,
        key_hex: str,
        salt_map: dict[str, list[str]],
    ) -> None:
        WeComIncrementalKeyStore.on_salt_found(self, salt_hex, key_hex, salt_map)

    def _flush(self) -> None:
        self.flush_count += 1

    @property
    def rel_keys(self) -> dict[str, str]:
        return dict(self._rel_keys)


def test_on_salt_found_persists_all_rels_for_salt() -> None:
    store = _FakeIncrementalStore()
    salt_map = {
        "aa" * 16: ["session.db", "message.db", "user.db"],
        "bb" * 16: ["calendar_r7.db"],
    }
    store.on_salt_found("aa" * 16, "cc" * 16, salt_map)
    assert store.rel_keys == {
        "session.db": "cc" * 16,
        "message.db": "cc" * 16,
        "user.db": "cc" * 16,
    }
    assert store.flush_count == 1
    store.on_salt_found("bb" * 16, "dd" * 16, salt_map)
    assert store.rel_keys["calendar_r7.db"] == "dd" * 16
    assert store.flush_count == 2


def test_on_salt_found_skips_duplicate_flush() -> None:
    store = _FakeIncrementalStore()
    salt_map = {"aa" * 16: ["session.db"]}
    store.on_salt_found("aa" * 16, "cc" * 16, salt_map)
    store.on_salt_found("aa" * 16, "cc" * 16, salt_map)
    assert store.flush_count == 1
