"""Background-file names stay on an allow-list of documents and images."""

from pathlib import Path
from unittest.mock import patch

import pytest

from services.features.mindmate_collab.background_files import (
    background_content_type,
    local_seminar_attachment,
    safe_background_filename,
    store_background_bytes,
)
from services.features.mindmate_collab.message_files import strip_seminar_message_file_tokens


def test_strip_seminar_message_file_tokens_keeps_typed_text() -> None:
    """Chat attachments stay out of the prompt MindMate reads."""
    raw = "看一下这份讲义\n\n[[sf:11111111-1111-1111-1111-111111111111|notes.pdf]]"
    assert strip_seminar_message_file_tokens(raw) == "看一下这份讲义"


def test_safe_background_filename_drops_directories() -> None:
    """Only the basename is stored, even when the client sends a path."""
    assert safe_background_filename("../lesson/背景.pdf") == "背景.pdf"


def test_background_content_type_accepts_documents_and_images() -> None:
    """Lesson files and pictures are the shared background set."""
    assert background_content_type("notes.pdf") == "application/pdf"
    assert background_content_type("photo.PNG") == "image/png"
    assert background_content_type("voice.webm") == "audio/webm"


def test_background_content_type_rejects_executables() -> None:
    """Anything outside the document and image list is refused."""
    with pytest.raises(ValueError, match="file_type"):
        background_content_type("setup.exe")


@pytest.mark.asyncio
async def test_store_background_bytes_writes_local_disk(tmp_path: Path) -> None:
    """Seminar resources always land under the local static tree."""
    with (
        patch(
            "services.features.mindmate_collab.background_files.STATIC_ROOT",
            tmp_path,
        ),
        patch(
            "services.features.mindmate_collab.background_files.build_logical_key",
            return_value="2026/10/local_notes.txt",
        ),
    ):
        key = await store_background_bytes("notes.txt", b"hello", "text/plain")
    assert key == "2026/10/local_notes.txt"
    assert (tmp_path / "2026/10/local_notes.txt").read_bytes() == b"hello"


def test_local_seminar_attachment_ignores_cos_when_disk_has_the_file(tmp_path: Path) -> None:
    """Image preview reads the local PNG even when workshop COS would presign."""
    stored = "2026/10/abc_photo.png"
    target = tmp_path / stored
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\x89PNG")
    with patch(
        "services.features.mindmate_collab.background_files.STATIC_ROOT",
        tmp_path,
    ):
        found = local_seminar_attachment(stored, "image/png", "计算机网络的分类.png")
    assert found is not None
    assert found.disk_path == target
    assert found.redirect_url is None
