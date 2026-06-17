"""Admin helpers for per-organization MindMate Dify settings on Organization rows."""

from __future__ import annotations

from typing import Any, Optional, cast

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization
from models.domain.messages import Language, Messages
from models.domain.mindbot_config import OrganizationMindbotConfig
from services.dify.org_mindmate_client import global_mindmate_dify_credentials
from services.mindbot.dify.service_health import check_dify_app_api_reachable
from utils.secrets_mask import mask_secret

MIN_DIFY_TIMEOUT_SECONDS = 5
MAX_DIFY_TIMEOUT_SECONDS = 600
MIN_AI_CARD_STREAMING_CHARS = 500
MAX_AI_CARD_STREAMING_CHARS = 50000
MIN_CHAIN_OF_THOUGHT_MAX_CHARS = 0
MAX_CHAIN_OF_THOUGHT_MAX_CHARS = 32000


def org_dify_behavior_fields(org: Organization) -> dict[str, Any]:
    """Shared MindBot/MindMate Dify behavior settings stored on the organization."""
    return {
        "dify_timeout_seconds": int(getattr(org, "dify_timeout_seconds", 300) or 300),
        "show_chain_of_thought_oto": bool(getattr(org, "show_chain_of_thought_oto", False)),
        "show_chain_of_thought_internal_group": bool(getattr(org, "show_chain_of_thought_internal_group", False)),
        "show_chain_of_thought_cross_org_group": bool(getattr(org, "show_chain_of_thought_cross_org_group", False)),
        "chain_of_thought_max_chars": int(getattr(org, "chain_of_thought_max_chars", 4000) or 4000),
        "dingtalk_ai_card_streaming_max_chars": int(getattr(org, "dingtalk_ai_card_streaming_max_chars", 6500) or 6500),
    }


def dify_list_fields(org: Organization) -> dict[str, Any]:
    """Serialized Dify fields for admin organization list (never exposes raw key)."""
    base_url = (cast(Optional[str], getattr(org, "dify_api_base_url", None)) or "").strip()
    key_raw = (cast(Optional[str], getattr(org, "dify_api_key", None)) or "").strip()
    return {
        "dify_api_base_url": base_url or None,
        "dify_api_key_masked": mask_secret(key_raw) if key_raw else None,
        **org_dify_behavior_fields(org),
    }


def resolve_organization_dify_credentials(org: Organization) -> tuple[str, str]:
    """Effective Dify API key and base URL for one school (org override or global .env)."""
    org_url = (cast(Optional[str], getattr(org, "dify_api_base_url", None)) or "").strip()
    org_key = (cast(Optional[str], getattr(org, "dify_api_key", None)) or "").strip()
    if org_url and org_key:
        return org_key, org_url
    return global_mindmate_dify_credentials()


def global_mindmate_dify_fields() -> dict[str, Any]:
    """Serialized global MindMate Dify settings from .env (never exposes raw key)."""
    api_key, api_url = global_mindmate_dify_credentials()
    return {
        "dify_api_base_url": api_url or None,
        "dify_api_key_masked": mask_secret(api_key) if api_key else None,
    }


def resolve_mindmate_dify_probe_credentials(
    org: Organization,
    body: Optional[dict],
) -> tuple[str, str]:
    """
    Credentials for admin health probe: optional draft from request body,
    else saved org override when complete, else global .env.
    """
    draft_url = ""
    draft_key = ""
    if body:
        draft_url = (body.get("dify_api_base_url") or "").strip()
        draft_key = (body.get("dify_api_key") or "").strip()

    org_url = (cast(Optional[str], getattr(org, "dify_api_base_url", None)) or "").strip()
    org_key = (cast(Optional[str], getattr(org, "dify_api_key", None)) or "").strip()

    if draft_url or draft_key:
        url = draft_url or org_url
        key = draft_key or org_key
        if url and key:
            return key, url

    if org_url and org_key:
        return org_key, org_url

    return global_mindmate_dify_credentials()


def resolve_mindmate_dify_probe_credentials_draft(
    body: Optional[dict],
) -> tuple[str, str]:
    """Credentials for pre-create admin probe: draft body or global .env."""
    draft_url = ""
    draft_key = ""
    if body:
        draft_url = (body.get("dify_api_base_url") or "").strip()
        draft_key = (body.get("dify_api_key") or "").strip()
    if draft_url and draft_key:
        return draft_key, draft_url
    return global_mindmate_dify_credentials()


async def probe_mindmate_dify_health_draft(body: Optional[dict]) -> dict[str, Any]:
    """Probe Dify for school create form (no organization row yet)."""
    api_key, api_url = resolve_mindmate_dify_probe_credentials_draft(body)
    online, http_status, err = await check_dify_app_api_reachable(api_url, api_key)
    return {
        "online": online,
        "http_status": http_status,
        "error": err,
    }


async def probe_mindmate_dify_health(
    org: Organization,
    body: Optional[dict],
) -> dict[str, Any]:
    """Probe Dify app API (GET /parameters) for effective MindMate credentials."""
    api_key, api_url = resolve_mindmate_dify_probe_credentials(org, body)
    online, http_status, err = await check_dify_app_api_reachable(api_url, api_key)
    return {
        "online": online,
        "http_status": http_status,
        "error": err,
    }


def _validate_dify_pair(
    base_url: str,
    api_key: str,
    lang: Language,
) -> None:
    """Validate dify pair."""
    if bool(base_url) != bool(api_key):
        error_msg = Messages.error("missing_required_fields", lang, "dify_api_base_url, dify_api_key")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    if base_url and len(base_url) > 512:
        error_msg = Messages.error("dify_api_base_url_too_long", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )


def apply_dify_on_create(org: Organization, request: dict, lang: Language) -> None:
    """Apply optional MindMate Dify override when creating an organization."""
    if "dify_api_base_url" not in request and "dify_api_key" not in request:
        return
    base_url = (request.get("dify_api_base_url") or "").strip()
    api_key = (request.get("dify_api_key") or "").strip()
    _validate_dify_pair(base_url, api_key, lang)
    if base_url and api_key:
        setattr(org, "dify_api_base_url", base_url)
        setattr(org, "dify_api_key", api_key)


def apply_dify_on_update(org: Organization, request: dict, lang: Language) -> None:
    """Apply MindMate Dify fields on organization update."""
    if "dify_api_base_url" in request:
        raw_url = request.get("dify_api_base_url")
        if raw_url is None:
            setattr(org, "dify_api_base_url", None)
        else:
            stripped = (raw_url or "").strip()
            setattr(org, "dify_api_base_url", stripped if stripped else None)

    if "dify_api_key" in request:
        raw_key = request.get("dify_api_key")
        if raw_key is None:
            setattr(org, "dify_api_key", None)
        else:
            stripped = (raw_key or "").strip()
            setattr(org, "dify_api_key", stripped if stripped else None)

    base_url = (cast(Optional[str], getattr(org, "dify_api_base_url", None)) or "").strip()
    key_raw = (cast(Optional[str], getattr(org, "dify_api_key", None)) or "").strip()
    if base_url or key_raw:
        _validate_dify_pair(base_url, key_raw, lang)

    _apply_org_dify_behavior_on_update(org, request)


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    """Clamp int."""
    return max(minimum, min(maximum, value))


def _apply_org_dify_behavior_on_update(org: Organization, request: dict) -> None:
    """Apply org dify behavior on update."""
    if "dify_timeout_seconds" in request:
        raw = request.get("dify_timeout_seconds")
        if raw is None:
            setattr(org, "dify_timeout_seconds", 300)
        else:
            setattr(
                org,
                "dify_timeout_seconds",
                _clamp_int(int(raw), MIN_DIFY_TIMEOUT_SECONDS, MAX_DIFY_TIMEOUT_SECONDS),
            )

    if "show_chain_of_thought" in request:
        enabled = bool(request.get("show_chain_of_thought"))
        setattr(org, "show_chain_of_thought_oto", enabled)
        setattr(org, "show_chain_of_thought_internal_group", enabled)
        setattr(org, "show_chain_of_thought_cross_org_group", enabled)
    else:
        if "show_chain_of_thought_oto" in request:
            setattr(org, "show_chain_of_thought_oto", bool(request.get("show_chain_of_thought_oto")))
        if "show_chain_of_thought_internal_group" in request:
            setattr(
                org,
                "show_chain_of_thought_internal_group",
                bool(request.get("show_chain_of_thought_internal_group")),
            )
        if "show_chain_of_thought_cross_org_group" in request:
            setattr(
                org,
                "show_chain_of_thought_cross_org_group",
                bool(request.get("show_chain_of_thought_cross_org_group")),
            )

    if "chain_of_thought_max_chars" in request:
        raw = request.get("chain_of_thought_max_chars")
        if raw is None:
            setattr(org, "chain_of_thought_max_chars", 4000)
        else:
            setattr(
                org,
                "chain_of_thought_max_chars",
                _clamp_int(
                    int(raw),
                    MIN_CHAIN_OF_THOUGHT_MAX_CHARS,
                    MAX_CHAIN_OF_THOUGHT_MAX_CHARS,
                ),
            )

    if "dingtalk_ai_card_streaming_max_chars" in request:
        raw = request.get("dingtalk_ai_card_streaming_max_chars")
        if raw is None:
            setattr(org, "dingtalk_ai_card_streaming_max_chars", 6500)
        else:
            setattr(
                org,
                "dingtalk_ai_card_streaming_max_chars",
                _clamp_int(
                    int(raw),
                    MIN_AI_CARD_STREAMING_CHARS,
                    MAX_AI_CARD_STREAMING_CHARS,
                ),
            )


def apply_org_dify_fields_to_mindbot_config(
    org: Organization,
    row: OrganizationMindbotConfig,
) -> None:
    """Copy org-level Dify behavior and optional credentials onto one MindBot config row."""
    behavior = org_dify_behavior_fields(org)
    row.dify_timeout_seconds = behavior["dify_timeout_seconds"]
    row.show_chain_of_thought_oto = behavior["show_chain_of_thought_oto"]
    row.show_chain_of_thought_internal_group = behavior["show_chain_of_thought_internal_group"]
    row.show_chain_of_thought_cross_org_group = behavior["show_chain_of_thought_cross_org_group"]
    row.chain_of_thought_max_chars = behavior["chain_of_thought_max_chars"]
    row.dingtalk_ai_card_streaming_max_chars = behavior["dingtalk_ai_card_streaming_max_chars"]
    api_key, api_url = resolve_organization_dify_credentials(org)
    if api_key and api_url:
        row.dify_api_base_url = api_url
        row.dify_api_key = api_key


async def propagate_org_dify_settings_to_mindbot_configs(
    db: AsyncSession,
    org: Organization,
) -> None:
    """Copy org-level Dify credentials and behavior settings to all MindBot configs."""
    result = await db.execute(
        select(OrganizationMindbotConfig).where(OrganizationMindbotConfig.organization_id == org.id)
    )
    rows = result.scalars().all()
    for row in rows:
        if not bool(getattr(row, "use_org_dify_settings", True)):
            continue
        apply_org_dify_fields_to_mindbot_config(org, row)
