"""Unit tests for Office preview backfill enqueue helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.showcase.covers.enqueue import (
    enqueue_missing_office_preview,
    enqueue_teaching_design_cover,
    office_attachment_needs_preview,
)


def test_office_attachment_needs_preview_for_pptx_without_path() -> None:
    """PPTX without preview_path must be flagged for LO PDF backfill."""
    key = office_attachment_needs_preview({"attachment_path": "showcase/posts/abc/attachment.pptx"})
    assert key == "showcase/posts/abc/attachment.pptx"


def test_office_attachment_needs_preview_skips_when_present() -> None:
    """Existing preview_path means no backfill."""
    assert (
        office_attachment_needs_preview(
            {
                "attachment_path": "showcase/posts/abc/attachment.docx",
                "preview_path": "showcase/posts/abc/preview.pdf",
            }
        )
        is None
    )


def test_office_attachment_needs_preview_skips_native_pdf() -> None:
    """Native PDF uses attachment_url; no separate preview object."""
    assert office_attachment_needs_preview({"attachment_path": "showcase/posts/abc/attachment.pdf"}) is None


def test_enqueue_missing_office_preview_calls_cover_job() -> None:
    """Backfill helper enqueues cover generation for Office without preview."""
    with patch("services.showcase.covers.enqueue.enqueue_teaching_design_cover") as enqueue:
        ok = enqueue_missing_office_preview(
            post_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            case_type="teaching_design",
            spec={"attachment_path": "showcase/posts/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/a.pptx"},
            author_id=9,
            organization_id=3,
            actor_user_id=1,
        )
    assert ok is True
    enqueue.assert_called_once()
    kwargs = enqueue.call_args.kwargs
    assert kwargs["post_id"] == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert kwargs["attachment_key"].endswith(".pptx")
    assert kwargs["author_id"] == 9
    assert kwargs["organization_id"] == 3
    assert kwargs["user_id"] == 1


def test_enqueue_missing_office_preview_noop_when_ready() -> None:
    """Do not enqueue when preview_path already exists."""
    with patch("services.showcase.covers.enqueue.enqueue_teaching_design_cover") as enqueue:
        ok = enqueue_missing_office_preview(
            post_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            case_type="teaching_design",
            spec={
                "attachment_path": "showcase/posts/x/a.docx",
                "preview_path": "showcase/posts/x/preview.pdf",
            },
            author_id=1,
        )
    assert ok is False
    enqueue.assert_not_called()


def test_enqueue_teaching_design_cover_dedupes_send_task() -> None:
    """Second enqueue for the same post must not call Celery again."""
    post_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    attachment = f"showcase/posts/{post_id}/attachment.docx"
    with (
        patch("services.showcase.covers.enqueue.showcase_server_covers_enabled", return_value=True),
        patch("services.showcase.covers.enqueue.try_claim_cover_enqueue", side_effect=[True, False]),
        patch("services.showcase.covers.enqueue.celery_app") as celery_app,
    ):
        celery_app.send_task = MagicMock()
        enqueue_teaching_design_cover(
            post_id=post_id,
            user_id=1,
            attachment_key=attachment,
            case_type="teaching_design",
            author_id=1,
        )
        enqueue_teaching_design_cover(
            post_id=post_id,
            user_id=1,
            attachment_key=attachment,
            case_type="teaching_design",
            author_id=1,
        )
    celery_app.send_task.assert_called_once()
