"""Shared utilities for MindBot router modules."""

from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import HTTPException, status

from config.settings import config
from models.domain.auth import User
from models.domain.mindbot_config import OrganizationMindbotConfig
from routers.api.mindbot_models import MindbotConfigPayload, MindbotConfigResponse
from services.mindbot.errors import MindbotErrorCode
from services.mindbot.telemetry.metrics import mindbot_metrics
from utils.auth.roles import is_admin


def _require_mindbot_feature() -> None:
    if not config.FEATURE_MINDBOT:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{MindbotErrorCode.FEATURE_DISABLED.value}: MindBot feature disabled",
        )


def _ensure_org_scope(user: User, organization_id: int) -> None:
    if is_admin(user):
        return
    uid_org = getattr(user, "organization_id", None)
    if uid_org is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization required",
        )
    if int(uid_org) != int(organization_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization access denied",
        )


def _mask_secret(secret: str, head: int = 4, tail: int = 4) -> str:
    """Show start/end of a stored secret; mask the middle for admin display only."""
    text = (secret or "").strip()
    if not text:
        return ""
    length = len(text)
    if length <= head + tail:
        if length <= 1:
            return "•"
        if length == 2:
            return text[0] + "•"
        return text[0] + "•" * (length - 2) + text[-1]
    mid = min(length - head - tail, 12)
    return text[:head] + "•" * mid + text[-tail:]


def _to_response(row: OrganizationMindbotConfig) -> MindbotConfigResponse:
    tok = (row.dingtalk_event_token or "").strip()
    aes = (row.dingtalk_event_aes_key or "").strip()
    own = (row.dingtalk_event_owner_key or "").strip()
    return MindbotConfigResponse(
        id=row.id,
        organization_id=row.organization_id,
        public_callback_token=_mask_secret(row.public_callback_token.strip(), head=0, tail=8),
        dingtalk_robot_code=row.dingtalk_robot_code,
        dingtalk_app_secret_masked=_mask_secret(row.dingtalk_app_secret),
        dify_api_key_masked=_mask_secret(row.dify_api_key),
        dingtalk_client_id=row.dingtalk_client_id,
        dingtalk_event_token_set=bool(tok),
        dingtalk_event_aes_key_set=bool(aes),
        dingtalk_event_owner_key=_mask_secret(own) if own else None,
        dify_api_base_url=row.dify_api_base_url,
        dify_timeout_seconds=row.dify_timeout_seconds,
        dify_inputs_json=row.dify_inputs_json,
        show_chain_of_thought_oto=bool(row.show_chain_of_thought_oto),
        show_chain_of_thought_internal_group=bool(row.show_chain_of_thought_internal_group),
        show_chain_of_thought_cross_org_group=bool(row.show_chain_of_thought_cross_org_group),
        chain_of_thought_max_chars=int(row.chain_of_thought_max_chars),
        dingtalk_ai_card_template_id=(row.dingtalk_ai_card_template_id or "").strip() or None,
        dingtalk_ai_card_param_key=(row.dingtalk_ai_card_param_key or "").strip() or None,
        is_enabled=row.is_enabled,
    )


def _callback_metrics_snapshot_for_user(user: User) -> dict[str, Any]:
    """
    Full callback counters for admins; managers only see their organization's slice.

    ``by_robot_code`` is omitted for managers because counters are not keyed by org in
    memory (would risk cross-tenant leakage if robot codes were ever ambiguous).
    """
    full = mindbot_metrics.snapshot()
    if is_admin(user):
        return full
    oid = getattr(user, "organization_id", None)
    if oid is None:
        return {"by_error_code": {}, "by_organization_id": {}, "by_robot_code": {}}
    oid_int = int(oid)
    by_org = full.get("by_organization_id") or {}
    org_codes: dict[str, int] = {}
    if oid_int in by_org:
        org_codes = dict(by_org[oid_int])
    else:
        for key, codes in by_org.items():
            if int(key) == oid_int:
                org_codes = dict(codes)
                break
    return {
        "by_error_code": {},
        "by_organization_id": {oid_int: org_codes},
        "by_robot_code": {},
    }


def _resolve_secrets(
    payload: MindbotConfigPayload,
    existing: Optional[OrganizationMindbotConfig],
) -> tuple[str, str]:
    secret_raw = (payload.dingtalk_app_secret or "").strip()
    key_raw = (payload.dify_api_key or "").strip()
    if existing is None:
        if not secret_raw or not key_raw:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"{MindbotErrorCode.ADMIN_SECRETS_REQUIRED.value}: "
                    "dingtalk_app_secret and dify_api_key are required for new config"
                ),
            )
        return secret_raw, key_raw
    return (
        secret_raw or existing.dingtalk_app_secret,
        key_raw or existing.dify_api_key,
    )


def _event_subscription_fields(
    payload: MindbotConfigPayload,
    existing: Optional[OrganizationMindbotConfig],
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Token and AES key: omit on update to keep; empty string clears."""
    if existing is None:
        return (
            (payload.dingtalk_event_token or "").strip() or None,
            (payload.dingtalk_event_aes_key or "").strip() or None,
            (payload.dingtalk_event_owner_key or "").strip() or None,
        )
    token = existing.dingtalk_event_token
    if "dingtalk_event_token" in payload.model_fields_set:
        raw = (payload.dingtalk_event_token or "").strip()
        token = raw if raw else None
    aes_key = existing.dingtalk_event_aes_key
    if "dingtalk_event_aes_key" in payload.model_fields_set:
        raw = (payload.dingtalk_event_aes_key or "").strip()
        aes_key = raw if raw else None
    owner_key = existing.dingtalk_event_owner_key
    if "dingtalk_event_owner_key" in payload.model_fields_set:
        raw = (payload.dingtalk_event_owner_key or "").strip()
        owner_key = raw if raw else None
    return token, aes_key, owner_key


def _norm_opt(value: Optional[str]) -> Optional[str]:
    text = (value or "").strip()
    return text if text else None


def _mindbot_auth_field_changes_on_update(
    *,
    payload: MindbotConfigPayload,
    secret_raw: str,
    key_raw: str,
    prev_client_id: Optional[str],
    prev_evt_token: Optional[str],
    prev_evt_aes: Optional[str],
    prev_evt_owner: Optional[str],
    resolved_evt_token: Optional[str],
    resolved_evt_aes: Optional[str],
    resolved_evt_owner: Optional[str],
) -> list[str]:
    """Non-secret field names for auth-related updates (for audit logging)."""
    parts: list[str] = []
    if secret_raw:
        parts.append("dingtalk_app_secret")
    if key_raw:
        parts.append("dify_api_key")
    if "dingtalk_client_id" in payload.model_fields_set:
        if _norm_opt(payload.dingtalk_client_id) != _norm_opt(prev_client_id):
            parts.append("dingtalk_client_id")
    if "dingtalk_event_token" in payload.model_fields_set:
        if _norm_opt(resolved_evt_token) != _norm_opt(prev_evt_token):
            parts.append("dingtalk_event_token")
    if "dingtalk_event_aes_key" in payload.model_fields_set:
        if _norm_opt(resolved_evt_aes) != _norm_opt(prev_evt_aes):
            parts.append("dingtalk_event_aes_key")
    if "dingtalk_event_owner_key" in payload.model_fields_set:
        if _norm_opt(resolved_evt_owner) != _norm_opt(prev_evt_owner):
            parts.append("dingtalk_event_owner_key")
    return parts


def _dict_from_dingtalk_raw_body(raw: bytes) -> dict[str, Any]:
    """
    Parse POST JSON for DingTalk robot HTTP mode.

    DingTalk may POST an empty body when saving the message URL; treat empty
    whitespace as an empty JSON object.
    """
    if not raw.strip():
        return {}
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail=f"{MindbotErrorCode.INVALID_JSON.value}: Invalid JSON body",
        ) from None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        raise HTTPException(
            status_code=400,
            detail=f"{MindbotErrorCode.INVALID_JSON.value}: Invalid JSON body",
        ) from None
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=400,
            detail=f"{MindbotErrorCode.INVALID_BODY.value}: Body must be a JSON object",
        )
    return parsed
