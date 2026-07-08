"""Tests for store-ready MindGraph extension zip packaging."""

from __future__ import annotations

import io
import zipfile

from utils.extension_store_packaging import build_store_zip_bytes


def test_build_store_zip_has_manifest_at_root() -> None:
    """Store zip must match Microsoft upload format (manifest.json at archive root)."""
    data = build_store_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
    assert "manifest.json" in names
    assert not any(name.startswith("chrome-extension/") for name in names)
    assert "node_modules/" not in "".join(names)
    assert "test/" not in names and not any(n.startswith("test/") for n in names)


def test_build_store_zip_includes_background_worker() -> None:
    """Runtime service worker must be present in the store package."""
    data = build_store_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        assert "background.js" in archive.namelist()
