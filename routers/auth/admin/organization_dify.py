"""Admin helpers for per-organization MindMate Dify settings on Organization rows."""

from __future__ import annotations

from typing import Any, Optional, cast

from fastapi import HTTPException, status

from models.domain.auth import Organization
from models.domain.messages import Language, Messages
from services.dify.org_mindmate_client import global_mindmate_dify_credentials
from utils.secrets_mask import mask_secret


def dify_list_fields(org: Organization) -> dict[str, Any]:
    """Serialized Dify fields for admin organization list (never exposes raw key)."""
    base_url = (cast(Optional[str], getattr(org, "dify_api_base_url", None)) or "").strip()
    key_raw = (cast(Optional[str], getattr(org, "dify_api_key", None)) or "").strip()
    return {
        "dify_api_base_url": base_url or None,
        "dify_api_key_masked": mask_secret(key_raw) if key_raw else None,
    }


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
    from services.mindbot.dify.service_health import check_dify_app_api_reachable

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
    from services.mindbot.dify.service_health import check_dify_app_api_reachable

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
