"""OCR helpers: DashScope vision model with a Tesseract fallback.

Shared by the document processor for image-file OCR and scanned-PDF page OCR.
Uses the configurable ``DASHSCOPE_VISION_MODEL`` (default ``qwen3.6-flash``) via
the DashScope multimodal-generation endpoint; falls back to Tesseract when the
provider call fails. Rasterizes scanned PDFs with PyMuPDF (fitz).

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import base64
import io
import logging
from typing import Any, Dict, List, Tuple, Type

from services.utils.error_types import FILE_IO_ERRORS

logger = logging.getLogger(__name__)

# Default OCR instruction: read every character, preserve layout.
OCR_PROMPT = "请提取图片中的所有文字，保持原有格式。如果没有文字，请回复空。"

_httpx_mod: Any = None
_httpx_available = False
try:
    import httpx as _httpx_import

    _httpx_mod = _httpx_import
    _httpx_available = True
except ImportError:
    pass

_settings_config: Any = None
_config_available = False
try:
    from config.settings import config as _settings_config_import

    _settings_config = _settings_config_import
    _config_available = True
except ImportError:
    pass

_fitz_mod: Any = None
_fitz_available = False
try:
    import fitz as _fitz_import

    _fitz_mod = _fitz_import
    _fitz_available = True
except ImportError:
    pass

_pytesseract_mod: Any = None
_pil_image_cls: Any = None
_tesseract_available = False
try:
    import pytesseract as _pytesseract_import
    from PIL import Image as _pil_image_import

    _pytesseract_mod = _pytesseract_import
    _pil_image_cls = _pil_image_import
    _tesseract_available = True
except ImportError:
    pass

# OCR calls hit DashScope over HTTP; include httpx transport/status errors so a
# provider failure falls back to Tesseract (or an empty page) instead of aborting.
if _httpx_available and _httpx_mod is not None:
    OCR_CALL_ERRORS: Tuple[Type[Exception], ...] = FILE_IO_ERRORS + (_httpx_mod.HTTPError,)
else:
    OCR_CALL_ERRORS = FILE_IO_ERRORS


def dashscope_vision_ocr(image_bytes: bytes, mime_type: str = "image/png") -> str:
    """Run OCR on raw image bytes via the DashScope multimodal endpoint.

    Uses the configurable ``DASHSCOPE_VISION_MODEL`` (default ``qwen3.6-flash``).
    Returns the extracted text (possibly empty); raises on transport errors.
    """
    if not _httpx_available or not _config_available or _httpx_mod is None or _settings_config is None:
        raise ValueError("httpx and config required for DashScope OCR")

    api_key = _settings_config.QWEN_API_KEY
    if not api_key:
        raise ValueError("DashScope API key required for OCR")

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": _settings_config.DASHSCOPE_VISION_MODEL,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"image": f"data:{mime_type};base64,{image_base64}"},
                        {"text": OCR_PROMPT},
                    ],
                }
            ]
        },
        "parameters": {},
    }

    base_url = _settings_config.DASHSCOPE_API_URL
    ocr_url = f"{base_url}services/aigc/multimodal-generation/generation"

    with _httpx_mod.Client(timeout=120.0) as client:
        response = client.post(ocr_url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

    return _parse_vision_ocr_text(result)


def parse_dashscope_multimodal_text(result: Dict[str, Any]) -> str:
    """Pull text out of a DashScope multimodal-generation response."""
    output = result.get("output") if isinstance(result, dict) else None
    choices = output.get("choices") if isinstance(output, dict) else None
    if not choices:
        return ""
    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif "text" in item:
                    text_parts.append(str(item["text"]))
            elif isinstance(item, str):
                text_parts.append(item)
        return "".join(text_parts).strip()
    if isinstance(content, str):
        return content.strip()
    return str(content).strip() if content else ""


def _parse_vision_ocr_text(result: Dict[str, Any]) -> str:
    """Backward-compatible alias for OCR helpers in this module."""
    return parse_dashscope_multimodal_text(result)


def ocr_image_bytes(png_bytes: bytes) -> str:
    """OCR raw PNG bytes via DashScope, falling back to Tesseract; never raises."""
    try:
        return dashscope_vision_ocr(png_bytes, "image/png")
    except OCR_CALL_ERRORS as exc:
        logger.warning("[DocumentOCR] DashScope page OCR failed, trying Tesseract: %s", exc)
    if _tesseract_available and _pil_image_cls is not None and _pytesseract_mod is not None:
        try:
            image = _pil_image_cls.open(io.BytesIO(png_bytes))
            return _pytesseract_mod.image_to_string(image, lang="chi_sim+eng")
        except FILE_IO_ERRORS as exc:
            logger.warning("[DocumentOCR] Tesseract page OCR failed: %s", exc)
    return ""


def ocr_image_file(file_path: str, mime_type: str = "image/jpeg") -> str:
    """OCR an image file via DashScope, falling back to Tesseract.

    Raises ``ValueError`` when both providers yield no text.
    """
    resolved_mime = mime_type if mime_type.startswith("image/") else "image/jpeg"
    with open(file_path, "rb") as handle:
        image_data = handle.read()
    try:
        text = dashscope_vision_ocr(image_data, resolved_mime)
        if text and text.strip():
            return text.strip()
    except OCR_CALL_ERRORS as exc:
        logger.warning("[DocumentOCR] DashScope image OCR failed: %s", exc)

    if not (_tesseract_available and _pil_image_cls is not None and _pytesseract_mod is not None):
        raise ValueError("OCR failed: DashScope unavailable and Tesseract not installed")
    try:
        image = _pil_image_cls.open(file_path)
        text = _pytesseract_mod.image_to_string(image, lang="chi_sim+eng")
    except FILE_IO_ERRORS as exc:
        raise ValueError(f"OCR failed with both DashScope and Tesseract: {exc}") from exc
    if text and str(text).strip():
        return str(text).strip()
    raise ValueError("No text extracted from OCR response")


def ocr_pdf_pages(file_path: str, max_pages: int, dpi: int) -> Tuple[str, List[Dict[str, Any]]]:
    """OCR a scanned PDF by rasterizing pages and reading each with the vision model.

    Renders pages with PyMuPDF (fitz), then OCRs each page image via the
    DashScope vision model, falling back to Tesseract per page. Returns
    ``(text, page_info)`` where ``page_info`` carries per-page char offsets
    (empty when OCR is unavailable or yields nothing).
    """
    if not _fitz_available or _fitz_mod is None:
        logger.warning("[DocumentOCR] PyMuPDF (fitz) unavailable; cannot OCR scanned PDF")
        return "", []

    text_parts: List[str] = []
    page_info: List[Dict[str, Any]] = []
    current_pos = 0
    try:
        with _fitz_mod.open(file_path) as doc:
            page_total = min(doc.page_count, max_pages)
            zoom = dpi / 72.0
            matrix = _fitz_mod.Matrix(zoom, zoom)
            for page_index in range(page_total):
                page = doc.load_page(page_index)
                pixmap = page.get_pixmap(matrix=matrix)
                png_bytes = pixmap.tobytes("png")
                page_text = ocr_image_bytes(png_bytes).strip()
                if page_text:
                    start_pos = current_pos
                    text_parts.append(page_text)
                    current_pos += len(page_text) + 2  # +2 for the "\n\n" join
                    page_info.append({"page": page_index + 1, "start": start_pos, "end": current_pos})
    except FILE_IO_ERRORS as exc:
        logger.error("[DocumentOCR] PDF OCR rasterization failed: %s", exc)

    return "\n\n".join(text_parts), page_info
