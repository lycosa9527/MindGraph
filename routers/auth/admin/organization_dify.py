"""
Admin helpers for per-organization MindMate Dify settings on Organization rows.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional, cast

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization
from models.domain.messages import Language, Messages
from models.domain.mindbot_config import OrganizationMindbotConfig
from services.dify.dify_servers import org_server_credentials, primary_server_no
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
    base_url_2 = (cast(Optional[str], getattr(org, "dify_api_base_url_2", None)) or "").strip()
    key_raw_2 = (cast(Optional[str], getattr(org, "dify_api_key_2", None)) or "").strip()
    return {
        "dify_api_base_url": base_url or None,
        "dify_api_key_masked": mask_secret(key_raw) if key_raw else None,
        "dify_api_base_url_2": base_url_2 or None,
        "dify_api_key_2_masked": mask_secret(key_raw_2) if key_raw_2 else None,
        "dify_active_server": primary_server_no(org),
        "dify_failover_enabled": bool(getattr(org, "dify_failover_enabled", True)),
        **org_dify_behavior_fields(org),
    }


def resolve_organization_dify_credentials(org: Organization, server: Optional[int] = None) -> tuple[str, str]:
    """
    Effective Dify API key and base URL for one school.

    With *server* (1 or 2) returns that server's credentials; otherwise the
    configured active/primary server. Falls back to the global ``.env`` server
    when the selected server has no per-org credentials.
    """
    selected = server if server in (1, 2) else primary_server_no(org)
    creds = org_server_credentials(org, selected)
    if creds is not None:
        api_key, api_url = creds
        return api_key, api_url
    return global_mindmate_dify_credentials()


def global_mindmate_dify_fields() -> dict[str, Any]:
    """Serialized global MindMate Dify settings from .env (never exposes raw key)."""
    api_key, api_url = global_mindmate_dify_credentials()
    return {
        "dify_api_base_url": api_url or None,
        "dify_api_key_masked": mask_secret(api_key) if api_key else None,
    }


def _probe_server_from_body(body: Optional[dict]) -> Optional[int]:
    """Server number (1/2) requested in a probe body, if any."""
    if not body:
        return None
    raw = body.get("server")
    try:
        value = int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return value if value in (1, 2) else None


def resolve_mindmate_dify_probe_credentials(
    org: Organization,
    body: Optional[dict],
) -> tuple[str, str]:
    """
    Credentials for admin health probe: optional draft from request body,
    else the saved override for the requested/active server, else global .env.
    """
    draft_url = ""
    draft_key = ""
    if body:
        draft_url = (body.get("dify_api_base_url") or "").strip()
        draft_key = (body.get("dify_api_key") or "").strip()

    server = _probe_server_from_body(body)
    selected = server if server in (1, 2) else primary_server_no(org)
    saved = org_server_credentials(org, selected)
    org_key, org_url = saved if saved is not None else ("", "")

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
    url_field: str = "dify_api_base_url",
    key_field: str = "dify_api_key",
) -> None:
    """Validate dify pair."""
    if bool(base_url) != bool(api_key):
        error_msg = Messages.error("missing_required_fields", lang, f"{url_field}, {key_field}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    if base_url and len(base_url) > 512:
        error_msg = Messages.error("dify_api_base_url_too_long", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )


def _apply_dify_pair_on_create(
    org: Organization,
    request: dict,
    lang: Language,
    url_field: str,
    key_field: str,
) -> None:
    """Apply one Dify server credential pair when creating an organization."""
    if url_field not in request and key_field not in request:
        return
    base_url = (request.get(url_field) or "").strip()
    api_key = (request.get(key_field) or "").strip()
    _validate_dify_pair(base_url, api_key, lang, url_field, key_field)
    if base_url and api_key:
        setattr(org, url_field, base_url)
        setattr(org, key_field, api_key)


def _apply_dify_server_selection(org: Organization, request: dict) -> None:
    """Apply active-server selector and failover toggle from a request payload."""
    if "dify_active_server" in request:
        raw = request.get("dify_active_server")
        try:
            value = int(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            value = 1
        setattr(org, "dify_active_server", value if value in (1, 2) else 1)
    if "dify_failover_enabled" in request:
        setattr(org, "dify_failover_enabled", bool(request.get("dify_failover_enabled")))


def apply_dify_on_create(org: Organization, request: dict, lang: Language) -> None:
    """Apply optional MindMate Dify overrides (both servers) when creating an organization."""
    _apply_dify_pair_on_create(org, request, lang, "dify_api_base_url", "dify_api_key")
    _apply_dify_pair_on_create(org, request, lang, "dify_api_base_url_2", "dify_api_key_2")
    _apply_dify_server_selection(org, request)


def _apply_dify_pair_on_update(
    org: Organization,
    request: dict,
    lang: Language,
    url_field: str,
    key_field: str,
) -> None:
    """Apply one Dify server credential pair on organization update."""
    if url_field in request:
        raw_url = request.get(url_field)
        if raw_url is None:
            setattr(org, url_field, None)
        else:
            stripped = (raw_url or "").strip()
            setattr(org, url_field, stripped if stripped else None)

    if key_field in request:
        raw_key = request.get(key_field)
        if raw_key is None:
            setattr(org, key_field, None)
        else:
            stripped = (raw_key or "").strip()
            setattr(org, key_field, stripped if stripped else None)

    base_url = (cast(Optional[str], getattr(org, url_field, None)) or "").strip()
    key_raw = (cast(Optional[str], getattr(org, key_field, None)) or "").strip()
    if base_url or key_raw:
        _validate_dify_pair(base_url, key_raw, lang, url_field, key_field)


def apply_dify_on_update(org: Organization, request: dict, lang: Language) -> None:
    """Apply MindMate Dify fields (both servers + selection) on organization update."""
    _apply_dify_pair_on_update(org, request, lang, "dify_api_base_url", "dify_api_key")
    _apply_dify_pair_on_update(org, request, lang, "dify_api_base_url_2", "dify_api_key_2")
    _apply_dify_server_selection(org, request)
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
