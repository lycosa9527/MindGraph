"""Unit tests for Showcase media_status derivation."""

from __future__ import annotations

from services.showcase.media_status import (
    MEDIA_STATUS_AWAITING_UPLOAD,
    MEDIA_STATUS_CONVERTING_PREVIEW,
    MEDIA_STATUS_COVER_FAILED,
    MEDIA_STATUS_COVER_READY,
    MEDIA_STATUS_GENERATING_COVER,
    MEDIA_STATUS_PREVIEW_FAILED,
    MEDIA_STATUS_PREVIEW_READY,
    MEDIA_STATUS_READY,
    cover_event_indicates_failure,
    resolve_showcase_media_status,
)


def test_cover_event_indicates_failure() -> None:
    """Parse Redis last-event payloads for cover_fail."""
    assert cover_event_indicates_failure(None) is False
    assert cover_event_indicates_failure("{") is False
    assert cover_event_indicates_failure('{"type":"cover_ready"}') is False
    assert cover_event_indicates_failure('{"type":"cover_fail","reason":"x"}') is True


def test_teaching_awaiting_upload() -> None:
    """Teaching design without attachment waits for upload."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path=None,
            spec={"type": "teaching_design"},
        )
        == MEDIA_STATUS_AWAITING_UPLOAD
    )


def test_teaching_converting_office_preview() -> None:
    """Office attachment without preview_path is converting."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path=None,
            spec={"attachment_path": "showcase/posts/a/attachment.docx"},
        )
        == MEDIA_STATUS_CONVERTING_PREVIEW
    )


def test_teaching_office_preview_failed() -> None:
    """cover_fail while Office preview is missing surfaces preview_failed."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path=None,
            spec={"attachment_path": "showcase/posts/a/attachment.pptx"},
            cover_failed=True,
        )
        == MEDIA_STATUS_PREVIEW_FAILED
    )


def test_teaching_preview_failed_from_cover_job_status() -> None:
    """Cold manifesto failed status maps to preview_failed without Redis."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path=None,
            spec={"attachment_path": "showcase/posts/a/attachment.docx"},
            cover_job_status="failed",
        )
        == MEDIA_STATUS_PREVIEW_FAILED
    )


def test_teaching_cover_failed_when_preview_ok() -> None:
    """Failed job with preview available but no thumb is cover_failed."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path=None,
            spec={
                "attachment_path": "showcase/posts/a/attachment.docx",
                "preview_path": "showcase/posts/a/preview.pdf",
            },
            cover_job_status="failed",
        )
        == MEDIA_STATUS_COVER_FAILED
    )
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path=None,
            spec={"attachment_path": "showcase/posts/a/attachment.pdf"},
            cover_failed=True,
        )
        == MEDIA_STATUS_COVER_FAILED
    )


def test_teaching_failed_refresh_keeps_cover_ready_when_paths_remain() -> None:
    """Later failed refresh still reports cover_ready if both paths remain."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path="showcase/posts/a/thumbnail.png",
            spec={
                "attachment_path": "showcase/posts/a/attachment.docx",
                "preview_path": "showcase/posts/a/preview.pdf",
            },
            cover_job_status="failed",
        )
        == MEDIA_STATUS_COVER_READY
    )


def test_teaching_in_flight_office_converting_preview() -> None:
    """Queued/running Office without preview_path is converting_preview."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path=None,
            spec={"attachment_path": "showcase/posts/a/attachment.docx"},
            cover_job_status="queued",
        )
        == MEDIA_STATUS_CONVERTING_PREVIEW
    )


def test_teaching_in_flight_native_pdf_generating_cover() -> None:
    """Queued/running native PDF (preview satisfied) is generating_cover."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path=None,
            spec={"attachment_path": "showcase/posts/a/attachment.pdf"},
            cover_job_status="running",
        )
        == MEDIA_STATUS_GENERATING_COVER
    )


def test_teaching_preview_ready_native_pdf() -> None:
    """Native PDF is previewable before cover generation finishes."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path=None,
            spec={"attachment_path": "showcase/posts/a/attachment.pdf"},
        )
        == MEDIA_STATUS_PREVIEW_READY
    )


def test_teaching_preview_ready_with_preview_path() -> None:
    """Office preview_path without thumbnail is preview_ready."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path=None,
            spec={
                "attachment_path": "showcase/posts/a/attachment.docx",
                "preview_path": "showcase/posts/a/preview.pdf",
            },
        )
        == MEDIA_STATUS_PREVIEW_READY
    )


def test_teaching_cover_ready() -> None:
    """Thumbnail plus preview (or native PDF) means cover_ready (both ready)."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path="showcase/posts/a/thumbnail.png",
            spec={
                "attachment_path": "showcase/posts/a/attachment.docx",
                "preview_path": "showcase/posts/a/preview.pdf",
            },
        )
        == MEDIA_STATUS_COVER_READY
    )
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path="showcase/posts/a/thumbnail.png",
            spec={"attachment_path": "showcase/posts/a/attachment.pdf"},
        )
        == MEDIA_STATUS_COVER_READY
    )


def test_teaching_thumb_without_office_preview_still_converting() -> None:
    """Thumb-only Office posts stay converting until preview_path exists."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path="showcase/posts/a/thumbnail.png",
            spec={"attachment_path": "showcase/posts/a/attachment.docx"},
        )
        == MEDIA_STATUS_CONVERTING_PREVIEW
    )


def test_diagram_gallery_and_ready() -> None:
    """Diagram gallery pending vs complete statuses."""
    assert (
        resolve_showcase_media_status(
            case_type="diagram_case",
            thumbnail_path=None,
            spec={"gallery": [{"kind": "image", "pending": True}]},
        )
        == MEDIA_STATUS_AWAITING_UPLOAD
    )
    assert (
        resolve_showcase_media_status(
            case_type="diagram_case",
            thumbnail_path=None,
            spec={"gallery": [{"kind": "image", "path": "showcase/posts/a/g0.png"}]},
        )
        == MEDIA_STATUS_READY
    )
    assert (
        resolve_showcase_media_status(
            case_type="diagram_template",
            thumbnail_path="showcase/posts/a/thumbnail.png",
            spec={"gallery": [{"kind": "image", "path": "showcase/posts/a/g0.png"}]},
        )
        == MEDIA_STATUS_COVER_READY
    )
