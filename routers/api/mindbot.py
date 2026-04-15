"""MindBot: DingTalk HTTP webhooks and admin CRUD for per-organization config."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from config.settings import config
from models.domain.auth import Organization, User
from models.domain.mindbot_config import OrganizationMindbotConfig
from repositories.mindbot_repo import MindbotConfigRepository
from repositories.mindbot_usage_repo import MindbotUsageRepository
from routers.auth.dependencies import require_admin, require_mindbot_admin_access
from services.mindbot.dify.service_health import check_dify_app_api_reachable
from services.mindbot.platforms.dingtalk.cards.ai_card import probe_ai_card_streaming_update_api
from services.mindbot.errors import MindbotErrorCode, mindbot_error_headers
from services.mindbot.integrations.dingtalk.inbound_log import (
    debug_callback_failure_logging_enabled,
    log_dingtalk_inbound,
)
from services.mindbot.integrations.dingtalk.platform_event import (
    dingtalk_platform_event_response,
    is_dingtalk_platform_event_request,
    shared_url_platform_event_error,
)
from services.mindbot.pipeline.callback import (
    mindbot_accept_ack_headers,
    process_dingtalk_callback,
    schedule_dingtalk_pipeline_background,
    validate_callback_fast,
)
from services.mindbot.session.callback_token import new_public_callback_token
from services.mindbot.telemetry.metrics import mindbot_metrics
from services.mindbot.telemetry.usage import mindbot_usage_tracking_enabled
from services.mindbot.platforms.dingtalk.auth.verify import extract_dingtalk_robot_auth_headers
from utils.auth.roles import is_admin

logger = logging.getLogger(__name__)


async def _dingtalk_robot_message_response_after_config(
    *,
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    raw: bytes,
    debug_route_label: str,
    request: Request,
) -> Response:
    """Shared path: validate, schedule background pipeline, return 200 ACCEPTED or early error."""
    ts, sg = extract_dingtalk_robot_auth_headers(request.headers)
    dbg = debug_callback_failure_logging_enabled()
    ok, early, ctx = await validate_callback_fast(
        timestamp_header=ts,
        sign_header=sg,
        body=body,
        resolved_config=cfg,
        debug_route_label=debug_route_label,
        debug_raw_body=raw if dbg else None,
        debug_request_headers=dict(request.headers) if dbg else None,
    )
    if not ok:
        if early is None:
            resp = Response(
                status_code=500,
                headers=mindbot_error_headers(MindbotErrorCode.DIFY_FAILED),
            )
            mindbot_metrics.record_from_headers(dict(resp.headers))
            return resp
        code, resp_headers = early
        mindbot_metrics.record_from_headers(resp_headers)
        return Response(status_code=code, headers=resp_headers)
    if ctx is None:
        resp = Response(
            status_code=500,
            headers=mindbot_error_headers(MindbotErrorCode.DIFY_FAILED),
        )
        mindbot_metrics.record_from_headers(dict(resp.headers))
        return resp
    schedule_dingtalk_pipeline_background(ctx)
    ack_headers = mindbot_accept_ack_headers(cfg)
    mindbot_metrics.record_from_headers(ack_headers)
    return Response(status_code=200, headers=ack_headers)


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
    dify_timeout_seconds: int = Field(300, ge=5, le=600)
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
    show_chain_of_thought_oto: bool = False
    show_chain_of_thought_internal_group: bool = False
    show_chain_of_thought_cross_org_group: bool = False
    chain_of_thought_max_chars: int = Field(4000, ge=0, le=32000)
    dingtalk_ai_card_template_id: Optional[str] = Field(
        None,
        max_length=128,
        description="Optional AI card template id; empty keeps legacy session webhook / OpenAPI text",
    )
    dingtalk_ai_card_param_key: Optional[str] = Field(
        None,
        max_length=128,
        description="Template variable key for streaming markdown body; empty defaults to 'content'",
    )


class MindbotConfigResponse(BaseModel):
    id: int
    organization_id: int
    public_callback_token: str
    dingtalk_robot_code: str
    dingtalk_app_secret_masked: str
    dify_api_key_masked: str
    dingtalk_client_id: Optional[str]
    dingtalk_event_token_set: bool
    dingtalk_event_aes_key_set: bool
    dingtalk_event_owner_key: Optional[str]
    dify_api_base_url: str
    dify_timeout_seconds: int
    dify_inputs_json: Optional[str]
    show_chain_of_thought_oto: bool
    show_chain_of_thought_internal_group: bool
    show_chain_of_thought_cross_org_group: bool
    chain_of_thought_max_chars: int
    dingtalk_ai_card_template_id: Optional[str]
    dingtalk_ai_card_param_key: Optional[str]
    is_enabled: bool


class DifyServiceStatusResponse(BaseModel):
    """MindBot admin: Dify app API reachability (server-side probe only)."""

    online: bool
    http_status: Optional[int] = None
    error: Optional[str] = None
    probe_url: Optional[str] = Field(
        default=None,
        description="GET target used for the check (no credentials)",
    )


class MindbotMemoryFootprintResponse(BaseModel):
    """In-process MindBot structures for capacity / leak diagnostics (per worker)."""

    oauth_lock_map_size: int = Field(
        ...,
        description="Current entries in the OAuth thundering-herd lock LRU map.",
    )
    oauth_lock_map_max: int = Field(
        ...,
        description="Configured cap before LRU eviction (MINDBOT_OAUTH_LOCK_MAP_MAX).",
    )
    dingtalk_stream_registered_clients: int = Field(
        ...,
        description="DingTalk Stream SDK clients in this process (one per client_id).",
    )
    callback_metrics: dict[str, Any] = Field(
        ...,
        description=(
            "Callback outcome counters since process start. "
            "School managers only receive their organization's ``by_organization_id`` "
            "entry; global aggregates and ``by_robot_code`` are admin-only."
        ),
    )


class DingtalkAiCardStreamingStatusResponse(BaseModel):
    """MindBot admin: probe DingTalk AI card streaming update API (OpenAPI)."""

    ok: bool
    http_status: Optional[int] = None
    error: Optional[str] = Field(
        default=None,
        description="Internal reason token when the probe fails before a DingTalk call.",
    )
    dingtalk_code: Optional[str] = None
    dingtalk_message: Optional[str] = None
    friendly_message: Optional[str] = Field(
        default=None,
        description="Operator-facing summary (mapped from DingTalk or internal reasons).",
    )
    probe_path: str = Field(
        default="/v1.0/card/streaming",
        description="PUT path used (see DingTalk AI card streaming update API).",
    )


class MindbotUsageEventItem(BaseModel):
    """One analytics row for admin (no message body stored)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    mindbot_config_id: Optional[int]
    dingtalk_staff_id: str
    sender_nick: Optional[str]
    dingtalk_sender_id: Optional[str]
    dify_user_key: str
    msg_id: Optional[str]
    dingtalk_conversation_id: Optional[str]
    dify_conversation_id: Optional[str]
    error_code: str
    streaming: bool
    prompt_chars: int
    reply_chars: int
    duration_seconds: Optional[float]
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    total_tokens: Optional[int]
    dingtalk_chat_scope: Optional[str]
    inbound_msg_type: Optional[str]
    conversation_user_turn: Optional[int]
    linked_user_id: Optional[int]
    created_at: datetime


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


@router.get("/dingtalk/callback")
async def dingtalk_callback_shared_get(request: Request) -> Response:
    """Optional GET reachability check (some DingTalk flows probe the URL with GET)."""
    _require_mindbot_feature()
    log_dingtalk_inbound(request, b"", "shared_get")
    return Response(
        status_code=200,
        headers=mindbot_error_headers(MindbotErrorCode.OK),
    )


@router.get("/dingtalk/orgs/{organization_id}/callback")
async def dingtalk_callback_per_org_get(request: Request, organization_id: int) -> Response:
    """Optional GET reachability check for the per-organization callback URL."""
    _require_mindbot_feature()
    log_dingtalk_inbound(request, b"", f"org_{organization_id}_get")
    return Response(
        status_code=200,
        headers=mindbot_error_headers(
            MindbotErrorCode.OK,
            organization_id=organization_id,
        ),
    )


@router.post("/dingtalk/callback")
async def dingtalk_callback_shared(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
) -> Response:
    """
    Shared URL (legacy): connectivity probe and migration-period shim only.

    Real message delivery must use ``POST /dingtalk/callback/t/{public_callback_token}``
    or ``POST /dingtalk/orgs/{organization_id}/callback`` so the tenant is chosen from
    the path, not from JSON ``robotCode`` (DingTalk often sends a placeholder that does
    not match the stored robot code).

    During migration, non-empty requests are acknowledged with 200 so DingTalk does not
    mark the shared URL as permanently failed before each school updates their console URL.
    """
    _require_mindbot_feature()
    raw = await request.body()
    body = _dict_from_dingtalk_raw_body(raw)
    log_dingtalk_inbound(request, raw, "shared", parsed_body=body)
    if is_dingtalk_platform_event_request(request, body):
        resp = shared_url_platform_event_error()
        mindbot_metrics.record_from_headers(dict(resp.headers))
        return resp
    ts, sg = extract_dingtalk_robot_auth_headers(request.headers)
    dbg = debug_callback_failure_logging_enabled()
    code, resp_headers = await process_dingtalk_callback(
        db,
        timestamp_header=ts,
        sign_header=sg,
        body=body,
        debug_route_label="shared",
        debug_raw_body=raw if dbg else None,
        debug_request_headers=dict(request.headers) if dbg else None,
    )
    if code == 404:
        resp_headers = mindbot_error_headers(MindbotErrorCode.PATH_CALLBACK_REQUIRED)
        mindbot_metrics.record_from_headers(resp_headers)
        return Response(status_code=200, headers=resp_headers)
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
    body = _dict_from_dingtalk_raw_body(raw)
    log_dingtalk_inbound(request, raw, f"org_{organization_id}", parsed_body=body)
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
    return await _dingtalk_robot_message_response_after_config(
        cfg=cfg,
        body=body,
        raw=raw,
        debug_route_label=f"org_{organization_id}",
        request=request,
    )


@router.get("/dingtalk/callback/t/{public_callback_token}")
async def dingtalk_callback_by_token_get(
    request: Request,
    public_callback_token: str = Path(..., min_length=8, max_length=64),
) -> Response:
    """GET reachability for opaque per-school URL (no numeric organization id in path)."""
    _require_mindbot_feature()
    token = public_callback_token.strip()
    log_dingtalk_inbound(request, b"", f"token_{token[:8]}_get")
    return Response(
        status_code=200,
        headers=mindbot_error_headers(MindbotErrorCode.OK),
    )


@router.post("/dingtalk/callback/t/{public_callback_token}")
async def dingtalk_callback_by_token(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    public_callback_token: str = Path(..., min_length=8, max_length=64),
) -> Response:
    """Per-school URL: resolve tenant by secret token in path (HTTP receive mode)."""
    _require_mindbot_feature()
    token = public_callback_token.strip()
    raw = await request.body()
    body = _dict_from_dingtalk_raw_body(raw)
    route_label = f"token_{token[:8]}"
    log_dingtalk_inbound(request, raw, route_label, parsed_body=body)
    repo = MindbotConfigRepository(db)
    if is_dingtalk_platform_event_request(request, body):
        cfg_any = await repo.get_by_public_callback_token(token)
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
    cfg = await repo.get_enabled_by_public_callback_token(token)
    if cfg is None:
        resp = Response(
            status_code=404,
            headers=mindbot_error_headers(MindbotErrorCode.CONFIG_NOT_FOUND),
        )
        mindbot_metrics.record_from_headers(dict(resp.headers))
        return resp
    return await _dingtalk_robot_message_response_after_config(
        cfg=cfg,
        body=body,
        raw=raw,
        debug_route_label=route_label,
        request=request,
    )


def _to_response(row: OrganizationMindbotConfig) -> MindbotConfigResponse:
    tok = (row.dingtalk_event_token or "").strip()
    aes = (row.dingtalk_event_aes_key or "").strip()
    own = (row.dingtalk_event_owner_key or "").strip()
    return MindbotConfigResponse(
        id=row.id,
        organization_id=row.organization_id,
        public_callback_token=row.public_callback_token.strip(),
        dingtalk_robot_code=row.dingtalk_robot_code,
        dingtalk_app_secret_masked=_mask_secret(row.dingtalk_app_secret),
        dify_api_key_masked=_mask_secret(row.dify_api_key),
        dingtalk_client_id=row.dingtalk_client_id,
        dingtalk_event_token_set=bool(tok),
        dingtalk_event_aes_key_set=bool(aes),
        dingtalk_event_owner_key=own or None,
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


@router.get("/admin/internal/memory-footprint", response_model=MindbotMemoryFootprintResponse)
async def admin_mindbot_memory_footprint(
    user: User = Depends(require_admin),
) -> MindbotMemoryFootprintResponse:
    """
    Long-lived in-process MindBot maps (OAuth lock LRU, DingTalk Stream clients) plus
    callback counters. Platform admins only (process-wide metrics, not org-scoped).

    School managers use MindBot admin APIs scoped to their organization; they must not
    observe worker-wide maps or global callback aggregates beyond org-sliced metrics.
    """
    from services.mindbot.telemetry.metrics import mindbot_long_lived_maps_snapshot

    _require_mindbot_feature()
    long_lived = mindbot_long_lived_maps_snapshot()
    return MindbotMemoryFootprintResponse(
        oauth_lock_map_size=int(long_lived["oauth_lock_map_size"]),
        oauth_lock_map_max=int(long_lived["oauth_lock_map_max"]),
        dingtalk_stream_registered_clients=int(long_lived["dingtalk_stream_registered_clients"]),
        callback_metrics=_callback_metrics_snapshot_for_user(user),
    )


@router.get("/admin/dify-service-status", response_model=DifyServiceStatusResponse)
async def admin_dify_service_status(
    _user: User = Depends(require_mindbot_admin_access),
) -> DifyServiceStatusResponse:
    """Probe configured Dify app API (GET /parameters); does not expose secrets."""
    _require_mindbot_feature()
    base = config.MINDBOT_DIFY_HEALTH_BASE_URL
    key = config.MINDBOT_DIFY_HEALTH_API_KEY
    probe_url = f"{base}/parameters" if base else None
    online, http_status, err = await check_dify_app_api_reachable(base, key)
    return DifyServiceStatusResponse(
        online=online,
        http_status=http_status,
        error=err,
        probe_url=probe_url,
    )


@router.get(
    "/admin/configs/{organization_id}/ai-card-streaming-status",
    response_model=DingtalkAiCardStreamingStatusResponse,
)
async def admin_ai_card_streaming_status(
    organization_id: int,
    template_id: Optional[str] = Query(
        None,
        max_length=128,
        description="Optional template id from the form (before save) to require a template for the check",
    ),
    dingtalk_client_id: Optional[str] = Query(
        None,
        max_length=128,
        description="Optional OpenAPI app key from the form before save; falls back to stored config",
    ),
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_mindbot_admin_access),
) -> DingtalkAiCardStreamingStatusResponse:
    """
    Server-side probe: ``PUT /v1.0/card/streaming`` with a random ``outTrackId``.

    Expects a business error when the card does not exist; that still indicates
    OAuth and streaming-update permission are working.
    """
    _require_mindbot_feature()
    _ensure_org_scope(user, organization_id)
    repo = MindbotConfigRepository(db)
    row = await repo.get_by_organization_id(organization_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{MindbotErrorCode.ADMIN_CONFIG_NOT_FOUND.value}: MindBot config not found",
        )
    probe = await probe_ai_card_streaming_update_api(
        row,
        template_id_override=template_id,
        dingtalk_client_id_override=dingtalk_client_id,
    )
    template_param = bool((template_id or "").strip())
    client_id_param = bool((dingtalk_client_id or "").strip())
    log_line = (
        "[MindBot] ai_card_streaming_probe organization_id=%s user_id=%s ok=%s "
        "http_status=%s error_token=%s dingtalk_code=%s template_param=%s "
        "client_id_param=%s"
    )
    log_args = (
        organization_id,
        user.id,
        probe.ok,
        probe.http_status,
        probe.error_token,
        probe.dingtalk_code,
        template_param,
        client_id_param,
    )
    if probe.ok:
        logger.info(log_line, *log_args)
    else:
        logger.warning(log_line, *log_args)
    return DingtalkAiCardStreamingStatusResponse(
        ok=probe.ok,
        http_status=probe.http_status,
        error=probe.error_token,
        dingtalk_code=probe.dingtalk_code,
        dingtalk_message=probe.dingtalk_message,
        friendly_message=probe.friendly_message,
    )


@router.get("/admin/configs", response_model=list[MindbotConfigResponse])
async def admin_list_mindbot_configs(
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_mindbot_admin_access),
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
    user: User = Depends(require_mindbot_admin_access),
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
    user: User = Depends(require_mindbot_admin_access),
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
    secret_raw = (payload.dingtalk_app_secret or "").strip()
    key_raw = (payload.dify_api_key or "").strip()
    app_secret, dify_key = _resolve_secrets(payload, existing)
    evt_token, evt_aes, evt_owner = _event_subscription_fields(payload, existing)
    prev_client_id: Optional[str] = None
    prev_evt_token: Optional[str] = None
    prev_evt_aes: Optional[str] = None
    prev_evt_owner: Optional[str] = None
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
            public_callback_token=new_public_callback_token(),
            dingtalk_app_secret=app_secret,
            dingtalk_client_id=(payload.dingtalk_client_id or "").strip() or None,
            dingtalk_event_token=evt_token,
            dingtalk_event_aes_key=evt_aes,
            dingtalk_event_owner_key=evt_owner,
            dify_api_base_url=payload.dify_api_base_url.strip(),
            dify_api_key=dify_key,
            dify_inputs_json=(payload.dify_inputs_json or "").strip() or None,
            dify_timeout_seconds=payload.dify_timeout_seconds,
            show_chain_of_thought_oto=payload.show_chain_of_thought_oto,
            show_chain_of_thought_internal_group=payload.show_chain_of_thought_internal_group,
            show_chain_of_thought_cross_org_group=payload.show_chain_of_thought_cross_org_group,
            chain_of_thought_max_chars=payload.chain_of_thought_max_chars,
            dingtalk_ai_card_template_id=(payload.dingtalk_ai_card_template_id or "").strip() or None,
            dingtalk_ai_card_param_key=(payload.dingtalk_ai_card_param_key or "").strip() or None,
            is_enabled=payload.is_enabled,
        )
        db.add(row)
    else:
        prev_client_id = existing.dingtalk_client_id
        prev_evt_token = existing.dingtalk_event_token
        prev_evt_aes = existing.dingtalk_event_aes_key
        prev_evt_owner = existing.dingtalk_event_owner_key
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
        if "dingtalk_client_id" in payload.model_fields_set:
            existing.dingtalk_client_id = (payload.dingtalk_client_id or "").strip() or None
        existing.dingtalk_event_token = evt_token
        existing.dingtalk_event_aes_key = evt_aes
        existing.dingtalk_event_owner_key = evt_owner
        existing.dify_api_base_url = payload.dify_api_base_url.strip()
        existing.dify_api_key = dify_key
        if "dify_inputs_json" in payload.model_fields_set:
            existing.dify_inputs_json = (payload.dify_inputs_json or "").strip() or None
        existing.dify_timeout_seconds = payload.dify_timeout_seconds
        existing.show_chain_of_thought_oto = payload.show_chain_of_thought_oto
        existing.show_chain_of_thought_internal_group = payload.show_chain_of_thought_internal_group
        existing.show_chain_of_thought_cross_org_group = payload.show_chain_of_thought_cross_org_group
        existing.chain_of_thought_max_chars = payload.chain_of_thought_max_chars
        if "dingtalk_ai_card_template_id" in payload.model_fields_set:
            existing.dingtalk_ai_card_template_id = (
                (payload.dingtalk_ai_card_template_id or "").strip() or None
            )
        if "dingtalk_ai_card_param_key" in payload.model_fields_set:
            existing.dingtalk_ai_card_param_key = (
                (payload.dingtalk_ai_card_param_key or "").strip() or None
            )
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
    if existing is None:
        logger.info(
            "[MindBot] config auth credentials initialized organization_id=%s config_id=%s "
            "user_id=%s client_id_set=%s event_token_set=%s event_aes_set=%s event_owner_set=%s",
            organization_id,
            row.id,
            user.id,
            bool((payload.dingtalk_client_id or "").strip()),
            bool(evt_token),
            bool(evt_aes),
            bool(evt_owner),
        )
    else:
        auth_changes = _mindbot_auth_field_changes_on_update(
            payload=payload,
            secret_raw=secret_raw,
            key_raw=key_raw,
            prev_client_id=prev_client_id,
            prev_evt_token=prev_evt_token,
            prev_evt_aes=prev_evt_aes,
            prev_evt_owner=prev_evt_owner,
            resolved_evt_token=evt_token,
            resolved_evt_aes=evt_aes,
            resolved_evt_owner=evt_owner,
        )
        if auth_changes:
            logger.info(
                "[MindBot] config auth fields updated organization_id=%s config_id=%s user_id=%s "
                "fields=%s",
                organization_id,
                row.id,
                user.id,
                ",".join(auth_changes),
            )
    return _to_response(row)


@router.delete("/admin/configs/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_mindbot_config(
    organization_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_mindbot_admin_access),
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


@router.post(
    "/admin/configs/{organization_id}/rotate-callback-token",
    response_model=MindbotConfigResponse,
)
async def admin_rotate_mindbot_callback_token(
    organization_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_mindbot_admin_access),
) -> MindbotConfigResponse:
    """Issue a new public callback token; DingTalk must use the new callback URL."""
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
    row.public_callback_token = new_public_callback_token()
    await db.commit()
    await db.refresh(row)
    logger.info(
        "[MindBot] callback token rotated organization_id=%s config_id=%s user_id=%s",
        organization_id,
        row.id,
        user.id,
    )
    return _to_response(row)


@router.get(
    "/admin/configs/{organization_id}/usage-events",
    response_model=list[MindbotUsageEventItem],
)
async def admin_list_mindbot_usage_events(
    organization_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_mindbot_admin_access),
    limit: int = Query(50, ge=1, le=100),
    before_id: Optional[int] = Query(
        None,
        description="Cursor: return rows with id strictly less than this value",
    ),
    dingtalk_staff_id: Optional[str] = Query(
        None,
        description="Filter to one DingTalk staff id (Monitor tab)",
    ),
) -> list[MindbotUsageEventItem]:
    _require_mindbot_feature()
    _ensure_org_scope(user, organization_id)
    if not mindbot_usage_tracking_enabled():
        return []
    repo = MindbotUsageRepository(db)
    rows = await repo.list_events_for_org(
        organization_id=organization_id,
        limit=limit,
        before_id=before_id,
        dingtalk_staff_id=dingtalk_staff_id,
    )
    return [MindbotUsageEventItem.model_validate(r) for r in rows]


@router.get(
    "/admin/configs/{organization_id}/usage-events/{event_id}",
    response_model=MindbotUsageEventItem,
)
async def admin_get_mindbot_usage_event(
    organization_id: int,
    event_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_mindbot_admin_access),
) -> MindbotUsageEventItem:
    _require_mindbot_feature()
    _ensure_org_scope(user, organization_id)
    if not mindbot_usage_tracking_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MindBot usage tracking disabled",
        )
    repo = MindbotUsageRepository(db)
    row = await repo.get_event_by_id(
        organization_id=organization_id,
        event_id=event_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usage event not found",
        )
    return MindbotUsageEventItem.model_validate(row)


@router.get(
    "/admin/configs/{organization_id}/usage-thread-events",
    response_model=list[MindbotUsageEventItem],
)
async def admin_list_mindbot_usage_thread_events(
    organization_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_mindbot_admin_access),
    dingtalk_staff_id: str = Query(
        ...,
        min_length=1,
        description="DingTalk staff id for the thread",
    ),
    dingtalk_conversation_id: Optional[str] = Query(
        None,
        description="DingTalk conversation id when present",
    ),
    dify_conversation_id: Optional[str] = Query(
        None,
        description="Dify conversation id when DingTalk id is absent",
    ),
    limit: int = Query(50, ge=1, le=100),
    before_id: Optional[int] = Query(
        None,
        description="Cursor: return rows with id strictly less than this value",
    ),
) -> list[MindbotUsageEventItem]:
    _require_mindbot_feature()
    _ensure_org_scope(user, organization_id)
    if not mindbot_usage_tracking_enabled():
        return []
    dt = (dingtalk_conversation_id or "").strip()
    df = (dify_conversation_id or "").strip()
    if not dt and not df:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="dingtalk_conversation_id or dify_conversation_id is required",
        )
    repo = MindbotUsageRepository(db)
    rows = await repo.list_events_for_thread(
        organization_id=organization_id,
        dingtalk_staff_id=dingtalk_staff_id,
        dingtalk_conversation_id=dt or None,
        dify_conversation_id=df or None,
        limit=limit,
        before_id=before_id,
    )
    return [MindbotUsageEventItem.model_validate(r) for r in rows]
