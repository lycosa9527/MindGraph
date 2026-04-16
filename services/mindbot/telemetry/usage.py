"""Persist MindBot callback analytics (DingTalk identity + optional Dify token usage).

Usage events are written in their own ``AsyncSessionLocal`` so a persistence
failure never poisons the caller's DB session or crashes the pipeline.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from config.database import AsyncSessionLocal
from models.domain.mindbot_usage import MindbotUsageEvent
from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.errors import MindbotErrorCode
from services.mindbot.platforms.dingtalk import extract_dingtalk_sender_profile
from utils.env_helpers import env_bool

logger = logging.getLogger(__name__)


def _clip_opt(value: str, max_len: int) -> Optional[str]:
    s = value.strip()
    if not s:
        return None
    return s[:max_len]


def mindbot_usage_tracking_enabled() -> bool:
    return env_bool("MINDBOT_USAGE_TRACKING", True)


async def persist_mindbot_usage_event(
    *,
    cfg: OrganizationMindbotConfig,
    body: dict[str, Any],
    text_in: str,
    conversation_id_dt: str,
    user_id: str,
    streaming: bool,
    error_code: MindbotErrorCode,
    reply_text: str,
    dify_conversation_id: Optional[str],
    started_mono: float,
    msg_id: Optional[str],
    usage: Optional[dict[str, int]],
    dingtalk_chat_scope: str,
    inbound_msg_type: str,
    conversation_user_turn: Optional[int],
) -> None:
    if not mindbot_usage_tracking_enabled():
        return
    staff_id, sender_nick, sender_ding_id = extract_dingtalk_sender_profile(body)
    duration = max(0.0, time.monotonic() - started_mono)
    pt = usage.get("prompt_tokens") if usage else None
    ct = usage.get("completion_tokens") if usage else None
    tt = usage.get("total_tokens") if usage else None
    row = MindbotUsageEvent(
        organization_id=cfg.organization_id,
        mindbot_config_id=cfg.id,
        dingtalk_staff_id=staff_id[:128],
        sender_nick=(sender_nick[:256] if sender_nick else None),
        dingtalk_sender_id=(sender_ding_id[:128] if sender_ding_id else None),
        dify_user_key=user_id[:256],
        msg_id=(msg_id[:128] if isinstance(msg_id, str) and msg_id.strip() else None),
        dingtalk_conversation_id=(
            conversation_id_dt[:256] if (conversation_id_dt or "").strip() else None
        ),
        dify_conversation_id=(
            dify_conversation_id[:128]
            if isinstance(dify_conversation_id, str) and dify_conversation_id.strip()
            else None
        ),
        error_code=error_code.value,
        streaming=streaming,
        prompt_chars=len(text_in),
        reply_chars=len(reply_text),
        duration_seconds=duration,
        prompt_tokens=pt,
        completion_tokens=ct,
        total_tokens=tt,
        dingtalk_chat_scope=_clip_opt(dingtalk_chat_scope, 16),
        inbound_msg_type=_clip_opt(inbound_msg_type, 32),
        conversation_user_turn=conversation_user_turn,
        linked_user_id=None,
    )
    try:
        async with AsyncSessionLocal() as session:
            session.add(row)
            await session.commit()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "[MindBot] usage_persist_failed org_id=%s error=%s msg_id=%s — "
            "usage event dropped; pipeline continues",
            cfg.organization_id,
            exc,
            msg_id or "",
        )
        return
    logger.debug(
        "[MindBot] usage_persisted org_id=%s error=%s duration_s=%.3f streaming=%s "
        "msg_id=%s prompt_chars=%s reply_chars=%s",
        cfg.organization_id,
        error_code.value,
        duration,
        streaming,
        msg_id or "",
        len(text_in),
        len(reply_text),
    )
