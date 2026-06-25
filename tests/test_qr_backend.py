"""Regression tests for MindBot bind QR backend (pyzbar + Pillow)."""

from __future__ import annotations

import importlib
import importlib.util
from collections.abc import Generator
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from services.mindbot.bind.qr_backend import (
    _PyzbarBackendState,
    get_pil_image_class,
    get_zbar_decode,
    pyzbar_backend_ready,
)


def _module_with(name: str, **attrs: Any) -> ModuleType:
    mod = ModuleType(name)
    for key, value in attrs.items():
        setattr(mod, key, value)
    return mod


@pytest.fixture(autouse=True)
def _reset_pyzbar_backend_state() -> Generator[None, None, None]:
    """Each test gets a fresh lazy-load attempt."""
    _PyzbarBackendState.attempted = False
    _PyzbarBackendState.zbar_decode = None
    _PyzbarBackendState.pil_image_module = None
    yield
    _PyzbarBackendState.attempted = False
    _PyzbarBackendState.zbar_decode = None
    _PyzbarBackendState.pil_image_module = None


def test_pyzbar_backend_ready_uses_pil_image_submodule_not_pil_package() -> None:
    """Pillow exposes Image via PIL.Image, not PIL.Image on the PIL package."""
    fake_pil_pkg = ModuleType("PIL")
    fake_pil_image = _module_with("PIL.Image", open=MagicMock())
    fake_pyzbar = _module_with("pyzbar.pyzbar", decode=MagicMock(return_value=[]))

    def fake_import(name: str) -> ModuleType:
        if name == "pyzbar.pyzbar":
            return fake_pyzbar
        if name == "PIL.Image":
            return fake_pil_image
        if name == "PIL":
            return fake_pil_pkg
        raise ImportError(name)

    with patch.object(importlib, "import_module", side_effect=fake_import):
        assert pyzbar_backend_ready() is True
        decode_fn = getattr(fake_pyzbar, "decode")
        assert get_zbar_decode() is decode_fn
        assert get_pil_image_class() is fake_pil_image


def test_pyzbar_backend_ready_false_when_only_pil_package_importable() -> None:
    """Importing top-level PIL alone must not count as a ready backend."""
    fake_pil_pkg = ModuleType("PIL")

    def fake_import(name: str) -> ModuleType:
        if name == "pyzbar.pyzbar":
            return _module_with("pyzbar.pyzbar", decode=MagicMock(return_value=[]))
        if name == "PIL.Image":
            raise ImportError("PIL.Image missing")
        if name == "PIL":
            return fake_pil_pkg
        raise ImportError(name)

    with patch.object(importlib, "import_module", side_effect=fake_import):
        assert pyzbar_backend_ready() is False
        assert get_zbar_decode() is None
        assert get_pil_image_class() is None


def test_pyzbar_backend_ready_false_when_pil_image_has_no_open() -> None:
    """PIL.Image without open must not register as ready."""
    fake_pil_image = ModuleType("PIL.Image")
    fake_pyzbar = _module_with("pyzbar.pyzbar", decode=MagicMock(return_value=[]))

    def fake_import(name: str) -> ModuleType:
        if name == "pyzbar.pyzbar":
            return fake_pyzbar
        if name == "PIL.Image":
            return fake_pil_image
        raise ImportError(name)

    with patch.object(importlib, "import_module", side_effect=fake_import):
        assert pyzbar_backend_ready() is False


@pytest.mark.skipif(
    importlib.util.find_spec("pyzbar") is None,
    reason="pyzbar not installed in this environment",
)
def test_pyzbar_backend_ready_integration_when_installed() -> None:
    """When pyzbar/Pillow are installed, readiness matches a direct import check."""
    importlib.import_module("pyzbar.pyzbar")
    pil_image_mod = importlib.import_module("PIL.Image")
    assert callable(getattr(pil_image_mod, "open", None))
    assert pyzbar_backend_ready() is True
