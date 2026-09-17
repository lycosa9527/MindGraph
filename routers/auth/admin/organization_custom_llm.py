"""Admin helpers for per-organization custom native LLM settings."""

from __future__ import annotations

from typing import Any, Optional, cast

from fastapi import HTTPException, status

from clients.llm.org_custom.factory import build_org_custom_llm_client
from models.domain.auth import Organization
from models.domain.messages import Language, Messages
from services.infrastructure.http.error_handler import LLMServiceError
from services.llm.org_custom_config import (
    config_from_draft,
    config_from_org,
)
from services.llm.org_custom_llm_constants import (
    API_TYPE_PLATFORM,
    CUSTOM_LLM_API_TYPES,
    CUSTOM_LLM_MODEL_MAX_LENGTH,
    CUSTOM_LLM_OVERRIDE_TYPES,
    CUSTOM_LLM_URL_MAX_LENGTH,
    normalize_custom_llm_api_type,
)
from services.llm.org_custom_llm_urls import validated_api_root
from utils.secrets_mask import mask_secret

ORG_CUSTOM_LLM_UPDATE_KEYS = frozenset(
    {
        "custom_llm_api_type",
        "custom_llm_base_url",
        "custom_llm_api_key",
        "custom_llm_model",
        "clear_custom_llm_api_key",
    }
)


def request_updates_custom_llm_settings(request: dict) -> bool:
    """True when the org update body touches custom LLM fields."""
    return bool(ORG_CUSTOM_LLM_UPDATE_KEYS.intersection(request))


def custom_llm_list_fields(org: Organization) -> dict[str, Any]:
    """Serialized custom LLM fields for admin list/update (never raw key)."""
    api_type = normalize_custom_llm_api_type(getattr(org, "custom_llm_api_type", None))
    base_url = (cast(Optional[str], getattr(org, "custom_llm_base_url", None)) or "").strip()
    key_raw = (cast(Optional[str], getattr(org, "custom_llm_api_key", None)) or "").strip()
    model = (cast(Optional[str], getattr(org, "custom_llm_model", None)) or "").strip()
    return {
        "custom_llm_api_type": api_type,
        "custom_llm_base_url": base_url or None,
        "custom_llm_api_key_masked": mask_secret(key_raw) if key_raw else None,
        "custom_llm_model": model or None,
        "custom_llm_enabled": config_from_org(org) is not None,
    }


def _strip_optional(raw: Any, max_length: int) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    return text[:max_length]


def _apply_cleared_platform(org: Organization) -> None:
    setattr(org, "custom_llm_api_type", API_TYPE_PLATFORM)
    setattr(org, "custom_llm_base_url", None)
    setattr(org, "custom_llm_api_key", None)
    setattr(org, "custom_llm_model", None)


def apply_custom_llm_on_update(org: Organization, request: dict, lang: Language) -> None:
    """Apply custom LLM fields on organization update."""
    api_type = normalize_custom_llm_api_type(
        request.get("custom_llm_api_type", getattr(org, "custom_llm_api_type", None))
    )
    if api_type not in CUSTOM_LLM_API_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("custom_llm_invalid_type", lang),
        )

    if api_type == API_TYPE_PLATFORM:
        _apply_cleared_platform(org)
        return

    if "custom_llm_base_url" in request:
        setattr(
            org,
            "custom_llm_base_url",
            validated_api_root(_strip_optional(request.get("custom_llm_base_url"), CUSTOM_LLM_URL_MAX_LENGTH) or ""),
        )
        if not getattr(org, "custom_llm_base_url", None):
            setattr(org, "custom_llm_base_url", None)

    if request.get("clear_custom_llm_api_key"):
        setattr(org, "custom_llm_api_key", None)
    elif "custom_llm_api_key" in request:
        key_val = _strip_optional(request.get("custom_llm_api_key"), 4096)
        if key_val is not None:
            setattr(org, "custom_llm_api_key", key_val)

    if "custom_llm_model" in request:
        setattr(
            org,
            "custom_llm_model",
            _strip_optional(request.get("custom_llm_model"), CUSTOM_LLM_MODEL_MAX_LENGTH),
        )

    setattr(org, "custom_llm_api_type", api_type)
    if config_from_org(org) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("custom_llm_incomplete", lang),
        )


async def probe_custom_llm_health(
    org: Organization,
    body: Optional[dict],
    lang: Language,
) -> dict[str, Any]:
    """Probe draft or stored school credentials with one official ping."""
    draft = body if isinstance(body, dict) else {}
    api_type = normalize_custom_llm_api_type(
        draft.get("custom_llm_api_type", getattr(org, "custom_llm_api_type", None))
    )
    if api_type == API_TYPE_PLATFORM:
        return {"online": True, "error": None, "custom_llm_api_type": api_type}
    if api_type not in CUSTOM_LLM_OVERRIDE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("custom_llm_invalid_type", lang),
        )

    stored_key = (cast(Optional[str], getattr(org, "custom_llm_api_key", None)) or "").strip()
    draft_key = (str(draft.get("custom_llm_api_key") or "")).strip()
    api_key = draft_key or stored_key
    config = config_from_draft(
        api_type,
        draft.get("custom_llm_base_url", getattr(org, "custom_llm_base_url", None)),
        api_key,
        draft.get("custom_llm_model", getattr(org, "custom_llm_model", None)),
    )
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("custom_llm_incomplete", lang),
        )
    try:
        client = build_org_custom_llm_client(config)
        await client.probe()
    except LLMServiceError as exc:
        message = getattr(exc, "user_message", None) or str(exc)
        return {
            "online": False,
            "error": message,
            "custom_llm_api_type": api_type,
        }
    return {"online": True, "error": None, "custom_llm_api_type": api_type}
