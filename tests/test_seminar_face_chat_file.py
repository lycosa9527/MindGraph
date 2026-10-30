"""Face-to-face note bytes stay a single markdown artifact."""

import pytest

from services.features.mindmate_seminar.face_chat_files import (
    face_chat_body,
    face_chat_lock_decision,
    normalize_face_chat_filename,
    parse_face_chat_lock,
)


def test_face_chat_filename_is_markdown() -> None:
    """A bare stem gets .md, and an existing .md name is left alone."""
    assert normalize_face_chat_filename("面聊记录-20261030-1806") == "面聊记录-20261030-1806.md"
    assert normalize_face_chat_filename("notes.md") == "notes.md"
    assert normalize_face_chat_filename("") == "face-chat.md"


def test_face_chat_body_rejects_blank_text() -> None:
    """Whitespace is not a transcript."""
    with pytest.raises(ValueError, match="empty_reply"):
        face_chat_body("   ")


def test_face_chat_body_is_utf8() -> None:
    """The saved bytes are the transcript encoded as UTF-8."""
    assert face_chat_body("说话人1：你好") == "说话人1：你好".encode("utf-8")


def test_face_chat_lock_parse_keeps_file_id() -> None:
    """A lock value is user id, token, and the file id, or absent when junk."""
    assert parse_face_chat_lock("7|token-a|file-1") == (7, "token-a", "file-1")
    assert parse_face_chat_lock(b"7|token-a|") == (7, "token-a", "")
    assert parse_face_chat_lock("not-a-lock") is None
    assert parse_face_chat_lock(None) is None


def test_face_chat_lock_one_recorder() -> None:
    """The same token may refresh. Another teacher or a late refresh is busy."""
    holder = (4, "token-a", "file-1")
    assert face_chat_lock_decision(None, 4, "token-a", refresh=False) == "acquire"
    assert face_chat_lock_decision(None, 4, "token-a", refresh=True) == "busy"
    assert face_chat_lock_decision(holder, 4, "token-a", refresh=False) == "refresh"
    assert face_chat_lock_decision(holder, 4, "token-b", refresh=False) == "busy"
    assert face_chat_lock_decision(holder, 9, "token-a", refresh=True) == "busy"
