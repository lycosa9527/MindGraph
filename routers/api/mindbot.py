"""MindBot: DingTalk HTTP webhooks and admin CRUD for per-organization config."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from config.settings import config
from models.domain.auth import Organization, User
from models.domain.mindbot_config import OrganizationMindbotConfig
from repositories.mindbot_repo import MindbotConfigRepository
from routers.auth.dependencies import require_admin_or_manager
from services.mindbot.dingtalk_platform_event import (
    dingtalk_platform_event_response,
    is_dingtalk_platform_event_request,
    shared_url_platform_event_error,
)
from services.mindbot.mindbot_callback import process_dingtalk_callback
from services.mindbot.platforms.dingtalk.verify import extract_dingtalk_robot_auth_headers
from services.mindbot.mindbot_errors import MindbotErrorCode, mindbot_error_headers
from services.mindbot.mindbot_metrics import mindbot_metrics
from utils.auth.roles import is_admin
from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)

_INBOUND_PREVIEW_LEN = 2048


def _log_mindbot_inbound(request: Request, raw: bytes, route_label: str) -> None:
    """When MINDBOT_LOG_CALLBACK_INBOUND=1, log safe inbound metadata for DingTalk debugging."""
    if not env_bool("MINDBOT_LOG_CALLBACK_INBOUND", False):
        return
    ts, sg = extract_dingtalk_robot_auth_headers(request.headers)
    preview = raw.decode("utf-8", errors="replace")[:_INBOUND_PREVIEW_LEN]
    logger.info(
        "[MindBot] inbound %s path=%s query=%s body_len=%s timestamp=%s sign_len=%s preview=%r",
        route_label,
        request.url.path,
        request.url.query or "",
        len(raw),
        "set" if ts else "missing",
        len(sg or ""),
        preview,
    )


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

router = APIRouter(prefix="/mindbot", tags=["mindbot"])


class MindbotConfigPayload(BaseModel):
    """Admin create/update body."""

    dingtalk_robot_code: str = Field(..., min_length=1, max_length=128)
    dingtalk_app_secret: Optional[str] = Field(
        None,
        description="Omit or empty on update to keep existing secret",
    )
    dingtalk_client_id: Optional[str] = Field(None, max_length=128)
    dify_api_base_url: str = Field(..., min_length=1, max_length=512)
    dify_api_key: Optional[str] = Field(
        None,
        description="Omit or empty on update to keep existing key",
    )
    dify_timeout_seconds: int = Field(30, ge=5, le=120)
    dify_inputs_json: Optional[str] = Field(
        None,
        description="Optional JSON object string passed as Dify chat-messages inputs",
    )
    dingtalk_event_token: Optional[str] = Field(
        None,
        max_length=128,
        description="DingTalk event subscription Token; omit on update to keep",
    )
    dingtalk_event_aes_key: Optional[str] = Field(
        None,
        max_length=128,
        description="EncodingAESKey; omit on update to keep",
    )
    dingtalk_event_owner_key: Optional[str] = Field(
        None,
        max_length=128,
        description="appKey, corpId, or suiteKey per DingTalk app type",
    )
    is_enabled: bool = True


class MindbotConfigResponse(BaseModel):
    id: int
    organization_id: int
    dingtalk_robot_code: str
    dingtalk_client_id: Optional[str]
    dingtalk_event_token_set: bool
    dingtalk_event_aes_key_set: bool
    dingtalk_event_owner_key: Optional[str]
    dify_api_base_url: str
    dify_timeout_seconds: int
    dify_inputs_json: Optional[str]
    is_enabled: bool


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


@router.post("/dingtalk/callback")
async def dingtalk_callback_shared(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """Shared URL: resolve tenant by ``robotCode`` in JSON body (HTTP receive mode)."""
    _require_mindbot_feature()
    raw = await request.body()
    _log_mindbot_inbound(request, raw, "shared")
    body = _dict_from_dingtalk_raw_body(raw)
    if is_dingtalk_platform_event_request(request, body):
        resp = shared_url_platform_event_error()
        mindbot_metrics.record_from_headers(dict(resp.headers))
        return resp
    ts, sg = extract_dingtalk_robot_auth_headers(request.headers)
    code, resp_headers = await process_dingtalk_callback(
        db,
        timestamp_header=ts,
        sign_header=sg,
        body=body,
    )
    mindbot_metrics.record_from_headers(resp_headers)
    return Response(status_code=code, headers=resp_headers)


@router.post("/dingtalk/orgs/{organization_id}/callback")
async def dingtalk_callback_per_org(
    organization_id: int,
    request: Request,
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """Per-org URL: robot HMAC (headers) or open-platform event subscription (query + encrypt)."""
    _require_mindbot_feature()
    raw = await request.body()
    _log_mindbot_inbound(request, raw, f"org_{organization_id}")
    body = _dict_from_dingtalk_raw_body(raw)
    repo = MindbotConfigRepository(db)
    if is_dingtalk_platform_event_request(request, body):
        cfg_any = await repo.get_by_organization_id(organization_id)
        if cfg_any is None:
            resp = Response(
                status_code=404,
                headers=mindbot_error_headers(MindbotErrorCode.CONFIG_NOT_FOUND),
            )
            mindbot_metrics.record_from_headers(dict(resp.headers))
            return resp
        resp = dingtalk_platform_event_response(request, body, cfg_any)
        mindbot_metrics.record_from_headers(dict(resp.headers))
        return resp
    cfg = await repo.get_enabled_by_organization_id(organization_id)
    if cfg is None:
        resp = Response(
            status_code=404,
            headers=mindbot_error_headers(MindbotErrorCode.CONFIG_NOT_FOUND),
        )
        mindbot_metrics.record_from_headers(dict(resp.headers))
        return resp
    ts, sg = extract_dingtalk_robot_auth_headers(request.headers)
    code, resp_headers = await process_dingtalk_callback(
        db,
        timestamp_header=ts,
        sign_header=sg,
        body=body,
        resolved_config=cfg,
    )
    mindbot_metrics.record_from_headers(resp_headers)
    return Response(status_code=code, headers=resp_headers)


def _to_response(row: OrganizationMindbotConfig) -> MindbotConfigResponse:
    tok = (row.dingtalk_event_token or "").strip()
    aes = (row.dingtalk_event_aes_key or "").strip()
    own = (row.dingtalk_event_owner_key or "").strip()
    return MindbotConfigResponse(
        id=row.id,
        organization_id=row.organization_id,
        dingtalk_robot_code=row.dingtalk_robot_code,
        dingtalk_client_id=row.dingtalk_client_id,
        dingtalk_event_token_set=bool(tok),
        dingtalk_event_aes_key_set=bool(aes),
        dingtalk_event_owner_key=own or None,
        dify_api_base_url=row.dify_api_base_url,
        dify_timeout_seconds=row.dify_timeout_seconds,
        dify_inputs_json=row.dify_inputs_json,
        is_enabled=row.is_enabled,
    )


@router.get("/admin/configs", response_model=list[MindbotConfigResponse])
async def admin_list_mindbot_configs(
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_admin_or_manager),
) -> list[MindbotConfigResponse]:
    _require_mindbot_feature()
    repo = MindbotConfigRepository(db)
    if is_admin(user):
        rows = await repo.list_all()
        return [_to_response(r) for r in rows]
    oid = getattr(user, "organization_id", None)
    if oid is None:
        return []
    row = await repo.get_by_organization_id(int(oid))
    return [_to_response(row)] if row else []


@router.get("/admin/configs/{organization_id}", response_model=MindbotConfigResponse)
async def admin_get_mindbot_config(
    organization_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_admin_or_manager),
) -> MindbotConfigResponse:
    _require_mindbot_feature()
    _ensure_org_scope(user, organization_id)
    repo = MindbotConfigRepository(db)
    row = await repo.get_by_organization_id(organization_id)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"{MindbotErrorCode.ADMIN_CONFIG_NOT_FOUND.value}: MindBot config not found",
        )
    return _to_response(row)


@router.put("/admin/configs/{organization_id}", response_model=MindbotConfigResponse)
async def admin_upsert_mindbot_config(
    organization_id: int,
    payload: MindbotConfigPayload,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_admin_or_manager),
) -> MindbotConfigResponse:
    _require_mindbot_feature()
    _ensure_org_scope(user, organization_id)
    org_check = await db.execute(select(Organization.id).where(Organization.id == organization_id))
    if org_check.scalar_one_or_none() is None:
        raise HTTPException(
            status_code=404,
            detail=f"{MindbotErrorCode.ADMIN_ORGANIZATION_NOT_FOUND.value}: Organization not found",
        )
    result = await db.execute(
        select(OrganizationMindbotConfig).where(
            OrganizationMindbotConfig.organization_id == organization_id,
        )
    )
    existing = result.scalar_one_or_none()
    app_secret, dify_key = _resolve_secrets(payload, existing)
    evt_token, evt_aes, evt_owner = _event_subscription_fields(payload, existing)
    if existing is None:
        dup = await db.execute(
            select(OrganizationMindbotConfig).where(
                OrganizationMindbotConfig.dingtalk_robot_code == payload.dingtalk_robot_code.strip(),
            )
        )
        if dup.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail=f"{MindbotErrorCode.ADMIN_ROBOT_CODE_CONFLICT.value}: robot_code already in use",
            )
        row = OrganizationMindbotConfig(
            organization_id=organization_id,
            dingtalk_robot_code=payload.dingtalk_robot_code.strip(),
            dingtalk_app_secret=app_secret,
            dingtalk_client_id=(payload.dingtalk_client_id or "").strip() or None,
            dingtalk_event_token=evt_token,
            dingtalk_event_aes_key=evt_aes,
            dingtalk_event_owner_key=evt_owner,
            dify_api_base_url=payload.dify_api_base_url.strip(),
            dify_api_key=dify_key,
            dify_inputs_json=(payload.dify_inputs_json or "").strip() or None,
            dify_timeout_seconds=payload.dify_timeout_seconds,
            is_enabled=payload.is_enabled,
        )
        db.add(row)
    else:
        conflict = await db.execute(
            select(OrganizationMindbotConfig).where(
                OrganizationMindbotConfig.dingtalk_robot_code == payload.dingtalk_robot_code.strip(),
                OrganizationMindbotConfig.id != existing.id,
            )
        )
        if conflict.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=409,
                detail=f"{MindbotErrorCode.ADMIN_ROBOT_CODE_CONFLICT.value}: robot_code already in use",
            )
        existing.dingtalk_robot_code = payload.dingtalk_robot_code.strip()
        existing.dingtalk_app_secret = app_secret
        existing.dingtalk_client_id = (payload.dingtalk_client_id or "").strip() or None
        existing.dingtalk_event_token = evt_token
        existing.dingtalk_event_aes_key = evt_aes
        existing.dingtalk_event_owner_key = evt_owner
        existing.dify_api_base_url = payload.dify_api_base_url.strip()
        existing.dify_api_key = dify_key
        if "dify_inputs_json" in payload.model_fields_set:
            existing.dify_inputs_json = (payload.dify_inputs_json or "").strip() or None
        existing.dify_timeout_seconds = payload.dify_timeout_seconds
        existing.is_enabled = payload.is_enabled
        row = existing
    await db.commit()
    await db.refresh(row)
    logger.info(
        "[MindBot] config %s organization_id=%s config_id=%s robot_code=%s enabled=%s "
        "client_id_set=%s user_id=%s",
        "created" if existing is None else "updated",
        organization_id,
        row.id,
        row.dingtalk_robot_code.strip(),
        row.is_enabled,
        bool((row.dingtalk_client_id or "").strip()),
        user.id,
    )
    return _to_response(row)


@router.delete("/admin/configs/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_mindbot_config(
    organization_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_admin_or_manager),
) -> Response:
    _require_mindbot_feature()
    _ensure_org_scope(user, organization_id)
    result = await db.execute(
        select(OrganizationMindbotConfig).where(
            OrganizationMindbotConfig.organization_id == organization_id,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"{MindbotErrorCode.ADMIN_CONFIG_NOT_FOUND.value}: MindBot config not found",
        )
    config_id = row.id
    robot_code = row.dingtalk_robot_code.strip()
    await db.delete(row)
    await db.commit()
    logger.info(
        "[MindBot] config deleted organization_id=%s config_id=%s robot_code=%s user_id=%s",
        organization_id,
        config_id,
        robot_code,
        user.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
