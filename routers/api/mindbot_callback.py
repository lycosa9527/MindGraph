"""DingTalk HTTP webhook callback endpoints for MindBot."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Path, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from repositories.mindbot_repo import MindbotConfigRepository
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
    schedule_dingtalk_pipeline_background,
    validate_callback_fast,
)
from services.mindbot.platforms.dingtalk.auth.verify import extract_dingtalk_robot_auth_headers
from services.mindbot.telemetry.metrics import mindbot_metrics
from routers.api.mindbot_helpers import _dict_from_dingtalk_raw_body, _require_mindbot_feature
from models.domain.mindbot_config import OrganizationMindbotConfig

logger = logging.getLogger(__name__)

router = APIRouter()


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
) -> Response:
    """
    Shared URL (legacy): connectivity probe and migration-period shim only.

    Real message delivery must use ``POST /dingtalk/callback/t/{public_callback_token}``
    or ``POST /dingtalk/orgs/{organization_id}/callback`` so the tenant is chosen from
    the path, not from JSON ``robotCode`` (DingTalk often sends a placeholder that does
    not match the stored robot code).

    The pipeline is scheduled in the background (same as per-org / per-token routes)
    so a slow Dify response does not block the HTTP worker.
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
    ok, early, ctx = await validate_callback_fast(
        timestamp_header=ts,
        sign_header=sg,
        body=body,
        debug_route_label="shared",
        debug_raw_body=raw if dbg else None,
        debug_request_headers=dict(request.headers) if dbg else None,
    )
    if not ok:
        if early is None:
            resp_headers = mindbot_error_headers(MindbotErrorCode.DIFY_FAILED)
            mindbot_metrics.record_from_headers(resp_headers)
            return Response(status_code=500, headers=resp_headers)
        code, resp_headers = early
        if code == 404:
            resp_headers = mindbot_error_headers(MindbotErrorCode.PATH_CALLBACK_REQUIRED)
        mindbot_metrics.record_from_headers(resp_headers)
        return Response(status_code=200 if code == 404 else code, headers=resp_headers)
    if ctx is None:
        resp_headers = mindbot_error_headers(MindbotErrorCode.DIFY_FAILED)
        mindbot_metrics.record_from_headers(resp_headers)
        return Response(status_code=500, headers=resp_headers)
    schedule_dingtalk_pipeline_background(ctx)
    ack_headers = mindbot_accept_ack_headers(ctx.cfg)
    mindbot_metrics.record_from_headers(ack_headers)
    return Response(status_code=200, headers=ack_headers)


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
