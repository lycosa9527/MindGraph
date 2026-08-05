"""Unit + fixture tests for Showcase server-side teaching-design covers."""

from __future__ import annotations

import io
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import fitz
import pytest
from PIL import Image, ImageStat

from services.knowledge.legacy_office_convert import resolve_soffice_path
from services.showcase.covers.generate import (
    attachment_key_in_post_scope,
    generate_showcase_cover,
)
from services.showcase.covers.office_to_pdf import office_suffix_needs_pdf
from services.showcase.covers.render import (
    THUMBNAIL_MAX_BYTES,
    render_document_cover_png,
    shrink_png_bytes,
)

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

_DEFAULT_DOCX_LIANG = Path(
    "/mnt/c/Users/roywa/Desktop/小学-六年级-语文-《两小儿辩日》-梁静-北京师范大学昌平附属学校4.docx"
)
_WIN_DOCX_LIANG = Path(
    r"C:\Users\roywa\Desktop"
    r"\小学-六年级-语文-《两小儿辩日》-梁静-北京师范大学昌平附属学校4.docx"
)
_DEFAULT_DOCX_AQ = Path("/mnt/c/Users/roywa/Desktop/【3.0版本】2402-《阿Q正传》教学设计-陈玉华.docx")
_WIN_DOCX_AQ = Path(r"C:\Users\roywa\Desktop\【3.0版本】2402-《阿Q正传》教学设计-陈玉华.docx")


def _resolve_fixture(env_name: str, *candidates: Path) -> Path | None:
    override = os.environ.get(env_name, "").strip()
    paths = [Path(override)] if override else []
    paths.extend(candidates)
    for path in paths:
        if path.is_file():
            return path
    return None


def _make_png_bytes(width: int = 1280, height: int = 960) -> bytes:
    # High-entropy pixels keep PNG size above the shrink budget.
    image = Image.frombytes("RGB", (width, height), os.urandom(width * height * 3))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", compress_level=0)
    return buffer.getvalue()


def _make_pdf(path: Path, text: str = "Showcase cover fixture") -> None:
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.draw_rect(fitz.Rect(40, 40, 555, 400), color=(0.1, 0.2, 0.5), fill=(0.2, 0.4, 0.7))
    page.insert_text((72, 120), text, fontsize=28, color=(1, 1, 1))
    document.save(path)
    document.close()


def test_office_suffix_includes_pptx() -> None:
    """PPTX must go through LibreOffice before cover rasterize."""
    assert office_suffix_needs_pdf(".pptx")
    assert office_suffix_needs_pdf(".docx")
    assert not office_suffix_needs_pdf(".pdf")


def test_attachment_key_in_post_scope() -> None:
    """Accept only keys under the post's showcase/posts/{id}/ prefix."""
    post_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert attachment_key_in_post_scope(
        post_id,
        f"showcase/posts/{post_id}/attachment.docx",
    )
    assert not attachment_key_in_post_scope(
        post_id,
        "showcase/posts/other-id/attachment.docx",
    )
    assert not attachment_key_in_post_scope(post_id, "")


def test_shrink_png_bytes_fits_budget() -> None:
    """Downscale cover PNGs until they fit the byte and pixel budgets."""
    huge = _make_png_bytes()
    assert len(huge) > 100_000
    shrunk = shrink_png_bytes(huge, max_bytes=100_000)
    assert shrunk.startswith(_PNG_MAGIC)
    assert len(shrunk) <= 100_000
    with Image.open(io.BytesIO(shrunk)) as image:
        assert max(image.size) <= 960
    # Default budget path still accepts already-small PNG magic payloads.
    under = shrink_png_bytes(shrunk, max_bytes=THUMBNAIL_MAX_BYTES)
    assert under.startswith(_PNG_MAGIC)
    assert len(under) <= THUMBNAIL_MAX_BYTES


def _mean_luminance(png: bytes) -> float:
    """Average channel luminance used to reject blank cover renders."""
    with Image.open(io.BytesIO(png)) as image:
        rgb = image.convert("RGB")
        means = ImageStat.Stat(rgb).mean
        return sum(means) / len(means)


def test_render_pdf_first_page_without_soffice(tmp_path: Path) -> None:
    """Rasterize PDF page 1 via PyMuPDF without LibreOffice."""
    pdf_path = tmp_path / "page.pdf"
    _make_pdf(pdf_path)
    png = render_document_cover_png(pdf_path, tmp_path / "work")
    assert png.startswith(_PNG_MAGIC)
    assert len(png) <= THUMBNAIL_MAX_BYTES
    assert 5 < _mean_luminance(png) < 250


@pytest.mark.asyncio
async def test_generate_aborts_on_stale_attachment_key() -> None:
    """Skip download/upload when the post attachment key no longer matches."""
    post_id = "11111111-2222-3333-4444-555555555555"
    stale_key = f"showcase/posts/{post_id}/attachment.docx"
    current_key = f"showcase/posts/{post_id}/attachment.pdf"
    post = MagicMock()
    post.case_type = "teaching_design"
    post.spec = {"attachment_path": current_key}

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = post
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None

    with (
        patch(
            "services.showcase.covers.generate.acquire_cover_lock",
            return_value="token",
        ),
        patch("services.showcase.covers.generate.release_cover_lock") as release,
        patch(
            "services.showcase.covers.generate.rls_async_session",
            return_value=session,
        ),
        patch(
            "services.showcase.covers.generate.mark_cover_job_running",
            new_callable=AsyncMock,
        ),
        patch(
            "services.showcase.covers.generate.mark_cover_job_failed",
            new_callable=AsyncMock,
        ),
        patch("services.showcase.covers.generate.download_to_path_sync") as download,
        patch("services.showcase.covers.generate.put_bytes_sync") as put,
        patch(
            "services.showcase.covers.generate.publish_showcase_cover_event",
            new_callable=AsyncMock,
        ) as publish,
    ):
        ok = await generate_showcase_cover(
            post_id=post_id,
            user_id=1,
            attachment_key=stale_key,
            organization_id=None,
            author_id=1,
        )
    assert ok is False
    download.assert_not_called()
    put.assert_not_called()
    release.assert_called_once_with(post_id, "token")
    publish.assert_awaited()
    stale_await = publish.await_args
    assert stale_await is not None
    assert stale_await.args[1] == "cover_fail"


@pytest.mark.asyncio
async def test_generate_refuses_out_of_scope_key() -> None:
    """Emit cover_fail when attachment_key is outside the post prefix."""
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    with (
        patch(
            "services.showcase.covers.generate.publish_showcase_cover_event",
            new_callable=AsyncMock,
        ) as publish,
        patch(
            "services.showcase.covers.generate.mark_cover_job_failed",
            new_callable=AsyncMock,
        ),
        patch(
            "services.showcase.covers.generate.rls_async_session",
            return_value=session,
        ),
    ):
        ok = await generate_showcase_cover(
            post_id="11111111-2222-3333-4444-555555555555",
            user_id=1,
            attachment_key="showcase/posts/other/attachment.docx",
        )
    assert ok is False
    publish.assert_awaited()
    scope_await = publish.await_args
    assert scope_await is not None
    assert scope_await.args[1] == "cover_fail"


@pytest.mark.asyncio
async def test_generate_persists_preview_pdf_for_docx(tmp_path: Path) -> None:
    """DOCX cover jobs upload LO PDF as preview.pdf (same as PPTX) for pdf.js."""
    post_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    attachment_key = f"showcase/posts/{post_id}/attachment.docx"
    pdf_path = tmp_path / "converted.pdf"
    _make_pdf(pdf_path)
    png_bytes = _make_png_bytes(64, 64)

    post = MagicMock()
    post.case_type = "teaching_design"
    post.author_id = 7
    post.spec = {"attachment_path": attachment_key}
    post.thumbnail_path = None

    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = post
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None

    def _fake_download(_key: str, dest: Path) -> bool:
        dest.write_bytes(b"PK\x03\x04fake-docx")
        return True

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
            "services.showcase.covers.generate.resolve_cover_pdf_path",
            return_value=pdf_path,
        ),
        patch(
            "services.showcase.covers.generate.render_pdf_first_page_png",
            return_value=png_bytes,
        ),
        patch(
            "services.showcase.covers.generate.shrink_png_bytes",
            return_value=png_bytes,
        ),
        patch("services.showcase.covers.generate.put_bytes_sync") as put,
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
            side_effect=lambda key: f"/assets/{key}",
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
        ) as mark_ok,
        patch(
            "services.showcase.covers.generate.mark_cover_job_failed",
            new_callable=AsyncMock,
        ),
    ):
        ok = await generate_showcase_cover(
            post_id=post_id,
            user_id=1,
            attachment_key=attachment_key,
            organization_id=None,
            author_id=7,
        )

    assert ok is True
    mark_ok.assert_awaited()
    put_keys = [call.args[0] for call in put.call_args_list]
    assert f"showcase/posts/{post_id}/thumbnail.png" in put_keys
    assert f"showcase/posts/{post_id}/preview.pdf" in put_keys
    assert post.spec.get("preview_path") == f"showcase/posts/{post_id}/preview.pdf"
    ready = publish.await_args
    assert ready is not None
    assert ready.args[1] == "cover_ready"
    assert ready.kwargs.get("preview_url") == f"/assets/showcase/posts/{post_id}/preview.pdf"


def _png_non_blank(png: bytes) -> None:
    assert png.startswith(_PNG_MAGIC)
    assert len(png) <= THUMBNAIL_MAX_BYTES
    assert 5 < _mean_luminance(png) < 250


@pytest.mark.skipif(
    resolve_soffice_path() is None,
    reason="LibreOffice (soffice) not installed",
)
@pytest.mark.skipif(
    _resolve_fixture("SHOWCASE_REAL_DOCX_2", _DEFAULT_DOCX_LIANG, _WIN_DOCX_LIANG) is None,
    reason="Set SHOWCASE_REAL_DOCX_2 or place 两小儿辩日 DOCX on Desktop",
)
def test_render_real_docx_liang_er_bian_ri(tmp_path: Path) -> None:
    """Optional soffice cover render for the 两小儿辩日 Desktop fixture."""
    source = _resolve_fixture(
        "SHOWCASE_REAL_DOCX_2",
        _DEFAULT_DOCX_LIANG,
        _WIN_DOCX_LIANG,
    )
    assert source is not None
    work = tmp_path / "lo"
    work.mkdir()
    png = render_document_cover_png(source, work)
    _png_non_blank(png)


@pytest.mark.skipif(
    resolve_soffice_path() is None,
    reason="LibreOffice (soffice) not installed",
)
@pytest.mark.skipif(
    _resolve_fixture("SHOWCASE_REAL_DOCX", _DEFAULT_DOCX_AQ, _WIN_DOCX_AQ) is None,
    reason="Set SHOWCASE_REAL_DOCX or place 阿Q正传 DOCX on Desktop",
)
def test_render_real_docx_aq_zheng_zhuan(tmp_path: Path) -> None:
    """Optional soffice cover render for the 阿Q正传 Desktop fixture."""
    source = _resolve_fixture("SHOWCASE_REAL_DOCX", _DEFAULT_DOCX_AQ, _WIN_DOCX_AQ)
    assert source is not None
    work = tmp_path / "lo"
    work.mkdir()
    png = render_document_cover_png(source, work)
    _png_non_blank(png)
