"""Load and validate per-organization custom LLM settings."""

from __future__ import annotations

import time
from typing import Any, Optional

from sqlalchemy import select

from models.domain.auth import Organization
from services.llm.org_custom_llm_constants import (
    API_TYPE_PLATFORM,
    CUSTOM_LLM_MODEL_MAX_LENGTH,
    CUSTOM_LLM_URL_MAX_LENGTH,
    OrgCustomLlmConfig,
    normalize_custom_llm_api_type,
)
from services.llm.org_custom_llm_urls import validated_api_root
from utils.db.session_open import system_rls_session

_CACHE_TTL_SECONDS = 5.0
_CONFIG_CACHE: dict[int, tuple[float, Optional[OrgCustomLlmConfig]]] = {}


def _strip(value: Any, max_length: int) -> str:
    text = str(value).strip() if value is not None else ""
    if len(text) > max_length:
        return text[:max_length]
    return text


def config_from_org(org: Optional[Organization]) -> Optional[OrgCustomLlmConfig]:
    """Build a config from an Organization row. None when platform default."""
    if org is None:
        return None
    api_type = normalize_custom_llm_api_type(getattr(org, "custom_llm_api_type", None))
    base_url = validated_api_root(_strip(getattr(org, "custom_llm_base_url", None), CUSTOM_LLM_URL_MAX_LENGTH))
    api_key = _strip(getattr(org, "custom_llm_api_key", None), 4096)
    model = _strip(getattr(org, "custom_llm_model", None), CUSTOM_LLM_MODEL_MAX_LENGTH)
    config = OrgCustomLlmConfig(
        api_type=api_type,
        base_url=base_url,
        api_key=api_key,
        model=model,
    )
    if not config.is_active:
        return None
    return config


def config_from_draft(
    api_type: Any,
    base_url: Any,
    api_key: Any,
    model: Any,
) -> Optional[OrgCustomLlmConfig]:
    """Build a config from admin form / probe draft values."""
    config = OrgCustomLlmConfig(
        api_type=normalize_custom_llm_api_type(str(api_type) if api_type is not None else None),
        base_url=validated_api_root(_strip(base_url, CUSTOM_LLM_URL_MAX_LENGTH)),
        api_key=_strip(api_key, 4096),
        model=_strip(model, CUSTOM_LLM_MODEL_MAX_LENGTH),
    )
    if not config.is_active:
        return None
    return config


def session_fields_from_config(config: Optional[OrgCustomLlmConfig]) -> dict[str, Any]:
    """Public session fields from a resolved config (no URL or key)."""
    if config is None:
        return {"custom_llm_enabled": False, "custom_llm_model": None}
    return {"custom_llm_enabled": True, "custom_llm_model": config.model}


def session_custom_llm_fields(org: Optional[Organization]) -> dict[str, Any]:
    """Public session fields from a live Organization row (not a Redis stub)."""
    return session_fields_from_config(config_from_org(org))


async def session_custom_llm_fields_for_org_id(organization_id: Optional[int]) -> dict[str, Any]:
    """Session flags from the same DB-backed loader used for routing."""
    return session_fields_from_config(await load_org_custom_llm_config(organization_id))


def invalidate_org_custom_llm_cache(organization_id: int) -> None:
    """Drop the short-lived in-process config cache after admin save."""
    _CONFIG_CACHE.pop(int(organization_id), None)


async def load_org_custom_llm_config(organization_id: Optional[int]) -> Optional[OrgCustomLlmConfig]:
    """Load an active school override, or None for the platform stack."""
    if organization_id is None or isinstance(organization_id, bool) or organization_id <= 0:
        return None
    org_id = int(organization_id)
    now = time.monotonic()
    cached = _CONFIG_CACHE.get(org_id)
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    async with system_rls_session() as db:
        org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
        config = config_from_org(org)
    _CONFIG_CACHE[org_id] = (now, config)
    return config


async def org_custom_llm_cache_stamp(organization_id: Optional[int]) -> str:
    """Result-cache stamp so platform and school results never mix."""
    config = await load_org_custom_llm_config(organization_id)
    if config is None:
        return API_TYPE_PLATFORM
    return config.cache_stamp
