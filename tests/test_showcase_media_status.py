"""Unit tests for Showcase media_status derivation."""

from __future__ import annotations

from services.showcase.media_status import (
    MEDIA_STATUS_AWAITING_UPLOAD,
    MEDIA_STATUS_CONVERSION_FAILED,
    MEDIA_STATUS_CONVERTING_PREVIEW,
    MEDIA_STATUS_COVER_READY,
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


def test_teaching_office_conversion_failed() -> None:
    """cover_fail while Office preview is missing surfaces conversion_failed."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path=None,
            spec={"attachment_path": "showcase/posts/a/attachment.pptx"},
            cover_failed=True,
        )
        == MEDIA_STATUS_CONVERSION_FAILED
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
    """Thumbnail plus preview (or native PDF) means cover_ready."""
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
