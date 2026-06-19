"""Decode bind tokens from QR images sent in DingTalk."""

from __future__ import annotations

import logging
import re
from io import BytesIO
from typing import Optional
from urllib.parse import parse_qs, urlparse

from services.auth.dingtalk_bind_constants import (
    BIND_PATH_MARKER,
    BIND_QUERY_CODE_PARAM,
    BIND_QUERY_PARAM,
)
from services.mindbot.bind.qr_backend import decode_qr_image, get_pil_image_class, pyzbar_backend_ready

logger = logging.getLogger(__name__)

_BIND_URL_RE = re.compile(
    rf"{re.escape(BIND_PATH_MARKER)}\?{re.escape(BIND_QUERY_PARAM)}=([A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


def extract_bind_token_from_text(text: str) -> Optional[str]:
    """Extract bind token from a URL or raw string containing the bind path."""
    token, _code = extract_bind_payload_from_text(text)
    return token


def extract_bind_payload_from_text(text: str) -> tuple[Optional[str], Optional[str]]:
    """Extract (token, bind_code) from a bind URL or raw string."""
    raw = (text or "").strip()
    if not raw or BIND_PATH_MARKER not in raw:
        return None, None
    match = _BIND_URL_RE.search(raw)
    token: Optional[str] = None
    if match:
        token = match.group(1).strip() or None
    try:
        parsed = urlparse(raw if "://" in raw else f"https://x{raw}")
    except ValueError:
        return token, None
    if BIND_PATH_MARKER not in (parsed.path or ""):
        return token, None
    params = parse_qs(parsed.query or "")
    if token is None:
        values = params.get(BIND_QUERY_PARAM) or params.get(BIND_QUERY_PARAM.upper()) or []
        if values:
            token = (values[0] or "").strip() or None
    code_values = params.get(BIND_QUERY_CODE_PARAM) or params.get(BIND_QUERY_CODE_PARAM.upper()) or []
    bind_code: Optional[str] = None
    if code_values:
        candidate = (code_values[0] or "").strip()
        if candidate:
            bind_code = candidate
    return token, bind_code


def decode_bind_token_from_image(image_bytes: bytes) -> tuple[Optional[str], Optional[str], bool]:
    """
    Decode QR image bytes.

    Returns (token, bind_code, is_bind_qr_attempt).
    ``is_bind_qr_attempt`` is True when decoded payload looks like a bind URL
    (even if token extraction failed).
    """
    if not image_bytes:
        return None, None, False
    if not pyzbar_backend_ready():
        logger.warning("[MindBot] pyzbar/PIL unavailable for bind QR decode")
        return None, None, False

    pil_image_class = get_pil_image_class()
    if pil_image_class is None:
        logger.warning("[MindBot] pyzbar/PIL unavailable for bind QR decode")
        return None, None, False

    try:
        image = pil_image_class.open(BytesIO(image_bytes))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        for symbol in decode_qr_image(image):
            payload = symbol.data
            if isinstance(payload, bytes):
                text = payload.decode("utf-8", errors="replace")
            else:
                text = str(payload)
            if BIND_PATH_MARKER not in text:
                continue
            token, bind_code = extract_bind_payload_from_text(text)
            return token, bind_code, True
    except OSError as exc:
        logger.debug("[MindBot] bind QR decode failed: %s", exc)
        return None, None, False
    return None, None, False
