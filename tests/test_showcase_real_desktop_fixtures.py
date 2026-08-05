"""Real Desktop fixtures: PDF/DOCX/PPTX → cover PNG + LO preview.pdf.

Default dir: ``C:\\Users\\roywa\\Desktop\\showcase test`` (WSL mount).
Override with ``SHOWCASE_REAL_FIXTURE_DIR``.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import fitz
import pytest
from PIL import Image, ImageStat

from services.knowledge.legacy_office_convert import resolve_soffice_path
from services.showcase.covers.generate import generate_showcase_cover
from services.showcase.covers.render import (
    THUMBNAIL_MAX_BYTES,
    render_document_cover_png,
    resolve_cover_pdf_path,
)

_DEFAULT_DIR = Path("/mnt/c/Users/roywa/Desktop/showcase test")
_WIN_DEFAULT_DIR = Path(r"C:\Users\roywa\Desktop\showcase test")
_SUFFIXES = frozenset({".pdf", ".doc", ".docx", ".pptx"})
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_OFFICE = frozenset({".doc", ".docx", ".pptx"})


def _fixture_dir() -> Path | None:
    override = os.environ.get("SHOWCASE_REAL_FIXTURE_DIR", "").strip()
    candidates = [Path(override)] if override else []
    candidates.extend((_DEFAULT_DIR, _WIN_DEFAULT_DIR))
    for path in candidates:
        if path.is_dir():
            return path
    return None


def _sources() -> list[Path]:
    root = _fixture_dir()
    if root is None:
        return []
    return sorted(path for path in root.iterdir() if path.is_file() and path.suffix.lower() in _SUFFIXES)


def _mean_luma(png: bytes) -> float:
    with Image.open(io.BytesIO(png)) as image:
        means = ImageStat.Stat(image.convert("RGB")).mean
        return sum(means) / len(means)


def _nonwhite_ratio(png: bytes, threshold: int = 245) -> float:
    with Image.open(io.BytesIO(png)) as image:
        rgb = image.convert("RGB")
        sample = rgb.resize(
            (min(160, rgb.width), min(160, rgb.height)),
            Image.Resampling.BILINEAR,
        )
        raw = sample.tobytes()
    total = len(raw) // 3
    if total <= 0:
        return 0.0
    ink = 0
    for index in range(0, total * 3, 3):
        if raw[index] < threshold or raw[index + 1] < threshold or raw[index + 2] < threshold:
            ink += 1
    return ink / total


requires_fixtures = pytest.mark.skipif(
    not _sources(),
    reason="Place pdf/docx/pptx under Desktop/showcase test or set SHOWCASE_REAL_FIXTURE_DIR",
)

requires_soffice = pytest.mark.skipif(
    resolve_soffice_path() is None,
    reason="LibreOffice (soffice) not installed",
)


@requires_fixtures
@requires_soffice
@pytest.mark.parametrize(
    "source",
    _sources() or [Path("missing.docx")],
    ids=lambda path: path.name if isinstance(path, Path) else "missing",
)
def test_real_fixture_cover_and_preview_pdf(source: Path, tmp_path: Path) -> None:
    """Each real fixture yields a non-blank thumb and a valid multi-page-capable PDF."""
    assert source.is_file()
    work = tmp_path / "work"
    work.mkdir()
    pdf_path = resolve_cover_pdf_path(source, work / "lo")
    assert pdf_path.is_file()
    assert pdf_path.read_bytes()[:5] == b"%PDF-"

    document = fitz.open(pdf_path)
    try:
        assert document.page_count >= 1
        page0 = document.load_page(0)
        # Must have either text or drawings/images — not an empty page.
        page_text = page0.get_text("text")
        has_text = bool(page_text.strip()) if isinstance(page_text, str) else bool(page_text)
        has_images = bool(page0.get_images(full=True))
        has_drawings = bool(page0.get_drawings())
        assert has_text or has_images or has_drawings
        page_has_text = has_text
    finally:
        document.close()

    png = render_document_cover_png(source, work / "cover")
    assert png.startswith(_PNG_MAGIC)
    assert len(png) <= THUMBNAIL_MAX_BYTES
    # Near-white worksheets (Xiaomi Car) are valid if they keep ink or text.
    assert _mean_luma(png) > 5
    assert _nonwhite_ratio(png) >= 0.004 or page_has_text


@requires_fixtures
@requires_soffice
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "source",
    [path for path in _sources() if path.suffix.lower() in _OFFICE] or [Path("missing.pptx")],
    ids=lambda path: path.name if isinstance(path, Path) else "missing",
)
async def test_generate_persists_preview_for_real_office(source: Path, tmp_path: Path) -> None:
    """Cover job for real Office files uploads thumbnail.png + preview.pdf."""
    assert source.is_file()
    post_id = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
    attachment_key = f"showcase/posts/{post_id}/attachment{source.suffix.lower()}"
    source_bytes = source.read_bytes()

    post = MagicMock()
    post.case_type = "teaching_design"
    post.author_id = 3
    post.spec = {"attachment_path": attachment_key}
    post.thumbnail_path = None

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = post
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None

    uploaded: dict[str, bytes] = {}

    def _fake_download(_key: str, dest: Path) -> bool:
        dest.write_bytes(source_bytes)
        return True

    def _fake_put(key: str, data: bytes, content_type: str = "") -> None:
        del content_type
        uploaded[key] = data

    with (
        patch(
            "services.showcase.covers.generate.acquire_cover_lock",
            return_value="token",
        ),
        patch("services.showcase.covers.generate.release_cover_lock"),
        patch(
            "services.showcase.covers.generate.rls_async_session",
            return_value=session,
        ),
        patch(
            "services.showcase.covers.generate.download_to_path_sync",
            side_effect=_fake_download,
        ),
        patch(
            "services.showcase.covers.generate.put_bytes_sync",
            side_effect=_fake_put,
        ),
        patch(
            "services.showcase.covers.generate.showcase_cache.invalidate_post",
            new_callable=AsyncMock,
        ),
        patch(
            "services.showcase.covers.generate.publish_showcase_cover_event",
            new_callable=AsyncMock,
        ) as publish,
        patch(
            "services.showcase.covers.generate.showcase_public_asset_url",
            side_effect=lambda key: f"/api/showcase/assets/{key}",
        ),
        patch(
            "services.showcase.covers.generate.tempfile.mkdtemp",
            return_value=str(tmp_path / "job"),
        ),
        patch(
            "services.showcase.covers.generate.mark_cover_job_running",
            new_callable=AsyncMock,
        ),
        patch(
            "services.showcase.covers.generate.mark_cover_job_stage",
            new_callable=AsyncMock,
        ),
        patch(
            "services.showcase.covers.generate.bind_cover_job_succeeded",
            new_callable=AsyncMock,
        ),
        patch(
            "services.showcase.covers.generate.mark_cover_job_failed",
            new_callable=AsyncMock,
        ),
    ):
        (tmp_path / "job").mkdir(parents=True, exist_ok=True)
        ok = await generate_showcase_cover(
            post_id=post_id,
            user_id=1,
            attachment_key=attachment_key,
            organization_id=None,
            author_id=3,
        )

    assert ok is True
    thumb_key = f"showcase/posts/{post_id}/thumbnail.png"
    preview_key = f"showcase/posts/{post_id}/preview.pdf"
    assert thumb_key in uploaded
    assert preview_key in uploaded
    assert uploaded[thumb_key].startswith(_PNG_MAGIC)
    assert uploaded[preview_key].startswith(b"%PDF-")
    assert _mean_luma(uploaded[thumb_key]) > 5
    assert _nonwhite_ratio(uploaded[thumb_key]) >= 0.004 or len(uploaded[preview_key]) > 10_000
    assert post.spec.get("preview_path") == preview_key
    ready = publish.await_args
    assert ready is not None
    assert ready.args[1] == "cover_ready"
    assert ready.kwargs.get("preview_url")


@requires_fixtures
@requires_soffice
def test_real_office_preview_pdf_readable_by_viewer_stack(tmp_path: Path) -> None:
    """LO preview.pdf must be loadable the same way pdf.js will (via PyMuPDF page walk)."""
    office = [path for path in _sources() if path.suffix.lower() in _OFFICE]
    assert office
    for source in office:
        pdf_path = resolve_cover_pdf_path(source, tmp_path / source.name / "lo")
        document = fitz.open(pdf_path)
        try:
            assert document.page_count >= 1
            for page_num in range(document.page_count):
                page = document.load_page(page_num)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(1.0, 1.0), alpha=False)
                assert pixmap.width > 0 and pixmap.height > 0
                assert len(pixmap.tobytes("png")) > 100
        finally:
            document.close()


@requires_fixtures
@requires_soffice
@pytest.mark.asyncio
async def test_generate_pdf_fixture_thumb_without_preview(tmp_path: Path) -> None:
    """Native PDF: thumbnail only — reader uses attachment, not preview.pdf."""
    pdfs = [path for path in _sources() if path.suffix.lower() == ".pdf"]
    if not pdfs:
        pytest.skip("no PDF fixture")
    source = pdfs[0]
    post_id = "cccccccc-dddd-eeee-ffff-000000000001"
    attachment_key = f"showcase/posts/{post_id}/attachment.pdf"
    source_bytes = source.read_bytes()

    post = MagicMock()
    post.case_type = "teaching_design"
    post.author_id = 3
    post.spec = {"attachment_path": attachment_key}
    post.thumbnail_path = None

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = post
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None

    uploaded: dict[str, bytes] = {}

    def _fake_download(_key: str, dest: Path) -> bool:
        dest.write_bytes(source_bytes)
        return True

    def _fake_put(key: str, data: bytes, content_type: str = "") -> None:
        del content_type
        uploaded[key] = data

    with (
        patch(
            "services.showcase.covers.generate.acquire_cover_lock",
            return_value="token",
        ),
        patch("services.showcase.covers.generate.release_cover_lock"),
        patch(
            "services.showcase.covers.generate.rls_async_session",
            return_value=session,
        ),
        patch(
            "services.showcase.covers.generate.download_to_path_sync",
            side_effect=_fake_download,
        ),
        patch(
            "services.showcase.covers.generate.put_bytes_sync",
            side_effect=_fake_put,
        ),
        patch(
            "services.showcase.covers.generate.showcase_cache.invalidate_post",
            new_callable=AsyncMock,
        ),
        patch(
            "services.showcase.covers.generate.publish_showcase_cover_event",
            new_callable=AsyncMock,
        ),
        patch(
            "services.showcase.covers.generate.showcase_public_asset_url",
            side_effect=lambda key: f"/api/showcase/assets/{key}",
        ),
        patch(
            "services.showcase.covers.generate.tempfile.mkdtemp",
            return_value=str(tmp_path / "job-pdf"),
        ),
        patch(
            "services.showcase.covers.generate.mark_cover_job_running",
            new_callable=AsyncMock,
        ),
        patch(
            "services.showcase.covers.generate.mark_cover_job_stage",
            new_callable=AsyncMock,
        ),
        patch(
            "services.showcase.covers.generate.bind_cover_job_succeeded",
            new_callable=AsyncMock,
        ),
        patch(
            "services.showcase.covers.generate.mark_cover_job_failed",
            new_callable=AsyncMock,
        ),
    ):
        (tmp_path / "job-pdf").mkdir(parents=True, exist_ok=True)
        ok = await generate_showcase_cover(
            post_id=post_id,
            user_id=1,
            attachment_key=attachment_key,
            organization_id=None,
            author_id=3,
        )

    assert ok is True
    assert f"showcase/posts/{post_id}/thumbnail.png" in uploaded
    assert f"showcase/posts/{post_id}/preview.pdf" not in uploaded
    assert "preview_path" not in (post.spec or {})
