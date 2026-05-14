"""Request model for canvas node label translation API."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

CANVAS_TRANSLATE_TARGET_CODES = frozenset(
    {
        "en",
        "zh",
        "yue",
        "ja",
        "ko",
        "fr",
        "de",
        "es",
        "pt",
        "it",
        "ru",
        "ar",
        "hi",
        "id",
        "vi",
        "th",
        "el",
        "tr",
    }
)

CANVAS_TRANSLATE_LANGUAGE_NAMES_EN = {
    "en": "English",
    "zh": "Chinese (Mandarin)",
    "yue": "Cantonese",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "pt": "Portuguese",
    "it": "Italian",
    "ru": "Russian",
    "ar": "Arabic",
    "hi": "Hindi",
    "id": "Indonesian",
    "vi": "Vietnamese",
    "th": "Thai",
    "el": "Greek",
    "tr": "Turkish",
}


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
        normalized = (value or "").strip().lower()
        if normalized not in CANVAS_TRANSLATE_TARGET_CODES:
            raise ValueError("Unsupported target_language code")
        return normalized

    @field_validator("diagram_type")
    @classmethod
    def normalize_diagram_type(cls, value: Optional[str]) -> Optional[str]:
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
        normalized = (value or "").strip().lower()
        if normalized not in CANVAS_TRANSLATE_TARGET_CODES:
            raise ValueError("Unsupported target_language code")
        return normalized

    @field_validator("diagram_type")
    @classmethod
    def normalize_batch_diagram_type(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("ui_locale")
    @classmethod
    def normalize_ui_locale(cls, value: Optional[str]) -> Optional[str]:
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
