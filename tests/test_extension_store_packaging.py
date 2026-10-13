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


_REMOTE_CODE_MARKERS = (
    "eval(",
    "new Function",
    'createElement("script")',
    "createElement('script')",
    'importScripts("${',
    "importScripts('${",
    "importScripts(`",
)


def test_build_store_zip_has_no_remote_code_patterns() -> None:
    """CWS rejects Manifest V3 packages that contain eval, new Function, or script injection."""
    data = build_store_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
        assert "vendor/jspdf.umd.min.js" not in names
        assert "vendor/pdfjs/pdf.worker.min.js" in names
        assert "vendor/pdfjs/pdf.min.js" in names
        assert "doc-extract/engines/jpeg-pdf.js" in names
        assert not any(name.endswith("REFERENCES.md") for name in names)
        assert not any(name.startswith("store-assets/") for name in names)
        background = archive.read("background.js").decode("utf-8")
        hosts = archive.read("doc-extract/hosts.js").decode("utf-8")
        offscreen = archive.read("offscreen.html").decode("utf-8")
        offenders: list[str] = []
        for name in sorted(names):
            if not name.endswith((".js", ".html", ".json")):
                continue
            text = archive.read(name).decode("utf-8")
            for marker in _REMOTE_CODE_MARKERS:
                if marker in text:
                    offenders.append(f"{name}: {marker}")
    assert not offenders, offenders
    assert "jspdf" not in background.lower()
    assert "jpeg-pdf.js" in background
    assert "437609" not in hosts
    assert "GreasyFork" not in hosts
    assert offscreen.index("pdf.worker.min.js") < offscreen.index("pdf.min.js")
