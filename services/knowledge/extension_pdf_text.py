"""Extract text from a PDF upload, including image-only SmartEdu transcodes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Dict, Tuple

import pypdf
from pypdf.errors import PdfReadError

from services.knowledge import document_ocr
from services.utils.error_types import FILE_IO_ERRORS

logger = logging.getLogger(__name__)

MAX_EXTENSION_PDF_BYTES = 8 * 1024 * 1024
MAX_EXTENSION_OCR_PAGES = 8
IMAGE_PAGE_MAX_CHARS = 20
CLASSIFY_SAMPLE_PAGES = 3
PDF_OCR_DPI = 200
EXTENSION_OCR_MODEL = "qwen3.8-flash"
PDF_READ_ERRORS: Tuple[type[BaseException], ...] = FILE_IO_ERRORS + (PdfReadError,)


def _resolved(obj: Any) -> Any:
    get_object = getattr(obj, "get_object", None)
    if callable(get_object):
        return get_object()
    return obj


def _xobject_has_image(xobjects: Any, depth: int = 0) -> bool:
    """True when an XObject tree contains an image, including one level of forms."""
    if xobjects is None or depth > 2:
        return False
    resolved = _resolved(xobjects)
    values = getattr(resolved, "values", None)
    if not callable(values):
        return False
    raw_items = values()
    if not isinstance(raw_items, Iterable):
        return False
    for item in raw_items:
        node = _resolved(item)
        getter = getattr(node, "get", None)
        if not callable(getter):
            continue
        subtype = str(getter("/Subtype") or "")
        if subtype == "/Image":
            return True
        if subtype != "/Form":
            continue
        resources = _resolved(getter("/Resources"))
        resource_get = getattr(resources, "get", None)
        if not callable(resource_get):
            continue
        nested = resource_get("/XObject")
        if nested is not None and _xobject_has_image(nested, depth + 1):
            return True
    return False


def page_has_image(page: Any) -> bool:
    """True when a PDF page paints an image XObject or a form that contains one."""
    getter = getattr(page, "get", None)
    if not callable(getter):
        return False
    resources = _resolved(getter("/Resources"))
    resource_get = getattr(resources, "get", None)
    if not callable(resource_get):
        return False
    return _xobject_has_image(resource_get("/XObject"))


def pdf_should_use_vision_ocr(text: str, sampled_pages: int, image_like_pages: int) -> bool:
    """Vision OCR is for files whose sampled pages are pictures, not text."""
    if sampled_pages < 1 or image_like_pages != sampled_pages:
        return False
    return len(text.strip()) < IMAGE_PAGE_MAX_CHARS


def inspect_pdf_file(file_path: str) -> Dict[str, Any]:
    """Read the text layer and decide whether the pages are images."""
    reader = pypdf.PdfReader(file_path)
    parts = []
    sample_limit = min(CLASSIFY_SAMPLE_PAGES, len(reader.pages))
    image_like_pages = 0
    for index, page in enumerate(reader.pages):
        page_text = (page.extract_text() or "").strip()
        if page_text:
            parts.append(page_text)
        if index < sample_limit and len(page_text) < IMAGE_PAGE_MAX_CHARS and page_has_image(page):
            image_like_pages += 1
    text = "\n\n".join(parts).strip()
    return {
        "text": text,
        "page_count": len(reader.pages),
        "image_based": pdf_should_use_vision_ocr(text, sample_limit, image_like_pages),
    }


def _extract_pdf_pages_mixed(
    file_path: str,
    page_cap: int,
    force_image: bool,
) -> Dict[str, Any]:
    """Per page: embedded text when rich enough, else vision OCR for image pages."""
    reader = pypdf.PdfReader(file_path)
    parts: list[str] = []
    used_ocr = False
    used_text_layer = False
    page_total = min(len(reader.pages), page_cap)
    for index in range(page_total):
        page = reader.pages[index]
        page_text = (page.extract_text() or "").strip()
        if len(page_text) >= IMAGE_PAGE_MAX_CHARS:
            parts.append(page_text)
            used_text_layer = True
            continue
        should_ocr = len(page_text) < IMAGE_PAGE_MAX_CHARS and (bool(force_image) or page_has_image(page))
        if should_ocr:
            ocr_piece = document_ocr.ocr_pdf_page_index(
                file_path,
                index,
                PDF_OCR_DPI,
                model=EXTENSION_OCR_MODEL,
            ).strip()
            if ocr_piece:
                parts.append(ocr_piece)
                used_ocr = True
                continue
        if page_text:
            parts.append(page_text)
    text = "\n\n".join(parts).strip()
    if not text:
        return {"text": "", "source": "empty", "image_based": bool(used_ocr)}
    if used_ocr and used_text_layer:
        source = "mixed"
    elif used_ocr:
        source = "ocr"
    else:
        source = "text"
    return {
        "text": text,
        "source": source,
        "image_based": bool(used_ocr),
    }


def extract_pdf_bytes(raw: bytes, max_ocr_pages: int, force_image: bool = False) -> Dict[str, Any]:
    """Return text for one PDF, merging text layers and image pages per page.

    ``force_image`` is the extension's pdf.js classification. A page with a real
    text layer is kept; sparse or image pages use vision OCR. ``source`` is
    ``text``, ``ocr``, ``mixed``, or ``empty``.
    """
    if not raw or not raw.startswith(b"%PDF"):
        raise ValueError("File is not a PDF")
    if len(raw) > MAX_EXTENSION_PDF_BYTES:
        raise ValueError("PDF is too large")
    page_cap = max(1, min(int(max_ocr_pages), MAX_EXTENSION_OCR_PAGES))
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as handle:
            handle.write(raw)
            temp_path = Path(handle.name)
        result = _extract_pdf_pages_mixed(str(temp_path), page_cap, force_image)
        logger.info(
            "[ExtensionPdfText] extracted source=%s image_based=%s chars=%d pages_cap=%d",
            result.get("source"),
            result.get("image_based"),
            len(str(result.get("text") or "")),
            page_cap,
        )
        return result
    except PDF_READ_ERRORS as exc:
        logger.warning("[ExtensionPdfText] extract failed: %s", exc)
        return {"text": "", "source": "empty", "image_based": False}
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)
