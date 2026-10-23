"""Share a saved canvas diagram into a seminar chat line."""

from __future__ import annotations

from services.features.mindmate_collab.diagram_library import canvas_diagram_preview_payload
from services.features.mindmate_collab.share_canvas import (
    canvas_share_message,
    normalize_canvas_diagram_id,
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
