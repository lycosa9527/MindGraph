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


def test_build_store_zip_excludes_jspdf_and_pdf_worker() -> None:
    """CWS RHC: do not ship jsPDF UMD or pdf.js worker (local jpeg-pdf + disableWorker)."""
    data = build_store_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = set(archive.namelist())
    assert "vendor/jspdf.umd.min.js" not in names
    assert "vendor/pdfjs/pdf.worker.min.js" not in names
    assert "doc-extract/engines/jpeg-pdf.js" in names
    assert not any(n.endswith("REFERENCES.md") for n in names)
    assert not any(n.startswith("store-assets/") for n in names)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        background = archive.read("background.js").decode("utf-8")
        hosts = archive.read("doc-extract/hosts.js").decode("utf-8")
    assert "jspdf" not in background.lower()
    assert "jpeg-pdf.js" in background
    assert "437609" not in hosts
    assert "GreasyFork" not in hosts
