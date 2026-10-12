"""Session payload for qwen3.8 live translation subtitles."""

from services.features.live_translate_bridge import (
    build_session_finish,
    build_translate_session_update,
    normalize_translate_target,
)


def test_session_update_is_text_only_qwen38() -> None:
    """Text subtitles must not send qwen3.5 audio or source-language fields."""
    payload = build_translate_session_update("uk")
    session = payload["session"]
    assert payload["type"] == "session.update"
    assert session == {
        "output_modalities": ["text"],
        "translation": {"language": "uk"},
    }


def test_session_finish_notifies_upstream() -> None:
    """Closing the caption session asks DashScope to flush the last utterance."""
    payload = build_session_finish()
    assert payload["type"] == "session.finish"
    assert str(payload["event_id"]).startswith("evt_")


def test_normalize_translate_target_rejects_blank_and_punctuation() -> None:
    """A target update only forwards a short alphabetic language code."""
    assert normalize_translate_target(" FR ") == "fr"
    assert normalize_translate_target("") == ""
    assert normalize_translate_target("zh-tw") == ""
    assert normalize_translate_target("x" * 17) == ""
