"""Unit tests for Showcase cover job manifesto helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from services.showcase.covers.job_manifest import (
    COVER_JOB_FAILED,
    COVER_JOB_QUEUED,
    COVER_JOB_RUNNING,
    COVER_JOB_SUCCEEDED,
    IN_FLIGHT_STALE_SECONDS,
    cover_job_public_payload,
    cover_reason_is_retryable,
    job_is_in_flight,
    job_is_succeeded,
)
from services.showcase.media_status import (
    MEDIA_STATUS_CONVERSION_FAILED,
    MEDIA_STATUS_CONVERTING_PREVIEW,
    MEDIA_STATUS_COVER_READY,
    resolve_showcase_media_status,
)


def test_cover_reason_retryable_classification() -> None:
    """Permanent input errors must not Celery-retry."""
    assert cover_reason_is_retryable("download_failed") is True
    assert cover_reason_is_retryable("soft_time_limit") is True
    assert cover_reason_is_retryable("post_missing") is False
    assert cover_reason_is_retryable("stale_attachment_key") is False
    assert cover_reason_is_retryable("unsupported_suffix=.xyz") is False
    assert cover_reason_is_retryable("enqueue_failed:broker down") is False


def test_job_status_helpers() -> None:
    """In-flight vs cold-succeeded helpers."""
    assert job_is_in_flight(COVER_JOB_QUEUED) is True
    assert job_is_in_flight(COVER_JOB_RUNNING) is True
    assert job_is_in_flight(COVER_JOB_FAILED) is False
    assert job_is_succeeded(COVER_JOB_SUCCEEDED) is True
    assert job_is_succeeded(COVER_JOB_FAILED) is False
    fresh = datetime.now(UTC)
    assert job_is_in_flight(COVER_JOB_RUNNING, fresh) is True
    stale = fresh - timedelta(seconds=IN_FLIGHT_STALE_SECONDS + 1)
    assert job_is_in_flight(COVER_JOB_RUNNING, stale) is False


def test_cover_job_public_payload_none() -> None:
    """No job yields None payload."""
    assert cover_job_public_payload(None) is None


def test_media_status_prefers_queued_job() -> None:
    """Queued/running manifesto forces converting even when paths exist."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path="showcase/posts/a/thumbnail.png",
            spec={
                "attachment_path": "showcase/posts/a/attachment.docx",
                "preview_path": "showcase/posts/a/preview.pdf",
            },
            cover_job_status=COVER_JOB_QUEUED,
        )
        == MEDIA_STATUS_CONVERTING_PREVIEW
    )
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path="showcase/posts/a/thumbnail.png",
            spec={
                "attachment_path": "showcase/posts/a/attachment.docx",
                "preview_path": "showcase/posts/a/preview.pdf",
            },
            cover_job_status=COVER_JOB_RUNNING,
        )
        == MEDIA_STATUS_CONVERTING_PREVIEW
    )


def test_media_status_prefers_failed_job() -> None:
    """Failed manifesto surfaces conversion_failed from cold data."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path=None,
            spec={"attachment_path": "showcase/posts/a/attachment.pptx"},
            cover_job_status=COVER_JOB_FAILED,
        )
        == MEDIA_STATUS_CONVERSION_FAILED
    )


def test_media_status_succeeded_uses_paths_only() -> None:
    """Succeeded job derives readiness from stored paths (no COS probe)."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path="showcase/posts/a/thumbnail.png",
            spec={
                "attachment_path": "showcase/posts/a/attachment.docx",
                "preview_path": "showcase/posts/a/preview.pdf",
            },
            cover_job_status=COVER_JOB_SUCCEEDED,
        )
        == MEDIA_STATUS_COVER_READY
    )


def test_media_status_without_job_status_uses_paths() -> None:
    """Stale in-flight ignored at format layer → path-derived cover_ready."""
    assert (
        resolve_showcase_media_status(
            case_type="teaching_design",
            thumbnail_path="showcase/posts/a/thumbnail.png",
            spec={
                "attachment_path": "showcase/posts/a/attachment.docx",
                "preview_path": "showcase/posts/a/preview.pdf",
            },
            cover_job_status=None,
        )
        == MEDIA_STATUS_COVER_READY
    )
