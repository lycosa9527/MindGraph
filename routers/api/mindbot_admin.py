"""MindBot admin CRUD endpoints for per-organization configuration and usage analytics."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from config.settings import config
from models.domain.auth import Organization, User
from models.domain.mindbot_config import OrganizationMindbotConfig
from repositories.mindbot_repo import MindbotConfigRepository
from repositories.mindbot_usage_repo import MindbotUsageRepository
from routers.api.mindbot_helpers import (
    _callback_metrics_snapshot_for_user,
    _ensure_org_scope,
    _event_subscription_fields,
    _mindbot_auth_field_changes_on_update,
    _require_mindbot_feature,
    _resolve_secrets,
    _to_response,
)
from routers.api.mindbot_models import (
    DifyServiceStatusResponse,
    DingtalkAiCardStreamingStatusResponse,
    MindbotConfigPayload,
    MindbotConfigResponse,
    MindbotMemoryFootprintResponse,
    MindbotUsageEventItem,
)
from routers.auth.dependencies import require_admin, require_mindbot_admin_access
from services.mindbot.dify.service_health import check_dify_app_api_reachable
from services.mindbot.errors import MindbotErrorCode
from services.mindbot.platforms.dingtalk.cards.ai_card import probe_ai_card_streaming_update_api
from services.mindbot.session.callback_token import new_public_callback_token
from services.mindbot.telemetry.usage import mindbot_usage_tracking_enabled
from utils.auth.roles import is_admin

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/internal/memory-footprint", response_model=MindbotMemoryFootprintResponse)
async def admin_mindbot_memory_footprint(
    user: User = Depends(require_admin),
) -> MindbotMemoryFootprintResponse:
    """
    Long-lived in-process MindBot maps (OAuth lock LRU, DingTalk Stream clients) plus
    callback counters. Platform admins only (process-wide metrics, not org-scoped).
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
    user: User = Depends(require_mindbot_admin_access),
) -> DifyServiceStatusResponse:
    """Probe configured Dify app API (GET /parameters); does not expose secrets."""
    _require_mindbot_feature()
    base = config.MINDBOT_DIFY_HEALTH_BASE_URL
    key = config.MINDBOT_DIFY_HEALTH_API_KEY
    probe_url = f"{base}/parameters" if base and is_admin(user) else None
    online, http_status, err = await check_dify_app_api_reachable(base, key)
    return DifyServiceStatusResponse(
        online=online,
        http_status=http_status,
        error=err,
        probe_url=probe_url,
    )


@router.get("/admin/configs/{organization_id}/dify-health", response_model=DifyServiceStatusResponse)
async def admin_org_dify_health(
    organization_id: int,
    db: AsyncSession = Depends(get_async_db),
    user: User = Depends(require_mindbot_admin_access),
) -> DifyServiceStatusResponse:
    """Probe the org's own Dify app API (GET /parameters); does not expose secrets."""
    _require_mindbot_feature()
    _ensure_org_scope(user, organization_id)
    repo = MindbotConfigRepository(db)
    row = await repo.get_by_organization_id(organization_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{MindbotErrorCode.ADMIN_CONFIG_NOT_FOUND.value}: MindBot config not found",
        )
    online, http_status, err = await check_dify_app_api_reachable(
        row.dify_api_base_url.strip(),
        row.dify_api_key.strip(),
    )
    logger.info(
        "[MindBot] org_dify_health_probe organization_id=%s user_id=%s online=%s http_status=%s",
        organization_id,
        user.id,
        online,
        http_status,
    )
    return DifyServiceStatusResponse(
        online=online,
        http_status=http_status,
        error=err,
        probe_url=None,
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
    limit: int = Query(50, ge=1, le=200),
    after_org_id: Optional[int] = Query(
        None,
        description="Cursor: return orgs with organization_id strictly greater than this value",
    ),
) -> list[MindbotConfigResponse]:
    _require_mindbot_feature()
    repo = MindbotConfigRepository(db)
    if is_admin(user):
        rows = await repo.list_all(limit=limit, after_org_id=after_org_id)
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
        select(OrganizationMindbotConfig)
        .where(OrganizationMindbotConfig.organization_id == organization_id)
        .with_for_update()
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
            dingtalk_ai_card_streaming_max_chars=payload.dingtalk_ai_card_streaming_max_chars,
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
            existing.dingtalk_ai_card_template_id = (payload.dingtalk_ai_card_template_id or "").strip() or None
        if "dingtalk_ai_card_param_key" in payload.model_fields_set:
            existing.dingtalk_ai_card_param_key = (payload.dingtalk_ai_card_param_key or "").strip() or None
        if "dingtalk_ai_card_streaming_max_chars" in payload.model_fields_set:
            existing.dingtalk_ai_card_streaming_max_chars = payload.dingtalk_ai_card_streaming_max_chars
        existing.is_enabled = payload.is_enabled
        row = existing
    await db.commit()
    await db.refresh(row)
    logger.info(
        "[MindBot] config %s organization_id=%s config_id=%s robot_code=%s enabled=%s client_id_set=%s user_id=%s",
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
                "[MindBot] config auth fields updated organization_id=%s config_id=%s user_id=%s fields=%s",
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
