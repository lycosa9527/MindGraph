"""Request models for ZhiHui /generate-text-to-image."""

from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from utils.prompt_output_languages import is_prompt_output_language

# DashScope Qwen Image 3.0 multimodal-generation models (T2I / I2I).
DEFAULT_IMAGE_MODEL = "qwen-image-3.0"
ALLOWED_IMAGE_MODELS = frozenset({"qwen-image-3.0", "qwen-image-3.0-pro"})
MAX_REFERENCE_IMAGES = 3
# Rough cap on data-URI payload (~4.5MB base64 ≈ 6MB string).
MAX_REFERENCE_IMAGE_CHARS = 6_000_000

_DATA_IMAGE_RE = re.compile(
    r"^data:image/(?:png|jpeg|jpg|webp);base64,[A-Za-z0-9+/=\s]+$",
    re.IGNORECASE,
)
_HTTP_IMAGE_RE = re.compile(r"^https?://\S+$", re.IGNORECASE)


def _validate_language(value: str) -> str:
    """Ensure API language is in the prompt-output registry."""
    if not is_prompt_output_language(value):
        raise ValueError("Language must be a supported generation language code")
    return value


def _normalize_reference_image(value: str) -> str:
    """Accept https URL or image data URI for DashScope I2I input."""
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError("reference image must not be empty")
    if len(cleaned) > MAX_REFERENCE_IMAGE_CHARS:
        raise ValueError("reference image is too large")
    if _DATA_IMAGE_RE.match(cleaned) or _HTTP_IMAGE_RE.match(cleaned):
        return cleaned
    raise ValueError("reference image must be an https URL or image data URI")


class GenerateTextToImageRequest(BaseModel):
    """Request model for POST /api/generate-text-to-image (Dify HTTP tool)."""

    prompt: str = Field(..., min_length=1, max_length=1000, description="Image generation prompt")
    language: str = Field("zh", description="Language code for notices / tracking")
    model: str = Field(
        DEFAULT_IMAGE_MODEL,
        description="Qwen Image 3.0 model: qwen-image-3.0 (default) or qwen-image-3.0-pro",
    )
    dify_user_id: Optional[str] = Field(
        None,
        max_length=256,
        description="Dify sys.user_id fallback when X-MG-Dify-User header unavailable",
    )
    mg_dify_user: Optional[str] = Field(
        None,
        max_length=256,
        description="Same as dify_user_id; MindMate/MindBot stream inputs alias",
    )
    conversation_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional Dify sys.conversation_id for logging and correlation",
    )
    mg_conversation_id: Optional[str] = Field(
        None,
        max_length=100,
        description="Same as conversation_id; MindMate/MindBot inputs alias",
    )
    size: Optional[str] = Field(
        None,
        description="Output size width*height; omit for model auto resolution",
    )
    watermark: Optional[bool] = Field(False, description="DashScope watermark flag")
    negative_prompt: Optional[str] = Field("", description="Negative prompt")
    prompt_extend: Optional[bool] = Field(True, description="API-level prompt extend when enhance off")
    reference_images: Optional[list[str]] = Field(
        None,
        description="Optional 1–3 reference images (https URL or data:image/*;base64,...) for I2I",
    )

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        """Reject unknown generation language codes."""
        return _validate_language(value)

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: Optional[str]) -> str:
        """Default to qwen-image-3.0; reject unknown model ids."""
        if value is None:
            return DEFAULT_IMAGE_MODEL
        cleaned = value.strip()
        if not cleaned:
            return DEFAULT_IMAGE_MODEL
        if cleaned not in ALLOWED_IMAGE_MODELS:
            allowed = ", ".join(sorted(ALLOWED_IMAGE_MODELS))
            raise ValueError(f"model must be one of: {allowed}")
        return cleaned

    @field_validator("reference_images")
    @classmethod
    def validate_reference_images(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        """Normalize optional reference images (max 3) for Qwen I2I."""
        if value is None:
            return None
        cleaned = [_normalize_reference_image(item) for item in value]
        if not cleaned:
            return None
        if len(cleaned) > MAX_REFERENCE_IMAGES:
            raise ValueError(f"at most {MAX_REFERENCE_IMAGES} reference images allowed")
        return cleaned

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prompt": "一只小猫在教室里看书",
                "language": "zh",
                "model": "qwen-image-3.0",
                "conversation_id": "conv-123",
                "dify_user_id": "user-456",
            }
        }
    )
