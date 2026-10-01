"""
MindBot Dify client and chat inputs, aligned with web MindMate.

Org-linked bots use the live MindMate resolver (active server, failover, org
timeout). Every turn sends the same three Start variables as web chat.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from clients.dify import AsyncDifyClient
from models.domain.mindbot_config import OrganizationMindbotConfig
from services.dify.org_dify_inputs import apply_persona_inputs_for_organization_id
from services.dify.org_mindmate_client import resolve_mindmate_dify_client
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)


def _parse_dify_inputs_json(raw: object) -> Optional[dict[str, Any]]:
    """Parse optional JSON object of extra Dify ``inputs`` from a config row."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("[MindBot] dify_inputs_json invalid JSON; ignoring")
        return None
    if not isinstance(parsed, dict):
        logger.warning("[MindBot] dify_inputs_json must be a JSON object; ignoring")
        return None
    return parsed


async def open_mindbot_dify_client(cfg: OrganizationMindbotConfig) -> AsyncDifyClient:
    """
    Open the Dify client for one MindBot turn.

    When the bot uses school MindMate settings, this is the same client web
    chat builds. A custom bot keeps the URL and key stored on its config row.
    """
    if bool(getattr(cfg, "use_org_dify_settings", True)):
        async with system_rls_session() as db:
            return await resolve_mindmate_dify_client(db, int(cfg.organization_id))
    raw_timeout = getattr(cfg, "dify_timeout_seconds", 300)
    timeout = max(5, min(600, int(300 if raw_timeout is None else raw_timeout)))
    return AsyncDifyClient(
        api_key=(getattr(cfg, "dify_api_key", None) or "").strip(),
        api_url=(getattr(cfg, "dify_api_base_url", None) or "").strip(),
        timeout=timeout,
    )


async def mindbot_dify_chat_inputs(
    cfg: OrganizationMindbotConfig,
    *,
    dify_user_id: str,
    dify_conversation_id: Optional[str],
) -> dict[str, Any]:
    """
    Build Dify ``inputs`` for one MindBot turn.

    Extra keys from ``dify_inputs_json`` are kept. ``mg_dify_user``,
    ``mg_conversation_id``, and the three persona Start variables are written
    the same way as web MindMate, and they overwrite any spoofed copies.
    """
    parsed = _parse_dify_inputs_json(getattr(cfg, "dify_inputs_json", None))
    inputs: dict[str, Any] = dict(parsed) if parsed else {}
    inputs["mg_dify_user"] = dify_user_id
    conversation_id = (dify_conversation_id or "").strip()
    if conversation_id:
        inputs["mg_conversation_id"] = conversation_id
    await apply_persona_inputs_for_organization_id(inputs, cfg.organization_id)
    return inputs
