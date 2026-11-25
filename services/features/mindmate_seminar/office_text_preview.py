"""Readable Office text when LibreOffice PDF conversion is unavailable.

Used by seminar resource preview so Word / PowerPoint / Excel still open
in the room without soffice.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError as DocxPackageNotFoundError
from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException
from pptx import Presentation

from services.knowledge.document_office_extract import (
    extract_docx_markdown,
    extract_pptx_markdown,
    extract_xlsx_markdown,
)
from services.utils.error_types import FILE_IO_ERRORS


def _pptx_package_not_found_error() -> type[BaseException]:
    """python-pptx does not always export PackageNotFoundError."""
    try:
        module = importlib.import_module("pptx.opc.exceptions")
    except ImportError:
        return type("PptxPackageNotFoundError", (Exception,), {})
    loaded = getattr(module, "PackageNotFoundError", None)
    if isinstance(loaded, type) and issubclass(loaded, BaseException):
        return loaded
    return type("PptxPackageNotFoundError", (Exception,), {})


PptxPackageNotFoundError = _pptx_package_not_found_error()

logger = logging.getLogger(__name__)

_TEXT_PREVIEW_ERRORS: tuple[type[BaseException], ...] = FILE_IO_ERRORS + (
    TypeError,
    KeyError,
    BadZipFile,
    DocxPackageNotFoundError,
    PptxPackageNotFoundError,
    InvalidFileException,
)


def office_text_preview(source: Path, filename: str) -> str:
    """Return markdown-ish text for an OOXML seminar file, or empty on failure."""
    suffix = (Path(filename).suffix or source.suffix).lower()
    try:
        if suffix == ".docx":
            return extract_docx_markdown(Document, str(source)).strip()
        if suffix == ".pptx":
            return extract_pptx_markdown(Presentation, str(source)).strip()
        if suffix == ".xlsx":
            return extract_xlsx_markdown(load_workbook, str(source)).strip()
    except _TEXT_PREVIEW_ERRORS as exc:
        logger.warning(
            "[SeminarFiles] text preview failed file=%s err=%s",
            filename,
            type(exc).__name__,
        )
        return ""
    return ""
