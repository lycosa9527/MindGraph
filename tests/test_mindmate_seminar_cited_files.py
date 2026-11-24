"""Cited seminar files become prompt text and Dify uploads."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from docx import Document

from clients.dify import DifyFile
from services.features.mindmate_seminar.background_files import SeminarDownload
from services.features.mindmate_seminar.cited_files import (
    CitedSeminarFile,
    cited_files_prompt_excerpt,
    extract_cited_file_text,
    load_cited_seminar_files,
    upload_cited_files_to_dify,
)


def _docx_bytes(tmp_path: Path, paragraph: str) -> bytes:
    path = tmp_path / "notes.docx"
    document = Document()
    document.add_paragraph(paragraph)
    document.save(str(path))
    return path.read_bytes()


def test_extract_cited_file_text_reads_docx_body(tmp_path: Path) -> None:
    """Word citations yield the document body, not only the filename."""
    body = _docx_bytes(tmp_path, "家校协同德育要把红色课文里的冲突点做成课堂问题")
    item = CitedSeminarFile(
        file_id="11111111-1111-1111-1111-111111111111",
        filename="小学红色课文家校协同德育实施策略研究.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        body=body,
        disk_path=None,
    )
    text = extract_cited_file_text(item)
    assert "家校协同德育要把红色课文里的冲突点做成课堂问题" in text
    excerpt = cited_files_prompt_excerpt([item])
    assert "小学红色课文家校协同德育实施策略研究.docx" in excerpt
    assert "冲突点做成课堂问题" in excerpt


def test_cited_files_prompt_excerpt_skips_images() -> None:
    """Pictures stay on the Dify upload path; they do not invent prompt text."""
    item = CitedSeminarFile(
        file_id="22222222-2222-2222-2222-222222222222",
        filename="photo.png",
        content_type="image/png",
        body=b"\x89PNG",
        disk_path=None,
    )
    assert extract_cited_file_text(item) == ""
    assert cited_files_prompt_excerpt([item]) == ""


def test_cited_files_prompt_excerpt_reads_plain_text() -> None:
    """txt citations decode as UTF-8."""
    item = CitedSeminarFile(
        file_id="33333333-3333-3333-3333-333333333333",
        filename="notes.txt",
        content_type="text/plain",
        body="换位思考可以写进课堂评价。".encode("utf-8"),
        disk_path=None,
    )
    excerpt = cited_files_prompt_excerpt([item])
    assert "换位思考可以写进课堂评价。" in excerpt


@pytest.mark.asyncio
async def test_load_cited_seminar_files_skips_missing_and_duplicates() -> None:
    """Only unique files that resolve on this session are loaded."""
    download = SeminarDownload(
        content_type="text/plain",
        filename="notes.txt",
        body="hello".encode("utf-8"),
    )
    missing_id = "11111111-1111-1111-1111-111111111111"
    found_id = "22222222-2222-2222-2222-222222222222"

    async def _resolve(_session_id: str, file_id: str) -> SeminarDownload | None:
        if file_id == found_id:
            return download
        return None

    with patch(
        "services.features.mindmate_seminar.cited_files.resolve_background_download",
        side_effect=_resolve,
    ):
        loaded = await load_cited_seminar_files(
            "sess-1",
            [missing_id, found_id, found_id],
        )
    assert len(loaded) == 1
    assert loaded[0].file_id == found_id
    assert loaded[0].body == b"hello"


@pytest.mark.asyncio
async def test_upload_cited_files_to_dify_builds_local_file_handles() -> None:
    """Successful Dify uploads become chat-messages file parts."""
    client = MagicMock()
    client.upload_file = AsyncMock(return_value={"id": "up-9"})
    item = CitedSeminarFile(
        file_id="44444444-4444-4444-4444-444444444444",
        filename="notes.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        body=b"PK fake-docx",
        disk_path=None,
    )
    uploaded = await upload_cited_files_to_dify(client, "ci_mindmate_seminar_1_sess-1", [item])
    assert uploaded == [
        DifyFile(type="document", transfer_method="local_file", upload_file_id="up-9"),
    ]
    client.upload_file.assert_awaited_once()
