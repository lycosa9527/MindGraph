"""Resolve MindGraph user id for MindBot generation session registration."""

from __future__ import annotations

import logging
from typing import Optional

from repositories.dingtalk_staff_link_repo import DingtalkStaffLinkRepository
from services.utils.error_types import BACKGROUND_INFRA_ERRORS
from utils.db.rls_context import RlsContext, rls_async_session

logger = logging.getLogger(__name__)


async def resolve_mindbot_linked_user_id(
    organization_id: int,
    staff_id: str,
    *,
    callback_token: Optional[str],
) -> Optional[int]:
    """Return bound MindGraph user id for a DingTalk staff member, if any."""
    staff = (staff_id or "").strip()
    if not staff:
        return None
    ctx = RlsContext.for_mindbot_service(
        organization_id=int(organization_id),
        callback_token=callback_token,
    )
    try:
        async with rls_async_session(ctx) as session:
            repo = DingtalkStaffLinkRepository(session)
            linked = await repo.resolve_user_id_for_staff(int(organization_id), staff)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[MindBot] linked_user_lookup_failed org_id=%s staff=%s: %s",
            organization_id,
            staff[:32],
            exc,
        )
        return None
    if linked is not None and int(linked) > 0:
        return int(linked)
    return None
