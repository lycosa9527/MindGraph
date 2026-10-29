"""Share a saved canvas diagram into a seminar chat line."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.mindmate_seminar.diagram_library import canvas_diagram_preview_payload
from services.features.mindmate_seminar.message_history import PersistedCollabMessage
from services.features.mindmate_seminar.seminar_message import SeminarMessageOutcome
from services.features.mindmate_seminar.share_canvas import (
    canvas_share_message,
    normalize_canvas_diagram_id,
    post_canvas_diagram_share,
)

_DIAGRAM_ID = "a43ea2be-e020-47e2-9db6-a8bc9f554362"


def test_normalize_canvas_diagram_id() -> None:
    """Only a library uuid is accepted."""
    assert normalize_canvas_diagram_id(_DIAGRAM_ID.upper()) == _DIAGRAM_ID
    assert normalize_canvas_diagram_id("deadbeef") is None
    assert normalize_canvas_diagram_id("") is None


def test_canvas_share_message_embeds_library_id_and_preview() -> None:
    """The seminar line keeps a title, a preview image, and the library id."""
    text = canvas_share_message(
        title="  Lesson [one]  ",
        diagram_id=_DIAGRAM_ID,
        image_url="https://example.test/preview.png",
    )
    assert text.splitlines()[0] == "Lesson one"
    assert "https://example.test/preview.png" in text
    assert f"<!-- mg-diagram-id:{_DIAGRAM_ID} -->" in text


def test_canvas_share_message_keeps_an_optional_note() -> None:
    """A share can carry a short note ahead of the diagram title."""
    text = canvas_share_message(
        title="Lesson",
        diagram_id=_DIAGRAM_ID,
        image_url="",
        note="  请大家看这张图 <!--x-->  ",
    )
    assert text.splitlines()[0] == "请大家看这张图 x"
    assert "Lesson" in text


def test_canvas_diagram_preview_payload_keeps_spec() -> None:
    """The bubble preview carries the library spec, type, and title."""
    payload, error = canvas_diagram_preview_payload(
        {
            "title": "  尝试分析  ",
            "diagram_type": "mind_map",
            "spec": {"topic": "尝试分析", "children": [{"text": "分支"}]},
        },
        _DIAGRAM_ID,
    )
    assert error == ""
    assert payload is not None
    assert payload["diagram_id"] == _DIAGRAM_ID
    assert payload["title"] == "尝试分析"
    assert payload["diagram_type"] == "mind_map"
    assert payload["spec"]["topic"] == "尝试分析"


def test_canvas_diagram_preview_payload_rejects_empty_spec() -> None:
    """A library row without a spec cannot be drawn in the bubble."""
    payload, error = canvas_diagram_preview_payload(
        {"title": "空", "diagram_type": "mind_map", "spec": {}},
        _DIAGRAM_ID,
    )
    assert payload is None
    assert error == "no_spec"


def test_canvas_share_message_skips_unsafe_image_urls() -> None:
    """A non-http preview is omitted so the bubble cannot load an arbitrary scheme."""
    text = canvas_share_message(
        title="Map",
        diagram_id=_DIAGRAM_ID,
        image_url="javascript:alert(1)",
    )
    assert "javascript:" not in text
    assert f"mg-diagram-id:{_DIAGRAM_ID}" in text


@pytest.mark.asyncio
async def test_canvas_share_saves_through_the_seminar_message_writer() -> None:
    """A shared diagram is a REST chat line, not a second insert path."""
    session = MagicMock()
    session.id = "sess-1"
    session.code = "ABC-DEF"
    manager = MagicMock()
    manager.load_session_by_id = AsyncMock(return_value=session)
    manager.session_accepts_chat = AsyncMock(return_value=True)
    user = MagicMock()
    user.id = 4
    user.username = "Ada"
    saved = PersistedCollabMessage(3, 2, "2026-10-01T00:00:00+00:00")
    outcome = SeminarMessageOutcome(None, saved, "user", None)
    cache = MagicMock()
    cache.get_diagram = AsyncMock(return_value={"title": "Map"})
    with (
        patch(
            "services.features.mindmate_seminar.share_canvas.get_diagram_cache",
            return_value=cache,
        ),
        patch(
            "services.features.mindmate_seminar.share_canvas.get_mindmate_seminar_manager",
            return_value=manager,
        ),
        patch(
            "services.features.mindmate_seminar.share_canvas.user_may_share_canvas",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_seminar.share_canvas.send_seminar_message",
            AsyncMock(return_value=outcome),
        ) as send,
    ):
        payload, error = await post_canvas_diagram_share(
            "sess-1",
            _DIAGRAM_ID,
            user,
            image_url="https://example.test/preview.png",
        )
    assert error == ""
    assert payload is not None
    assert payload["message_id"] == 3
    send.assert_awaited_once()
    assert send.await_args is not None
    assert send.await_args.kwargs["kind"] == "chat"
    assert send.await_args.kwargs["to_mindmate"] is False
    manager.persist_message.assert_not_called()
