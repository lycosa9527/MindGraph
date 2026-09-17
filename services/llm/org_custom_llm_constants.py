"""Constants and config shape for per-organization custom native LLM."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

API_TYPE_PLATFORM = "dashscope_volcengine"
API_TYPE_OPENAI_CHAT = "openai_chat"
API_TYPE_OPENAI_RESPONSES = "openai_responses"
API_TYPE_ANTHROPIC = "anthropic_messages"

CUSTOM_LLM_API_TYPES = frozenset(
    {
        API_TYPE_PLATFORM,
        API_TYPE_OPENAI_CHAT,
        API_TYPE_OPENAI_RESPONSES,
        API_TYPE_ANTHROPIC,
    }
)

CUSTOM_LLM_OVERRIDE_TYPES = frozenset(
    {
        API_TYPE_OPENAI_CHAT,
        API_TYPE_OPENAI_RESPONSES,
        API_TYPE_ANTHROPIC,
    }
)

ANTHROPIC_VERSION = "2023-06-01"

CUSTOM_LLM_MODEL_MAX_LENGTH = 128
CUSTOM_LLM_URL_MAX_LENGTH = 512


@dataclass(frozen=True)
class OrgCustomLlmConfig:
    """Resolved school LLM override. Inactive when type is the platform default."""

    api_type: str
    base_url: str
    api_key: str
    model: str

    @property
    def is_active(self) -> bool:
        """True when the school should use this endpoint instead of platform LLM."""
        if self.api_type not in CUSTOM_LLM_OVERRIDE_TYPES:
            return False
        return bool(self.base_url and self.api_key and self.model)

    @property
    def cache_stamp(self) -> str:
        """Fingerprint for org LLM result-cache keys (hashed; no raw secret)."""
        if not self.is_active:
            return API_TYPE_PLATFORM
        material = f"{self.api_type}\0{self.base_url}\0{self.model}\0{self.api_key}"
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
        return f"{self.api_type}:{digest}"


def normalize_custom_llm_api_type(raw: Optional[str]) -> str:
    """Return a known API type, defaulting to the platform stack."""
    value = (raw or "").strip()
    if value in CUSTOM_LLM_API_TYPES:
        return value
    return API_TYPE_PLATFORM
