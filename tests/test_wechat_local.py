"""Unit tests for WeChat v3/v4 local path detection."""

from __future__ import annotations

from pathlib import Path

from file_reader.wechat.local import (
    WeChatLocalStatus,
    _iter_account_dirs,
    _key_db_found,
    _message_db_count,
    detect_wechat_local,
)


def _make_v3_tree(base: Path) -> Path:
    wxid = base / "WeChat Files" / "wxid_testuser"
    (wxid / "Msg" / "Multi").mkdir(parents=True)
    (wxid / "Msg" / "Multi" / "MSG0.db").write_bytes(b"")
    (wxid / "Msg" / "Multi" / "MSG1.db").write_bytes(b"")
    return wxid


def _make_v4_tree(base: Path) -> Path:
    root = base / "xwechat_files"
    account = root / "user_ab12"
    msg_dir = account / "db_storage" / "message"
    msg_dir.mkdir(parents=True)
    (msg_dir / "message_0.db").write_bytes(b"")
    (msg_dir / "message_1.db").write_bytes(b"")
    login = root / "all_users" / "login" / "user"
    login.mkdir(parents=True)
    (login / "key_info.db").write_bytes(b"")
    return account


def test_v3_message_db_count(tmp_path: Path) -> None:
    """v3 layout counts MSG shards under Msg/Multi."""
    wxid = _make_v3_tree(tmp_path)
    count, variant = _message_db_count(wxid)
    assert count == 2
    assert variant == "v3"


def test_v4_message_db_count_and_key(tmp_path: Path) -> None:
    """v4 layout counts message shards and detects key_info.db."""
    account = _make_v4_tree(tmp_path)
    count, variant = _message_db_count(account)
    assert count == 2
    assert variant == "v4"
    root = tmp_path / "xwechat_files"
    assert _key_db_found(root, "user") is True


def test_iter_account_dirs_v3_and_v4(tmp_path: Path) -> None:
    """Account iteration finds v3 wxid dirs and v4 user labels."""
    v3_root = tmp_path / "WeChat Files"
    _make_v3_tree(tmp_path)
    v3_accounts = list(_iter_account_dirs(v3_root))
    assert len(v3_accounts) == 1
    assert v3_accounts[0][1] == "testuser"

    v4_root = tmp_path / "xwechat_files"
    _make_v4_tree(tmp_path)
    v4_accounts = list(_iter_account_dirs(v4_root))
    labels = {label for _path, label in v4_accounts}
    assert "user" in labels


def test_v3_micromsg_db(tmp_path: Path) -> None:
    """MicroMsg.db alone counts as a v3 message database."""
    wxid = tmp_path / "WeChat Files" / "wxid_abc"
    wxid.mkdir(parents=True)
    (wxid / "MicroMsg.db").write_bytes(b"")
    count, variant = _message_db_count(wxid)
    assert count >= 1
    assert variant == "v3"


def test_live_db_ready_v4_without_key_info(tmp_path: Path) -> None:
    """v4 live DB is ready when process runs even without key_info.db."""
    account = _make_v4_tree(tmp_path)
    status = WeChatLocalStatus(
        process_running=True,
        data_root=account,
        wxid="user",
        db_count=2,
        client_variant="v4",
        key_db_found=False,
        key_methods=("v4_xhex", "v4_wx_key_dll"),
    )
    assert status.live_db_ready is True


def test_detect_wechat_local_returns_status() -> None:
    """``detect_wechat_local`` returns a ``WeChatLocalStatus`` instance."""
    status = detect_wechat_local()
    assert isinstance(status, WeChatLocalStatus)
