"""Tests for WeChat markdown export helpers."""

from __future__ import annotations

from pathlib import Path

from file_reader.chat.messages import (
    ChatMessage,
    export_content_for_upload,
    messages_to_markdown,
    messages_to_payload,
    parse_text_export_file,
    write_export_file,
)
from services.knowledge.chat_transcript_normalizer import normalize_chat_messages


def test_messages_to_markdown_matches_server_normalizer() -> None:
    """Client markdown export matches server chat transcript normalizer."""
    messages = [
        ChatMessage(sender="Alice", text="Hello", timestamp="2026-06-29 10:00"),
        ChatMessage(sender="Bob", text="Hi", timestamp=None),
    ]
    payload = messages_to_payload(messages)
    client_md = messages_to_markdown(messages, "Team chat", "wechat")
    server_md = normalize_chat_messages(payload, "Team chat", "wechat")
    assert client_md.strip() == server_md.strip()


def test_write_export_file_creates_md(tmp_path: Path) -> None:
    """``write_export_file`` writes a markdown file beside the txt path."""
    messages = [ChatMessage(sender="Alice", text="One", timestamp="2026-06-29 10:00")]
    path = tmp_path / "sample.txt"
    count = write_export_file(path, messages, title="Sample", platform="wechat")
    assert count == 1
    md_path = tmp_path / "sample.md"
    assert md_path.is_file()
    saved = md_path.read_text(encoding="utf-8")
    assert saved.startswith("# Sample (wechat)\n\n")
    assert "[2026-06-29 10:00] Alice: One" in saved


def test_parse_markdown_roundtrip(tmp_path: Path) -> None:
    """Exported markdown round-trips through ``parse_text_export_file``."""
    messages = [
        ChatMessage(sender="Alice", text="Hello", timestamp="2026-06-29 10:00"),
        ChatMessage(sender="Bob", text="Hi", timestamp=None),
    ]
    path = tmp_path / "chat.md"
    write_export_file(path, messages, title="Team chat", platform="wechat")
    parsed = parse_text_export_file(path)
    assert len(parsed) == 2
    assert parsed[0].sender == "Alice"
    assert parsed[0].timestamp == "2026-06-29 10:00"
    assert parsed[1].sender == "Bob"


def test_export_content_for_upload_preserves_md(tmp_path: Path) -> None:
    """Upload helper returns existing markdown body unchanged."""
    path = tmp_path / "ready.md"
    body = "# Saved chat (wechat)\n\nAlice: Hello\n"
    path.write_text(body, encoding="utf-8")
    loaded = export_content_for_upload(path, "Other title", "wechat")
    assert loaded == body.strip()
