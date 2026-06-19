"""Optional QR decode backend (pyzbar + Pillow)."""

from __future__ import annotations

import importlib
from typing import Any, Callable, Optional, Type


class _PyzbarBackendState:
    """Lazy loader for optional pyzbar + Pillow QR decode."""

    attempted: bool = False
    zbar_decode: Optional[Callable[..., list[Any]]] = None
    pil_image_class: Optional[Type[Any]] = None


def pyzbar_backend_ready() -> bool:
    """Return True when pyzbar and Pillow are importable."""
    if _PyzbarBackendState.attempted:
        return _PyzbarBackendState.zbar_decode is not None
    _PyzbarBackendState.attempted = True
    try:
        pyzbar_mod = importlib.import_module("pyzbar.pyzbar")
        pil_pkg = importlib.import_module("PIL")
    except ImportError:
        return False
    _PyzbarBackendState.zbar_decode = pyzbar_mod.decode
    _PyzbarBackendState.pil_image_class = pil_pkg.Image
    return True


def get_zbar_decode() -> Optional[Callable[..., list[Any]]]:
    """Return pyzbar decode callable when available."""
    if pyzbar_backend_ready():
        return _PyzbarBackendState.zbar_decode
    return None


def get_pil_image_class() -> Optional[Type[Any]]:
    """Return Pillow Image class when available."""
    if pyzbar_backend_ready():
        return _PyzbarBackendState.pil_image_class
    return None


def decode_qr_image(image: Any) -> list[Any]:
    """Decode QR symbols from a Pillow image, or return an empty list."""
    if not pyzbar_backend_ready():
        return []
    pyzbar_mod = importlib.import_module("pyzbar.pyzbar")
    decode_attr = getattr(pyzbar_mod, "decode", None)
    if not callable(decode_attr):
        return []
    symbols = decode_attr(image)
    if isinstance(symbols, list):
        return symbols
    return []
