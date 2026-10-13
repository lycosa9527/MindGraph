"""Diagram translate accepts prompt-registry languages, including Norwegian."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from models.requests.requests_canvas_translate import (
    TranslateDiagramLabelsRequest,
    TranslateNodeLabelRequest,
    canvas_translate_language_name,
)


def test_norwegian_is_a_diagram_translate_target() -> None:
    """The interface locale `no` is sent through as Norwegian."""
    body = TranslateDiagramLabelsRequest.model_validate(
        {
            "items": [{"item_id": "n1", "text": "Light"}],
            "target_language": "no",
            "ui_locale": "no",
        }
    )
    assert body.target_language == "no"
    assert canvas_translate_language_name(body.target_language, body.ui_locale) == "Norwegian"


def test_bokmaal_alias_maps_to_norwegian() -> None:
    """Bokmål and Nynorsk codes share the Norwegian prompt language."""
    body = TranslateNodeLabelRequest.model_validate({"text": "Light", "target_language": "NB"})
    assert body.target_language == "no"


def test_traditional_chinese_ui_uses_zh_with_a_traditional_name() -> None:
    """Traditional Chinese UI still uses target code zh and a traditional prompt name."""
    body = TranslateNodeLabelRequest.model_validate({"text": "光", "target_language": "zh-tw"})
    assert body.target_language == "zh"
    assert canvas_translate_language_name("zh", "zh-tw") == "Traditional Chinese"


def test_unknown_target_is_rejected() -> None:
    """Codes outside the prompt registry are not translation targets."""
    with pytest.raises(ValidationError):
        TranslateNodeLabelRequest.model_validate({"text": "Light", "target_language": "zzz"})
