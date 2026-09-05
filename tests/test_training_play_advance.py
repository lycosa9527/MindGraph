"""Prev/next walks mark clicks, then course slides."""

from routers.api.training_play_routes import _step_extras
from services.features.training.payloads import command_etag, snapshot_from_session
from services.features.training.play_advance import mark_span, resolve_play_cursor


def test_mark_span_reads_overlays_and_stored_count() -> None:
    """Highest overlay click wins over a stale stored count."""
    current, highest = mark_span(
        {
            "mark_step": 2,
            "mark_steps": 2,
            "overlays": [{"kind": "text", "step": 4}],
        }
    )
    assert current == 2
    assert highest == 4


def test_resolve_play_cursor_stays_on_slide_until_marks_done() -> None:
    """Next eats remaining clicks before changing slides."""
    steps = [
        {"mark_step": 1, "mark_steps": 3, "overlays": [{"step": 2}, {"step": 3}]},
        {"mark_step": 1, "mark_steps": 1, "overlays": []},
    ]
    live = {"mark_step": 1, "mark_steps": 3, "overlays": [{"step": 2}, {"step": 3}]}
    assert resolve_play_cursor(steps, 0, live, 1) == (0, 2)
    live["mark_step"] = 3
    assert resolve_play_cursor(steps, 0, live, 1) == (1, 1)
    assert resolve_play_cursor(steps, 1, steps[1], -1) == (0, 3)


def test_command_etag_is_per_session() -> None:
    """Restarts at seq 1 must not share the previous session ETag."""
    assert command_etag("sess-1", 4) == '"sess-1:4"'
    assert command_etag(None, 0) == '"none:0"'


def test_step_extras_reenable_pull_after_free() -> None:
    """Next / play always pull teachers back, even if the slide was authored free."""
    extras = _step_extras(
        "course-1",
        0,
        {"type": "page", "page_key": "auth", "pull_users": False},
    )
    assert extras["pull_users"] is True
    assert extras["diagram_type"] is None


def test_snapshot_exposes_free_release() -> None:
    """Session-level pull_users false is visible to clients."""
    body = snapshot_from_session(
        {
            "state": "live",
            "session_id": "s",
            "org_id": 1,
            "seq": 2,
            "instructor_id": 9,
            "pull_users": False,
            "step_count": 4,
        }
    )
    assert body["pull_users"] is False
    assert body["step_count"] == 4
