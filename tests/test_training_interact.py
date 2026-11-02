"""Slide interaction payload stays on the course step and drops unknown modes."""

from services.features.training.courses.diagram_spec import clean_diagram_spec
from services.features.training.courses.interact import clean_interact
from services.features.training.courses.repository import _step_payload
from services.features.training.courses.serialize import snapshot_step_payload


def test_clean_interact_keeps_a_quiz_and_drops_a_bad_mode() -> None:
    """A three-choice quiz survives cleaning. An unknown mode is removed."""
    kept = clean_interact(
        {
            "mode": "quiz",
            "read_order": ["n1", ""],
            "blanks": [{"node_id": "n1", "answer": "根"}],
            "quizzes": [
                {
                    "node_id": "n1",
                    "prompt": "这是什么",
                    "choices": [
                        {"id": "a", "label": "根", "correct": True},
                        {"id": "b", "label": "叶", "correct": False},
                    ],
                }
            ],
        }
    )
    assert kept is not None
    assert kept["mode"] == "quiz"
    assert kept["read_order"] == ["n1"]
    assert kept["blanks"] == [{"node_id": "n1", "answer": "根"}]
    choices = kept["quizzes"][0]["choices"]
    assert [row["id"] for row in choices] == ["a", "b", "c"]
    assert choices[0]["correct"] is True
    assert choices[2]["label"] == ""
    assert kept["sequence_saved"] is False
    saved = clean_interact({"mode": "read", "read_order": ["a"], "sequence_saved": True, "play_index": 4})
    assert saved is not None
    assert saved["sequence_saved"] is True
    assert "play_index" not in saved
    drag = clean_interact(
        {
            "mode": "drag",
            "blanks": [{"node_id": "n1", "answer": "根", "hint": "想想根的位置"}],
            "sequence_saved": True,
        }
    )
    assert drag is not None
    assert drag["sequence_saved"] is True
    assert drag["blanks"] == [{"node_id": "n1", "answer": "根", "hint": "想想根的位置"}]
    assert saved["node_extras"] == []
    extras = clean_interact(
        {
            "mode": "read",
            "node_extras": [
                {"node_id": "n1", "kinds": ["note", "nope", "image", "note"]},
            ],
        }
    )
    assert extras is not None
    assert extras["node_extras"] == [{"node_id": "n1", "kinds": ["note", "image"]}]
    linked = clean_interact(
        {
            "mode": "read",
            "node_extras": [
                {"node_id": "n1", "kinds": ["video", "nope"], "vod_media_id": "vid-1"},
            ],
        }
    )
    assert linked is not None
    assert linked["node_extras"] == [
        {"node_id": "n1", "kinds": ["video"], "vod_media_id": "vid-1"},
    ]
    assert clean_interact({"mode": "dance"}) is None
    assert clean_interact(None) is None


def test_step_payload_and_snapshot_keep_interact() -> None:
    """Autosave and the live snapshot both carry the interaction block."""
    payload = _step_payload(
        {
            "type": "canvas",
            "page_key": "canvas",
            "interact": {"mode": "read", "read_order": ["a"]},
        }
    )
    assert payload["interact"]["mode"] == "read"
    assert payload["interact"]["read_order"] == ["a"]
    assert payload["interact"]["quizzes"] == []
    snapshot = snapshot_step_payload({"type": "canvas", "interact": payload["interact"]})
    assert snapshot["interact"]["mode"] == "read"
    assert snapshot_step_payload({"type": "page"}).get("interact") is None


def test_step_payload_keeps_diagram_spec() -> None:
    """Canvas nodes stay on the course so guided-reading ids survive reload."""
    spec = {"type": "mindmap", "topic": "AI", "nodes": [{"id": "topic", "text": "AI"}]}
    payload = _step_payload(
        {
            "type": "canvas",
            "page_key": "canvas",
            "diagram_spec": spec,
            "interact": {"mode": "read", "read_order": ["topic"], "sequence_saved": True},
        }
    )
    assert payload["diagram_spec"]["topic"] == "AI"
    assert payload["diagram_spec"]["nodes"][0]["id"] == "topic"
    assert "llm_results" not in (clean_diagram_spec({**spec, "llm_results": {"x": 1}}) or {})
    snapshot = snapshot_step_payload({"type": "canvas", "diagram_spec": payload["diagram_spec"]})
    assert snapshot["diagram_spec"]["topic"] == "AI"
    assert clean_diagram_spec(None) is None
    assert clean_diagram_spec([]) is None
