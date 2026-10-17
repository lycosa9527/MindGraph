"""PDF text extraction for the Chrome extension, including scanned-page OCR."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.database import get_async_db
from routers.api.extension_pdf_text import router
from services.knowledge.document_processor import DocumentProcessor
from services.knowledge.extension_pdf_text import (
    extract_pdf_bytes,
    page_has_image,
    pdf_should_use_vision_ocr,
)
from utils.auth import get_current_user_or_api_key

app = FastAPI()
app.include_router(router, prefix="/api")


def _text_pdf(message: str) -> bytes:
    stream = f"BT /F1 24 Tf 40 80 Td ({message}) Tj ET"
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] "
        + "/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        f"4 0 obj\n<< /Length {len(stream)} >>\nstream\n{stream}\nendstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    body = "%PDF-1.4\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(body))
        body += obj
    xref_at = len(body)
    xref = "xref\n0 6\n0000000000 65535 f \n"
    for index in range(1, 6):
        xref += f"{offsets[index]:010d} 00000 n \n"
    trailer = f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    return (body + xref + trailer).encode("ascii")


def _blank_pdf() -> bytes:
    return _text_pdf("")


def _make_user() -> SimpleNamespace:
    user = SimpleNamespace()
    user.id = 42
    user.role = "teacher"
    user.organization_id = 1
    return user


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """Return a TestClient bound to the extension PDF route."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Reset FastAPI dependency overrides before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def _write_pdf(tmp_path: Path, payload: bytes) -> str:
    path = tmp_path / "lesson.pdf"
    path.write_bytes(payload)
    return str(path)


def test_extract_pdf_text_reads_embedded_text_layer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A normal PDF returns its text layer and does not call OCR."""

    def fail_ocr(*_args: object, **_kwargs: object) -> tuple[str, list[object]]:
        raise AssertionError("OCR should not run for a text PDF")

    monkeypatch.setattr(
        "services.knowledge.document_processor.document_ocr.ocr_pdf_pages",
        fail_ocr,
    )
    text, source = DocumentProcessor().extract_pdf_text(_write_pdf(tmp_path, _text_pdf("Hello MindGraph")))
    assert source == "text"
    assert "Hello MindGraph" in text


def test_extract_pdf_text_uses_ocr_when_the_layer_is_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An image-only PDF falls back to rasterized OCR."""

    def fake_ocr(file_path: str, max_pages: int, dpi: int) -> tuple[str, list[dict[str, int]]]:
        del file_path, dpi
        assert max_pages == 4
        return "教学目标：朗读课文", []

    monkeypatch.setattr(
        "services.knowledge.document_processor.document_ocr.ocr_pdf_pages",
        fake_ocr,
    )
    text, source = DocumentProcessor().extract_pdf_text(
        _write_pdf(tmp_path, _blank_pdf()),
        max_ocr_pages=4,
    )
    assert source == "ocr"
    assert "教学目标" in text


def test_extract_pdf_bytes_rejects_non_pdf() -> None:
    """Non-PDF uploads are rejected before OCR."""
    with pytest.raises(ValueError, match="not a PDF"):
        extract_pdf_bytes(b"not a pdf", 4)


def test_extension_extract_pdf_text_returns_ocr_body(client: TestClient) -> None:
    """The extension route returns server-extracted text for an uploaded PDF."""
    app.dependency_overrides[get_current_user_or_api_key] = _make_user

    async def _db_override():
        yield None

    app.dependency_overrides[get_async_db] = _db_override
    with (
        patch(
            "routers.api.extension_pdf_text.check_endpoint_rate_limit",
            new_callable=AsyncMock,
        ),
        patch(
            "routers.api.extension_pdf_text.extract_pdf_bytes",
            return_value={"text": "济南的冬天", "source": "ocr"},
        ),
    ):
        response = client.post(
            "/api/extension/extract_pdf_text",
            files={"file": ("lesson.pdf", _text_pdf("ignored"), "application/pdf")},
            data={"max_pages": "4"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "济南的冬天"
    assert body["source"] == "ocr"


def test_extension_extract_pdf_text_rejects_non_pdf(client: TestClient) -> None:
    """The route reports a non-PDF upload as a client error."""
    app.dependency_overrides[get_current_user_or_api_key] = _make_user

    async def _db_override():
        yield None

    app.dependency_overrides[get_async_db] = _db_override
    with patch(
        "routers.api.extension_pdf_text.check_endpoint_rate_limit",
        new_callable=AsyncMock,
    ):
        response = client.post(
            "/api/extension/extract_pdf_text",
            files={"file": ("notes.txt", b"hello", "text/plain")},
            data={"max_pages": "4"},
        )
    assert response.status_code == 400


class _PdfNode:
    """Minimal pypdf-like node for image-XObject checks."""

    def __init__(self, mapping: dict[str, object]) -> None:
        self._mapping = mapping

    def get_object(self) -> "_PdfNode":
        """Return this node, matching pypdf's indirect-object resolution."""
        return self

    def get(self, key: str, default: object = None) -> object:
        """Read one PDF dictionary entry."""
        return self._mapping.get(key, default)

    def values(self) -> object:
        """Return child objects the way a pypdf dictionary does."""
        return self._mapping.values()


def test_page_has_image_finds_image_inside_a_form() -> None:
    """A slide wrapped in a form XObject still counts as an image page."""
    image = _PdfNode({"/Subtype": "/Image"})
    form = _PdfNode(
        {
            "/Subtype": "/Form",
            "/Resources": _PdfNode({"/XObject": _PdfNode({"/Im0": image})}),
        }
    )
    page = _PdfNode({"/Resources": _PdfNode({"/XObject": _PdfNode({"/Fm0": form})})})
    assert page_has_image(page) is True
    assert page_has_image(_PdfNode({"/Resources": _PdfNode({})})) is False


def test_pdf_should_use_vision_ocr_requires_every_sampled_page() -> None:
    """Vision OCR is reserved for files whose sampled pages are all pictures."""
    assert pdf_should_use_vision_ocr("", 2, 2) is True
    assert pdf_should_use_vision_ocr("Hello MindGraph lesson text is long enough", 2, 2) is False
    assert pdf_should_use_vision_ocr("", 2, 1) is False


def test_extract_pdf_bytes_keeps_text_layer_even_if_marked_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real text layer is returned without calling the vision model."""

    def fail_page_ocr(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("vision OCR should not run")

    monkeypatch.setattr(
        "services.knowledge.extension_pdf_text.document_ocr.ocr_pdf_page_index",
        fail_page_ocr,
    )
    pdf_path = _write_pdf(tmp_path, _text_pdf("Hello MindGraph lesson text is long enough"))
    result = extract_pdf_bytes(Path(pdf_path).read_bytes(), 4, True)
    assert result["source"] == "text"
    assert result["image_based"] is False
    assert "Hello MindGraph" in result["text"]


def test_extract_pdf_bytes_ocrs_when_the_client_detected_images(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The extension's image classification OCRs sparse image pages."""

    def fake_page_ocr(
        _path: str,
        page_index: int,
        _dpi: int,
        *,
        model: str | None = None,
    ) -> str:
        assert page_index == 0
        assert model == "qwen3.8-flash"
        return "教学目标：朗读课文，整体感知济南的冬天。"

    monkeypatch.setattr(
        "services.knowledge.extension_pdf_text.document_ocr.ocr_pdf_page_index",
        fake_page_ocr,
    )
    pdf_path = _write_pdf(tmp_path, _blank_pdf())
    result = extract_pdf_bytes(Path(pdf_path).read_bytes(), 4, True)
    assert result["source"] == "ocr"
    assert result["image_based"] is True
    assert "教学目标" in result["text"]
