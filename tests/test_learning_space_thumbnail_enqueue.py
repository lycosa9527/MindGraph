"""Homework submit queues a Celery thumbnail and leaves a grace window for it."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from kombu.exceptions import OperationalError as BrokerOperationalError

from services.learning_space.thumbnail_enqueue import enqueue_submit_thumbnail
from services.learning_space.thumbnail_submit import (
    SUBMIT_THUMBNAIL_GRACE_SECONDS,
    SUBMIT_THUMBNAIL_LEASE_SECONDS,
    THUMB_PENDING,
    THUMB_RETRY_AT,
    THUMB_TOKEN,
    thumbnail_not_before,
    thumbnail_render_lease_active,
)
from tasks.learning_space_thumbnail_tasks import render_submit_thumbnail_task


def test_enqueue_sends_the_submission_and_token() -> None:
    """Submit hands Celery the row id and the pending token."""
    sent = MagicMock()
    sent.id = "task-1"
    with patch("services.learning_space.thumbnail_enqueue.celery_app") as celery:
        celery.send_task.return_value = sent
        assert enqueue_submit_thumbnail(12, "tok") is True
    celery.send_task.assert_called_once_with(
        "learning_space.render_submit_thumbnail",
        kwargs={"submission_id": 12, "token": "tok"},
        queue="default",
    )


def test_enqueue_keeps_the_submit_when_the_broker_is_down() -> None:
    """A broker error does not raise. The API sweep can still draw the row."""
    with patch("services.learning_space.thumbnail_enqueue.celery_app") as celery:
        celery.send_task.side_effect = BrokerOperationalError("redis down")
        assert enqueue_submit_thumbnail(12, "tok") is False


def test_enqueue_ignores_a_blank_token() -> None:
    """No Celery message when this submit has nothing to draw."""
    with patch("services.learning_space.thumbnail_enqueue.celery_app") as celery:
        assert enqueue_submit_thumbnail(12, "  ") is False
    celery.send_task.assert_not_called()


def test_submit_grace_is_not_a_render_lease() -> None:
    """The short stamp written at submit still lets the Celery job claim the row."""
    now = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
    snapshot = {
        THUMB_TOKEN: "tok",
        THUMB_PENDING: "tok",
        THUMB_RETRY_AT: thumbnail_not_before(now, SUBMIT_THUMBNAIL_GRACE_SECONDS),
        "spec": {"nodes": []},
    }
    assert thumbnail_render_lease_active(snapshot, now) is False
    claimed = dict(snapshot)
    claimed[THUMB_RETRY_AT] = thumbnail_not_before(now, SUBMIT_THUMBNAIL_LEASE_SECONDS)
    assert thumbnail_render_lease_active(claimed, now) is True


def test_task_module_registers_the_submit_thumbnail_name() -> None:
    """The worker banner must include the homework thumbnail task."""
    assert render_submit_thumbnail_task.name == "learning_space.render_submit_thumbnail"
