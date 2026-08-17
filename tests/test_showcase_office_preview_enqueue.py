"""Unit tests for Office preview backfill enqueue helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.showcase.covers.enqueue import (
    enqueue_missing_office_preview,
    enqueue_teaching_design_cover,
    office_attachment_needs_preview,
)
from services.showcase.covers.job_manifest import cover_job_blocks_auto_enqueue_sync
from tasks import showcase_cover_tasks


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
    with (
        patch(
            "services.showcase.covers.enqueue.cover_job_blocks_auto_enqueue_sync",
            return_value=False,
        ),
        patch("services.showcase.covers.enqueue.enqueue_teaching_design_cover") as enqueue,
    ):
        enqueue.return_value = True
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


def test_enqueue_missing_office_preview_skips_cold_succeeded() -> None:
    """Automatic backfill must not re-queue a cold-succeeded manifesto."""
    with (
        patch(
            "services.showcase.covers.enqueue.cover_job_blocks_auto_enqueue_sync",
            return_value=True,
        ),
        patch("services.showcase.covers.enqueue.enqueue_teaching_design_cover") as enqueue,
    ):
        ok = enqueue_missing_office_preview(
            post_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            case_type="teaching_design",
            spec={"attachment_path": "showcase/posts/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/a.pptx"},
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
        patch(
            "services.showcase.covers.enqueue.cover_job_blocks_auto_enqueue_sync",
            return_value=False,
        ),
        patch("services.showcase.covers.enqueue.try_claim_cover_enqueue", side_effect=[True, False]),
        patch("services.showcase.covers.enqueue.mark_cover_job_queued_sync", return_value=True),
        patch("services.showcase.covers.enqueue.clear_cover_last_event_sync"),
        patch("services.showcase.covers.enqueue.celery_app") as celery_app,
    ):
        celery_app.send_task = MagicMock(return_value=MagicMock(id="task-1"))
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


def test_enqueue_force_can_queue_after_succeeded() -> None:
    """Admin force refresh bypasses cold-succeeded auto-skip."""
    post_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    attachment = f"showcase/posts/{post_id}/attachment.docx"
    with (
        patch("services.showcase.covers.enqueue.showcase_server_covers_enabled", return_value=True),
        patch(
            "services.showcase.covers.enqueue.get_cover_job_snapshot_sync",
            return_value={"status": "succeeded", "attachment_key": attachment},
        ),
        patch("services.showcase.covers.enqueue.try_claim_cover_enqueue") as claim,
        patch("services.showcase.covers.enqueue.mark_cover_job_queued_sync", return_value=True) as queued,
        patch("services.showcase.covers.enqueue.clear_cover_last_event_sync"),
        patch("services.showcase.covers.enqueue.celery_app") as celery_app,
    ):
        celery_app.send_task = MagicMock(return_value=MagicMock(id="task-force"))
        ok = enqueue_teaching_design_cover(
            post_id=post_id,
            user_id=1,
            attachment_key=attachment,
            case_type="teaching_design",
            author_id=1,
            force=True,
        )
    assert ok is True
    celery_app.send_task.assert_called_once()
    claim.assert_not_called()
    assert queued.call_args.kwargs.get("force") is True


def test_enqueue_force_ignores_dedupe_lock() -> None:
    """Force refresh must send_task even when enqueue claim would deny."""
    post_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    attachment = f"showcase/posts/{post_id}/attachment.docx"
    with (
        patch("services.showcase.covers.enqueue.showcase_server_covers_enabled", return_value=True),
        patch(
            "services.showcase.covers.enqueue.get_cover_job_snapshot_sync",
            return_value={"status": "failed", "attachment_key": attachment},
        ),
        patch("services.showcase.covers.enqueue.try_claim_cover_enqueue", return_value=False),
        patch("services.showcase.covers.enqueue.mark_cover_job_queued_sync", return_value=True),
        patch("services.showcase.covers.enqueue.clear_cover_last_event_sync"),
        patch("services.showcase.covers.enqueue.celery_app") as celery_app,
    ):
        celery_app.send_task = MagicMock(return_value=MagicMock(id="task-force-2"))
        ok = enqueue_teaching_design_cover(
            post_id=post_id,
            user_id=1,
            attachment_key=attachment,
            case_type="teaching_design",
            author_id=1,
            force=True,
        )
    assert ok is True
    celery_app.send_task.assert_called_once()


def test_blocks_auto_enqueue_when_in_flight() -> None:
    """GET-post / cover-stream must not send a second task while one is live."""
    attachment = "showcase/posts/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/attachment.docx"
    replacement = "showcase/posts/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/attachment.pptx"
    with patch(
        "services.showcase.covers.job_manifest.get_cover_job_snapshot_sync",
        return_value={
            "status": "running",
            "attachment_key": attachment,
            "updated_at": datetime.now(UTC),
        },
    ):
        assert (
            cover_job_blocks_auto_enqueue_sync(
                post_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                attachment_key=attachment,
                user_id=1,
            )
            is True
        )
        assert (
            cover_job_blocks_auto_enqueue_sync(
                post_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                attachment_key=replacement,
                user_id=1,
            )
            is False
        )


def test_enqueue_skips_send_task_when_in_flight() -> None:
    """Auto-enqueue after the 90s Redis NX window must not start a second worker."""
    post_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    attachment = f"showcase/posts/{post_id}/attachment.docx"
    with (
        patch("services.showcase.covers.enqueue.showcase_server_covers_enabled", return_value=True),
        patch(
            "services.showcase.covers.enqueue.cover_job_blocks_auto_enqueue_sync",
            return_value=True,
        ),
        patch("services.showcase.covers.enqueue.try_claim_cover_enqueue") as claim,
        patch("services.showcase.covers.enqueue.celery_app") as celery_app,
    ):
        celery_app.send_task = MagicMock()
        ok = enqueue_teaching_design_cover(
            post_id=post_id,
            user_id=1,
            attachment_key=attachment,
            case_type="teaching_design",
            author_id=1,
        )
    assert ok is False
    claim.assert_not_called()
    celery_app.send_task.assert_not_called()


def test_cover_task_closes_async_redis() -> None:
    """Prefork workers must close the loop-bound Redis client after asyncio.run."""
    src = Path(showcase_cover_tasks.__file__).read_text(encoding="utf-8")
    assert "close_async_redis" in src
    assert "def _run_and_close" in src
