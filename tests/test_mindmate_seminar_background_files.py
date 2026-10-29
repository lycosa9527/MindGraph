"""Background-file names stay on an allow-list of documents and images."""

from pathlib import Path
from unittest.mock import patch

import pytest

from services.features.mindmate_seminar.background_files import (
    background_content_type,
    local_seminar_attachment,
    safe_background_filename,
    store_background_bytes,
)
from services.features.mindmate_seminar.message_files import strip_seminar_message_file_tokens
from services.features.mindmate_seminar.seminar_file_storage import (
    delete_seminar_bytes_sync,
    mirror_local_seminar_file_sync,
    put_seminar_bytes_sync,
    read_seminar_bytes_sync,
)


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
    """Seminar resources land on local disk when COS is off."""
    with (
        patch(
            "services.features.mindmate_seminar.background_files.STATIC_ROOT",
            tmp_path,
        ),
        patch(
            "services.features.mindmate_seminar.background_files.build_logical_key",
            return_value="2026/10/local_notes.txt",
        ),
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
            return_value=False,
        ),
    ):
        key = await store_background_bytes("notes.txt", b"hello", "text/plain")
    assert key == "2026/10/local_notes.txt"
    assert (tmp_path / "2026/10/local_notes.txt").read_bytes() == b"hello"


def test_cos_put_skips_local_disk(tmp_path: Path) -> None:
    """COS uploads do not leave the seminar file on the app server."""
    with (
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
            return_value=True,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.upload_bytes",
            return_value=True,
        ) as upload,
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.full_seminar_cos_key",
            return_value="dev/mindmate/2026/10/ab_notes.txt",
        ),
    ):
        stored = put_seminar_bytes_sync(
            "2026/10/ab_notes.txt",
            b"hello",
            "text/plain",
            tmp_path,
        )
    assert stored == "2026/10/ab_notes.txt"
    upload.assert_called_once()
    assert upload.call_args.args[0] == b"hello"
    assert upload.call_args.args[1] == "dev/mindmate/2026/10/ab_notes.txt"
    assert not list(tmp_path.rglob("*"))


def test_cos_put_raises_when_upload_fails(tmp_path: Path) -> None:
    """A COS failure must not leave a local file the other hosts cannot see."""
    with (
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
            return_value=True,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.upload_bytes",
            return_value=False,
        ),
        pytest.raises(ValueError, match="upload_failed"),
    ):
        put_seminar_bytes_sync("2026/10/ab_notes.txt", b"x", "text/plain", tmp_path)
    assert not list(tmp_path.rglob("*"))


def test_mirror_uploads_a_disk_only_file(tmp_path: Path) -> None:
    """A file saved before COS is copied up the first time it is opened."""
    stored = tmp_path / "2026/10/ab_notes.txt"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"hello")
    with (
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
            return_value=True,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.object_exists",
            return_value=False,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.full_seminar_cos_key",
            return_value="dev/mindmate/2026/10/ab_notes.txt",
        ),
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.upload_bytes",
            return_value=True,
        ) as upload,
    ):
        mirror_local_seminar_file_sync("2026/10/ab_notes.txt", stored, content_type="text/plain")
    upload.assert_called_once()
    assert upload.call_args.args[0] == b"hello"
    assert stored.read_bytes() == b"hello"


def test_mirror_skips_when_cos_already_has_the_object(tmp_path: Path) -> None:
    """Opening a file that is already on COS does not upload it again."""
    stored = tmp_path / "notes.txt"
    stored.write_bytes(b"hello")
    with (
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
            return_value=True,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.object_exists",
            return_value=True,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.full_seminar_cos_key",
            return_value="dev/mindmate/notes.txt",
        ),
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.upload_bytes",
        ) as upload,
    ):
        mirror_local_seminar_file_sync("notes.txt", stored, content_type="text/plain")
    upload.assert_not_called()


def test_cos_read_returns_object_bytes() -> None:
    """Downloads proxy COS bytes so the room can preview them with fetch()."""
    with (
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
            return_value=True,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.get_object_bytes",
            return_value=b"png",
        ) as fetch,
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.full_seminar_cos_key",
            return_value="dev/mindmate/2026/10/ab_photo.png",
        ),
    ):
        body = read_seminar_bytes_sync("2026/10/ab_photo.png", max_bytes=100)
    assert body == b"png"
    fetch.assert_called_once()


def test_delete_removes_local_copy_and_cos_objects(tmp_path: Path) -> None:
    """Delete drops the local file, its preview PDF, and both COS objects."""
    stored = "2026/10/ab_notes.docx"
    target = tmp_path / stored
    target.parent.mkdir(parents=True)
    target.write_bytes(b"doc")
    preview = target.with_name(f"{target.name}.preview.pdf")
    preview.write_bytes(b"pdf")
    with (
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.cos_seminar_enabled",
            return_value=True,
        ),
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.full_seminar_cos_key",
            side_effect=lambda key: f"dev/mindmate/{key}",
        ),
        patch(
            "services.features.mindmate_seminar.seminar_file_storage.delete_object",
        ) as remove,
    ):
        delete_seminar_bytes_sync(stored, tmp_path)
    assert not target.exists()
    assert not preview.exists()
    assert remove.call_count == 2


def test_local_seminar_attachment_ignores_cos_when_disk_has_the_file(tmp_path: Path) -> None:
    """Image preview reads the local PNG even when workshop COS would presign."""
    stored = "2026/10/abc_photo.png"
    target = tmp_path / stored
    target.parent.mkdir(parents=True)
    target.write_bytes(b"\x89PNG")
    with patch(
        "services.features.mindmate_seminar.background_files.STATIC_ROOT",
        tmp_path,
    ):
        found = local_seminar_attachment(stored, "image/png", "计算机网络的分类.png")
    assert found is not None
    assert found.disk_path == target
    assert found.redirect_url is None
