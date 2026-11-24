"""Load seminar chat citations into the MindMate (Dify) turn.

Cited and dropped files ride the chat as ``[[sf:uuid|filename]]`` tokens. The
typed question strips those tokens; this module loads the bytes, extracts
readable text for the prompt, and uploads the files to Dify so document /
vision tools can read them too.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Optional

import pypdf
from pypdf.errors import PdfReadError

from clients.dify import AsyncDifyClient, DifyFile
from services.dify.file_upload_types import (
    dify_chat_file_type,
    dify_upload_content_type,
    dify_upload_max_bytes,
    legacy_doc_upload_detail,
)
from services.features.mindmate_seminar.background_files import (
    DIAGRAM_REF_TYPE,
    resolve_background_download,
)
from services.features.mindmate_seminar.office_text_preview import office_text_preview
from services.utils.error_types import DIFY_API_ERRORS, FILE_IO_ERRORS

logger = logging.getLogger(__name__)

DEFAULT_CITED_FILE_QUERY = "请阅读附件并回答。"
MAX_CITED_FILES = 6
_MAX_CHARS_PER_FILE = 8000
_MAX_CHARS_TOTAL = 16000
_PLAIN_SUFFIXES = frozenset({".txt", ".md"})
_OFFICE_SUFFIXES = frozenset({".docx", ".pptx", ".xlsx"})
_PDF_SUFFIXES = frozenset({".pdf"})
_PDF_ERRORS: tuple[type[BaseException], ...] = FILE_IO_ERRORS + (
    PdfReadError,
    TypeError,
    KeyError,
    IndexError,
)
_TEXT_DECODE_ERRORS: tuple[type[BaseException], ...] = (UnicodeDecodeError, LookupError)


@dataclass(frozen=True)
class CitedSeminarFile:
    """One seminar background file loaded for a MindMate turn."""

    file_id: str
    filename: str
    content_type: str
    body: bytes
    disk_path: Optional[Path]


@dataclass(frozen=True)
class CitedFilesBind:
    """Prompt excerpt plus Dify ``files`` for one assistant turn."""

    excerpt: str
    dify_files: list[DifyFile]


def _decode_plain_text(body: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return body.decode(encoding).strip()
        except _TEXT_DECODE_ERRORS:
            continue
    return body.decode("utf-8", errors="replace").strip()


def _pdf_text(body: bytes) -> str:
    try:
        reader = pypdf.PdfReader(BytesIO(body))
    except _PDF_ERRORS:
        return ""
    parts: list[str] = []
    try:
        pages = list(reader.pages)
    except _PDF_ERRORS:
        return ""
    for page in pages:
        try:
            text = (page.extract_text() or "").strip()
        except _PDF_ERRORS:
            continue
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _office_text(filename: str, body: bytes, disk_path: Optional[Path]) -> str:
    if disk_path is not None:
        return office_text_preview(disk_path, filename)
    suffix = Path(filename).suffix.lower() or ".docx"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / Path(filename).name
        if path.suffix.lower() != suffix:
            path = Path(tmp) / f"cited{suffix}"
        path.write_bytes(body)
        return office_text_preview(path, filename)


def extract_cited_file_text(item: CitedSeminarFile) -> str:
    """Return markdown-ish text for one cited file, or empty when it is binary."""
    suffix = Path(item.filename).suffix.lower()
    if suffix in _PLAIN_SUFFIXES:
        return _decode_plain_text(item.body)
    if suffix in _OFFICE_SUFFIXES:
        try:
            return _office_text(item.filename, item.body, item.disk_path)
        except FILE_IO_ERRORS:
            return ""
    if suffix in _PDF_SUFFIXES:
        return _pdf_text(item.body)
    return ""


def cited_files_prompt_excerpt(files: list[CitedSeminarFile]) -> str:
    """Labeled document text appended to the Dify query."""
    blocks: list[str] = []
    remaining = _MAX_CHARS_TOTAL
    for item in files:
        if remaining <= 0:
            break
        text = extract_cited_file_text(item).strip()
        if not text:
            continue
        cap = min(_MAX_CHARS_PER_FILE, remaining)
        clipped = text if len(text) <= cap else f"{text[:cap].rstrip()}\n…"
        blocks.append(f"【附件：{item.filename}】\n{clipped}")
        remaining -= len(clipped)
    return "\n\n".join(blocks)


async def load_cited_seminar_files(session_id: str, file_ids: list[str]) -> list[CitedSeminarFile]:
    """Resolve unique cited ids that belong to this seminar."""
    loaded: list[CitedSeminarFile] = []
    seen: set[str] = set()
    for file_id in file_ids:
        if not file_id or file_id in seen or len(loaded) >= MAX_CITED_FILES:
            continue
        seen.add(file_id)
        download = await resolve_background_download(session_id, file_id)
        if download is None:
            logger.warning("[MindmateSeminar] cited file missing session=%s file=%s", session_id, file_id)
            continue
        if download.content_type == DIAGRAM_REF_TYPE:
            continue
        body = download.body
        if body is None and download.disk_path is not None:
            try:
                body = await asyncio.to_thread(download.disk_path.read_bytes)
            except FILE_IO_ERRORS as exc:
                logger.warning(
                    "[MindmateSeminar] cited file read failed session=%s file=%s err=%s",
                    session_id,
                    file_id,
                    type(exc).__name__,
                )
                continue
        if not body:
            continue
        loaded.append(
            CitedSeminarFile(
                file_id=file_id,
                filename=download.filename,
                content_type=download.content_type,
                body=body,
                disk_path=download.disk_path,
            )
        )
    return loaded


async def upload_cited_files_to_dify(
    client: AsyncDifyClient,
    dify_user: str,
    files: list[CitedSeminarFile],
) -> list[DifyFile]:
    """Upload cited bytes to Dify. Failures skip that file and keep the turn going."""
    uploaded: list[DifyFile] = []
    for item in files:
        if legacy_doc_upload_detail(item.filename, item.body) is not None:
            continue
        if len(item.body) > dify_upload_max_bytes(item.filename):
            logger.warning(
                "[MindmateSeminar] cited file too large for Dify file=%s bytes=%s",
                item.filename,
                len(item.body),
            )
            continue
        mime = dify_upload_content_type(item.filename, item.content_type)
        try:
            result = await client.upload_file(
                dify_user,
                file_bytes=item.body,
                filename=item.filename,
                content_type=mime,
            )
        except DIFY_API_ERRORS as exc:
            logger.warning(
                "[MindmateSeminar] Dify upload failed file=%s err=%s",
                item.filename,
                type(exc).__name__,
            )
            continue
        file_id = result.get("id") if isinstance(result, dict) else None
        if not isinstance(file_id, str) or not file_id.strip():
            logger.warning("[MindmateSeminar] Dify upload missing id file=%s", item.filename)
            continue
        uploaded.append(
            DifyFile(
                type=dify_chat_file_type(item.filename, mime),
                transfer_method="local_file",
                upload_file_id=file_id.strip(),
            )
        )
    return uploaded


async def bind_cited_files_for_dify(
    *,
    session_id: str,
    file_ids: list[str],
    client: AsyncDifyClient,
    dify_user: str,
) -> CitedFilesBind:
    """Load cited seminar files, extract prompt text, and upload them to Dify."""
    if not file_ids:
        return CitedFilesBind("", [])
    loaded = await load_cited_seminar_files(session_id, file_ids)
    if not loaded:
        return CitedFilesBind("", [])
    excerpt = await asyncio.to_thread(cited_files_prompt_excerpt, loaded)
    dify_files = await upload_cited_files_to_dify(client, dify_user, loaded)
    logger.info(
        "[MindmateSeminar] cited files session=%s loaded=%s excerpt_chars=%s dify_files=%s",
        session_id,
        len(loaded),
        len(excerpt),
        len(dify_files),
    )
    return CitedFilesBind(excerpt, dify_files)
