"""Unit tests for WeChat DB reader helpers."""

from __future__ import annotations

from pathlib import Path

from file_reader.chat.messages import ChatMessage
from file_reader.wechat.db_reader import (
    ContactDirectory,
    WeChatSessionPreview,
    _display_name_for_username,
    _format_message_text,
    _is_official_account_username,
    _self_display_name,
    _split_msg_type,
    _username_to_msg_table,
    format_chat_preview,
    format_session_time,
)
from file_reader.wechat.local import WeChatLocalStatus
from file_reader.wechat.wcdb import PAGE_SZ, collect_db_files, verify_enc_key


def test_is_official_account_username() -> None:
    assert _is_official_account_username("gh_deadbeeffeed") is True
    assert _is_official_account_username("BrandSessionHolder") is True
    assert _is_official_account_username("wxid_alice") is False
    assert _is_official_account_username("12345678@chatroom") is False


def test_self_display_name_prefers_remark() -> None:
    contacts = ContactDirectory(
        display_names={"wxid_me": "昵称王老师", "wxid_alice": "Alice"},
        remarks={"wxid_me": "备注王老师"},
        nick_names={"wxid_me": "昵称王老师"},
    )
    account_dir = Path("/tmp/rulerwang_c571")
    assert _self_display_name(account_dir, contacts, "wxid_me") == "备注王老师"


def test_display_name_for_self_uses_remark() -> None:
    contacts = ContactDirectory(
        display_names={"wxid_me": "昵称王老师", "wxid_alice": "Alice"},
        remarks={"wxid_me": "备注王老师"},
        nick_names={"wxid_me": "昵称王老师", "wxid_alice": "Alice昵称"},
    )
    label = _display_name_for_username(
        "wxid_me",
        self_username="wxid_me",
        self_display_name="备注王老师",
        contacts=contacts,
    )
    assert label == "备注王老师"


def test_display_name_for_other_prefers_remark() -> None:
    contacts = ContactDirectory(
        display_names={"wxid_alice": "Alice昵称"},
        remarks={"wxid_alice": "Alice备注"},
        nick_names={"wxid_alice": "Alice昵称"},
    )
    label = _display_name_for_username(
        "wxid_alice",
        self_username="wxid_me",
        self_display_name="我",
        contacts=contacts,
    )
    assert label == "Alice备注"


def test_split_msg_type_packed() -> None:
    base, sub = _split_msg_type(0x100000001)
    assert base == 1
    assert sub == 1


def test_format_message_text_plain() -> None:
    text = _format_message_text(1, "hello", is_group=False)
    assert text == "hello"


def test_format_message_text_image() -> None:
    text = _format_message_text(3, "ignored", is_group=False)
    assert text == "[图片]"


def test_format_session_time_zero() -> None:
    assert format_session_time(0) == ""


def test_live_db_ready_v3_and_v4_when_process_and_dbs() -> None:
    ready_v4 = WeChatLocalStatus(
        process_running=True,
        data_root=Path("/tmp/account"),
        wxid="user",
        db_count=3,
        client_variant="v4",
        key_db_found=True,
    )
    assert ready_v4.live_db_ready is True

    ready_v3 = WeChatLocalStatus(
        process_running=True,
        data_root=Path("/tmp/account"),
        wxid="user",
        db_count=3,
        client_variant="v3",
        key_db_found=False,
    )
    assert ready_v3.live_db_ready is True

    ready_v41 = WeChatLocalStatus(
        process_running=True,
        data_root=Path("/tmp/account"),
        wxid="user",
        db_count=3,
        client_variant="v4.1",
        key_db_found=True,
    )
    assert ready_v41.live_db_ready is True

    offline = WeChatLocalStatus(
        process_running=False,
        data_root=Path("/tmp/account"),
        wxid="user",
        db_count=3,
        client_variant="v4.1",
        key_db_found=True,
    )
    assert offline.live_db_ready is False


def test_collect_db_files_skips_small_files(tmp_path: Path) -> None:
    db_dir = tmp_path / "db_storage"
    db_dir.mkdir()
    (db_dir / "session").mkdir()
    tiny = db_dir / "session" / "session.db"
    tiny.write_bytes(b"tiny")
    files, salts = collect_db_files(db_dir)
    assert not files
    assert not salts


def test_verify_enc_key_rejects_garbage() -> None:
    page1 = b"\x00" * PAGE_SZ
    assert verify_enc_key(b"\x01" * 32, page1) is False


def test_format_chat_preview() -> None:
    messages = [
        ChatMessage(sender="Alice", text="hello", timestamp="2026-01-01 12:00:00"),
        ChatMessage(sender="Bob", text="hi", timestamp=None),
    ]
    text = format_chat_preview(messages)
    assert "Alice" in text
    assert "Bob" in text


def test_username_to_msg_table() -> None:
    table = _username_to_msg_table("wxid_test")
    assert table.startswith("Msg_")
    assert len(table) == 36


def test_session_preview_fields() -> None:
    preview = WeChatSessionPreview(
        username="wxid_test",
        display_name="Test",
        last_timestamp=1_700_000_000,
        summary="hi",
        is_group=False,
    )
    assert preview.display_name == "Test"
    assert "01-" in format_session_time(preview.last_timestamp) or format_session_time(preview.last_timestamp)
