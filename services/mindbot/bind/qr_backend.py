"""Optional QR decode backend (pyzbar + Pillow)."""

from __future__ import annotations

import importlib
import logging
from typing import Any, Callable, Optional, cast

logger = logging.getLogger(__name__)


class _PyzbarBackendState:
    """Lazy loader for optional pyzbar + Pillow QR decode."""

    attempted: bool = False
    zbar_decode: Optional[Callable[..., list[Any]]] = None
    pil_image_module: Optional[Any] = None


def _backend_loaded() -> bool:
    return (
        _PyzbarBackendState.zbar_decode is not None
        and _PyzbarBackendState.pil_image_module is not None
    )


def pyzbar_backend_ready() -> bool:
    """Return True when pyzbar and Pillow are importable."""
    if _PyzbarBackendState.attempted:
        return _backend_loaded()
    _PyzbarBackendState.attempted = True
    try:
        pyzbar_mod = importlib.import_module("pyzbar.pyzbar")
        pil_image_mod = importlib.import_module("PIL.Image")
        pil_open = getattr(pil_image_mod, "open", None)
        zbar_decode = getattr(pyzbar_mod, "decode", None)
    except (ImportError, OSError) as exc:
        logger.warning("[MindBot] bind QR backend unavailable: %s", exc)
        return False
    if not callable(pil_open) or not callable(zbar_decode):
        logger.warning("[MindBot] bind QR backend unavailable: Pillow.open or pyzbar.decode missing")
        return False
    _PyzbarBackendState.zbar_decode = cast(Callable[..., list[Any]], zbar_decode)
    _PyzbarBackendState.pil_image_module = pil_image_mod
    return True


def get_zbar_decode() -> Optional[Callable[..., list[Any]]]:
    """Return pyzbar decode callable when available."""
    if pyzbar_backend_ready():
        return _PyzbarBackendState.zbar_decode
    return None


def get_pil_image_class() -> Optional[Any]:
    """Return Pillow Image module (provides ``open``) when available."""
    if pyzbar_backend_ready():
        return _PyzbarBackendState.pil_image_module
    return None


def _decode_with_zbar(decode_fn: Callable[..., list[Any]], image: Any) -> list[Any]:
    symbols = decode_fn(image)
    if isinstance(symbols, list):
        return symbols
    return []


def decode_qr_image(image: Any) -> list[Any]:
    """Decode QR symbols from a Pillow image, or return an empty list."""
    if not pyzbar_backend_ready():
        return []
    zbar_decode_fn = _PyzbarBackendState.zbar_decode
    if zbar_decode_fn is None:
        return []
    return _decode_with_zbar(zbar_decode_fn, image)
