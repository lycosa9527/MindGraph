"""Hybrid sync vs background job routing for MindMate export."""

from __future__ import annotations

from services.dify.export.export_config import SYNC_MAX_CONVERSATIONS, SYNC_MAX_USERS
from services.dify.export.types import ExportScope


def should_use_background_job(
    scope: ExportScope,
    user_count: int,
    *,
    conversation_count: int | None = None,
) -> bool:
    """Return True when export should run as a background job instead of inline sync."""
    if scope == "all":
        return True
    if user_count > SYNC_MAX_USERS:
        return True
    if conversation_count is not None and conversation_count > SYNC_MAX_CONVERSATIONS:
        return True
    return False
