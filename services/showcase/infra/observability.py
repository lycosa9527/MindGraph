"""Structured logging helpers for Showcase (Kitty-style).

Use ``logger.info(..., extra=showcase_extra(...))`` for shipper-friendly fields.
Use ``showcase_wf_log(stage, detail, ...)`` for the publish/upload/download pipeline.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

_WF_LOGGER = logging.getLogger("showcase.workflow")
_DETAIL_MAX = 240


def _env_falsy(name: str) -> bool:
    raw = os.environ.get(name, "")
    return raw.strip().lower() in ("0", "false", "no", "off")


def showcase_workflow_trace_enabled() -> bool:
    """On by default; set ``SHOWCASE_WORKFLOW_TRACE=0`` to disable."""
    return not _env_falsy("SHOWCASE_WORKFLOW_TRACE")


def showcase_extra(
    event: str,
    *,
    post_id: Optional[str] = None,
    user_id: Optional[int] = None,
    role: Optional[str] = None,
    key: Optional[str] = None,
    backend: Optional[str] = None,
    reason: Optional[str] = None,
    error_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Build ``extra=`` dict with ``showcase_``-prefixed keys."""
    out: Dict[str, Any] = {"showcase_event": event}
    if post_id is not None:
        out["showcase_post_id"] = post_id
    if user_id is not None:
        out["showcase_user_id"] = user_id
    if role is not None:
        out["showcase_role"] = role
    if key is not None:
        out["showcase_key"] = key
    if backend is not None:
        out["showcase_backend"] = backend
    if reason is not None:
        out["showcase_reason"] = reason
    if error_type is not None:
        out["showcase_error_type"] = error_type
    return out


def _clip(text: str, limit: int = _DETAIL_MAX) -> str:
    cleaned = " ".join(str(text).split()).strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1]}…"


def _short_post(post_id: Optional[str]) -> str:
    if not post_id or not isinstance(post_id, str):
        return "—"
    s = post_id.strip()
    if len(s) <= 12:
        return s
    return f"{s[:8]}…"


def showcase_wf_log(
    stage: str,
    detail: str = "",
    *,
    post_id: Optional[str] = None,
    user_id: Optional[int] = None,
    role: Optional[str] = None,
    key: Optional[str] = None,
    backend: Optional[str] = None,
) -> None:
    """
    Log one step in the Showcase create → upload → download → delete pipeline.

    Stages include: create, create_fail, create_rollback, upload_init,
    upload_init_fail, upload_complete, upload_complete_fail, upload_rollback,
    download, download_deny, withdraw, delete, assets_deleted, cache_invalidate,
    sync_scan, sync_purge.
    """
    if not showcase_workflow_trace_enabled():
        return
    parts = [f"stage={stage}", f"post={_short_post(post_id)}"]
    if user_id is not None:
        parts.append(f"uid={user_id}")
    if role:
        parts.append(f"role={role}")
    if backend:
        parts.append(f"backend={backend}")
    if key:
        parts.append(f"key={_clip(key, 64)}")
    msg_detail = _clip(detail)
    if msg_detail:
        parts.append(f"detail={msg_detail}")
    _WF_LOGGER.info("SHOWCASE_WF %s", " | ".join(parts))
