"""
Request model for canvas node label translation API.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from utils.prompt_output_languages import OUTPUT_LANGUAGE_ENGLISH_NAMES, is_prompt_output_language

CANVAS_TRANSLATE_MODEL = "qwen3.8-flash"

_TRADITIONAL_CHINESE_UI = frozenset({"zh-tw", "zh-hant", "zh-hk", "zh-mo", "hk", "mo"})
_NORWEGIAN_ALIASES = frozenset({"nb", "nn"})


def normalize_canvas_translate_target(value: str) -> str:
    """Map a UI locale to a prompt-registry code the diagram translator accepts."""
    normalized = (value or "").strip().lower().replace("_", "-")
    if normalized in _TRADITIONAL_CHINESE_UI:
        return "zh"
    if normalized in _NORWEGIAN_ALIASES:
        return "no"
    if not is_prompt_output_language(normalized):
        raise ValueError("Unsupported target_language code")
    return normalized


def canvas_translate_language_name(lang_code: str, ui_locale: Optional[str] = None) -> str:
    """English language name for the translate prompt."""
    locale = (ui_locale or "").strip().lower().replace("_", "-")
    if lang_code == "zh" and locale in _TRADITIONAL_CHINESE_UI:
        return "Traditional Chinese"
    return OUTPUT_LANGUAGE_ENGLISH_NAMES.get(lang_code, lang_code)


class TranslateNodeLabelRequest(BaseModel):
    """Request body for POST /api/canvas/translate_node_label."""

    text: str = Field(..., min_length=1, max_length=4096, description="Label text to translate")
    target_language: str = Field(..., min_length=2, max_length=16, description="Target language code")
    diagram_id: Optional[str] = Field(
        None,
        description="Saved diagram id for collaboration owner checks",
    )
    diagram_type: Optional[str] = Field(
        None,
        max_length=64,
        description="Diagram type for usage metadata",
    )

    @field_validator("target_language")
    @classmethod
    def validate_target_language(cls, value: str) -> str:
        """Reject target codes that the canvas translate API does not support."""
        return normalize_canvas_translate_target(value)

    @field_validator("diagram_type")
    @classmethod
    def normalize_diagram_type(cls, value: Optional[str]) -> Optional[str]:
        """Strip empty diagram_type values to None."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TranslateNodeLabelResponse(BaseModel):
    """JSON response for successful label translation."""

    translated_text: str = Field(..., description="Translated plain text")


class TranslateDiagramLabelItem(BaseModel):
    """One diagram item whose text should be translated (node label or connection label)."""

    item_id: str = Field(..., min_length=1, max_length=128, description="Node id or connection id")
    text: str = Field(..., min_length=1, max_length=4096, description="Label text to translate")
    item_kind: Literal["node", "connection"] = Field(
        default="node",
        description="node = diagram node label; connection = edge/concept-map relationship label",
    )


class TranslateDiagramLabelsRequest(BaseModel):
    """Request body for POST /api/canvas/translate_diagram_labels."""

    items: list[TranslateDiagramLabelItem] = Field(
        ...,
        min_length=1,
        max_length=250,
        description="Items to translate (order preserved in the response)",
    )
    target_language: str = Field(..., min_length=2, max_length=16, description="Target language code")
    diagram_id: Optional[str] = Field(
        None,
        description="Saved diagram id for collaboration owner checks",
    )
    diagram_type: Optional[str] = Field(
        None,
        max_length=64,
        description="Diagram type for usage metadata",
    )
    ui_locale: Optional[str] = Field(
        None,
        max_length=32,
        description="Interface locale (e.g. zh-tw) for Chinese script and style hints",
    )

    @field_validator("target_language")
    @classmethod
    def validate_batch_target_language(cls, value: str) -> str:
        """Reject target codes that the canvas translate API does not support."""
        return normalize_canvas_translate_target(value)

    @field_validator("diagram_type")
    @classmethod
    def normalize_batch_diagram_type(cls, value: Optional[str]) -> Optional[str]:
        """Strip empty diagram_type values to None."""
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("ui_locale")
    @classmethod
    def normalize_ui_locale(cls, value: Optional[str]) -> Optional[str]:
        """Lowercase ui_locale and treat blank strings as omitted."""
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            return None
        return stripped.lower()


class TranslateDiagramLabelResult(BaseModel):
    """One translated item in the batch response."""

    item_id: str
    translated_text: str
    item_kind: Literal["node", "connection"] = "node"


class TranslateDiagramLabelsResponse(BaseModel):
    """JSON response for batch label translation."""

    translations: list[TranslateDiagramLabelResult]
