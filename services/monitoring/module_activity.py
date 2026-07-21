"""
Unified module activity tracking: Redis live + usage timeline + greppable logs.

Call sites should prefer ``track_module_activity`` / ``schedule_module_activity``
instead of wiring Redis, Postgres, and INFO logs separately.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Mapping, Optional

from models.domain.auth import User
from services.admin.user_usage_activity import (
    clip_activity_preview,
    schedule_user_usage_activity,
)
from services.redis.redis_activity_tracker import get_activity_tracker
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.auth.connection_types import HttpOrWebSocket
from utils.auth.mg_client import (
    activity_details_with_request_client,
    client_source_from_request,
)
from utils.auth.request_helpers import get_client_ip

logger = logging.getLogger(__name__)

VALID_MODULES = frozenset(
    {
        "canvas",
        "mindmate",
        "kitty",
        "knowledge",
        "doc_summary",
        "workshop",
        "askonce",
        "debateverse",
        "markets",
        "library",
        "showcase",
        "auth",
        "dingtalk",
    }
)


def _resolve_user_fields(
    user: Optional[User],
    user_id: Optional[int],
    organization_id: Optional[int],
    user_phone: Optional[str],
    user_name: Optional[str],
) -> tuple[int, Optional[int], str, Optional[str]]:
    """Normalize identity fields from a User object or explicit ids."""
    resolved_id = int(user.id) if user is not None and hasattr(user, "id") else int(user_id or 0)
    if user is not None:
        org = getattr(user, "organization_id", None)
        phone = getattr(user, "phone", None) or ""
        name = getattr(user, "name", None)
        return (
            resolved_id,
            int(org) if org is not None else organization_id,
            str(phone),
            str(name) if name else user_name,
        )
    return resolved_id, organization_id, user_phone or "", user_name


def _format_detail(detail: Optional[str], details: Optional[Mapping[str, Any]]) -> str:
    """Build a single clipped detail string for logs."""
    if detail and str(detail).strip():
        clipped = clip_activity_preview(str(detail))
        return clipped or "-"
    if not details:
        return "-"
    parts: list[str] = []
    for key in (
        "diagram_type",
        "title",
        "topic",
        "format",
        "scope",
        "channel",
        "package_id",
        "endpoint",
        "method",
        "action",
    ):
        value = details.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            parts.append(f"{key}={text}")
    if not parts:
        for key, value in details.items():
            if key in {"client_source", "user_id", "ip_address"}:
                continue
            if value is None:
                continue
            text = str(value).strip()
            if text:
                parts.append(f"{key}={text}")
            if len(parts) >= 3:
                break
    joined = " ".join(parts)
    clipped = clip_activity_preview(joined) if joined else None
    return clipped or "-"


async def track_module_activity(
    *,
    module: str,
    redis_activity_type: str,
    user: Optional[User] = None,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    user_phone: Optional[str] = None,
    user_name: Optional[str] = None,
    request: Optional[HttpOrWebSocket] = None,
    details: Optional[Mapping[str, Any]] = None,
    detail: Optional[str] = None,
    client_source: Optional[str] = None,
    usage_source: Optional[str] = None,
    usage_action: Optional[str] = None,
    title: Optional[str] = None,
    prompt_preview: Optional[str] = None,
    reply_preview: Optional[str] = None,
    diagram_type: Optional[str] = None,
    diagram_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    total_tokens: Optional[int] = None,
    success: bool = True,
    persist_usage: bool = True,
    log_info: bool = True,
) -> None:
    """
    Record Redis live activity, optional usage timeline row, and INFO log.

    Never raises to callers.
    """
    try:
        uid, org_id, phone, name = _resolve_user_fields(user, user_id, organization_id, user_phone, user_name)
        if uid <= 0:
            return

        module_key = (module or "").strip().lower()
        if module_key not in VALID_MODULES:
            module_key = "canvas"

        action_key = (redis_activity_type or "").strip() or "unknown"
        resolved_client = client_source
        if resolved_client is None and request is not None:
            resolved_client = client_source_from_request(request)
        client_label = resolved_client or "-"
        org_label = str(org_id) if org_id is not None else "-"
        detail_text = _format_detail(detail, details)

        if log_info:
            logger.info(
                "[UserActivity] user=%s action=%s module=%s client=%s org=%s detail=%s",
                uid,
                action_key,
                module_key,
                client_label,
                org_label,
                detail_text,
            )

        ip_address = None
        if request is not None:
            try:
                ip_address = get_client_ip(request)
            except BACKGROUND_INFRA_ERRORS:
                ip_address = None

        redis_details = activity_details_with_request_client(details, request)
        tracker = get_activity_tracker()
        await tracker.record_activity(
            user_id=uid,
            user_phone=phone,
            activity_type=action_key,
            details=redis_details,
            user_name=name,
            ip_address=ip_address,
            client_source=resolved_client,
        )

        if persist_usage and usage_source and usage_action:
            schedule_user_usage_activity(
                user_id=uid,
                organization_id=org_id,
                source=usage_source,
                action=usage_action,
                title=title,
                prompt_preview=prompt_preview,
                reply_preview=reply_preview,
                diagram_type=diagram_type,
                diagram_id=diagram_id,
                conversation_id=conversation_id,
                total_tokens=total_tokens,
                success=success,
            )
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug("[UserActivity] track_failed: %s", exc)


def schedule_module_activity(
    *,
    module: str,
    redis_activity_type: str,
    user: Optional[User] = None,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    user_phone: Optional[str] = None,
    user_name: Optional[str] = None,
    request: Optional[HttpOrWebSocket] = None,
    details: Optional[Mapping[str, Any]] = None,
    detail: Optional[str] = None,
    client_source: Optional[str] = None,
    usage_source: Optional[str] = None,
    usage_action: Optional[str] = None,
    title: Optional[str] = None,
    prompt_preview: Optional[str] = None,
    reply_preview: Optional[str] = None,
    diagram_type: Optional[str] = None,
    diagram_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
    total_tokens: Optional[int] = None,
    success: bool = True,
    persist_usage: bool = True,
    log_info: bool = True,
) -> None:
    """Fire-and-forget wrapper for request/WS hot paths."""
    asyncio.create_task(
        track_module_activity(
            module=module,
            redis_activity_type=redis_activity_type,
            user=user,
            user_id=user_id,
            organization_id=organization_id,
            user_phone=user_phone,
            user_name=user_name,
            request=request,
            details=details,
            detail=detail,
            client_source=client_source,
            usage_source=usage_source,
            usage_action=usage_action,
            title=title,
            prompt_preview=prompt_preview,
            reply_preview=reply_preview,
            diagram_type=diagram_type,
            diagram_id=diagram_id,
            conversation_id=conversation_id,
            total_tokens=total_tokens,
            success=success,
            persist_usage=persist_usage,
            log_info=log_info,
        )
    )
