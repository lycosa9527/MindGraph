"""Claim generate_dingtalk previews into the authenticated user's library."""

from __future__ import annotations

import logging
from typing import Optional

from models.domain.auth import User
from services.diagram.generation_library_save import SAVE_LIMIT_REACHED, try_save_diagram_to_library
from services.diagram.generation_skip_registry import (
    get_generation_preview_outcome,
    update_generation_preview_diagram_id,
)

logger = logging.getLogger(__name__)

CLAIM_ERROR_NOT_FOUND = "preview_not_found"
CLAIM_ERROR_NO_SPEC = "preview_not_reclaimable"
CLAIM_ERROR_LIMIT = "limit_reached"
CLAIM_ERROR_SAVE = "save_error"


async def claim_generation_preview_for_user(
    unique_id: str,
    current_user: User,
) -> tuple[Optional[str], str]:
    """
    Save a pending generate_dingtalk preview for the logged-in MindMate user.

    Returns ``(diagram_id, error_code)``. ``error_code`` is empty on success.
    """
    uid = (unique_id or "").strip()
    if not uid:
        return None, CLAIM_ERROR_NOT_FOUND

    outcome = await get_generation_preview_outcome(uid)
    if outcome is None:
        return None, CLAIM_ERROR_NOT_FOUND

    # Owner guard: a preview tied to a specific MindGraph user may only be claimed by that
    # user. Previews with no recorded owner (e.g. no_user / unbound_staff) stay claimable by
    # any authenticated user. Treat a mismatch as not-found to avoid leaking preview existence.
    recorded_user_id = outcome.get("user_id")
    if (
        isinstance(recorded_user_id, int)
        and recorded_user_id > 0
        and recorded_user_id != int(current_user.id)
    ):
        return None, CLAIM_ERROR_NOT_FOUND

    existing_id = outcome.get("diagram_id")
    if isinstance(existing_id, str) and existing_id.strip():
        return existing_id.strip(), ""

    spec = outcome.get("spec")
    if not isinstance(spec, dict) or not spec:
        return None, CLAIM_ERROR_NO_SPEC

    org_raw = getattr(current_user, "organization_id", None)
    org_id = int(org_raw) if org_raw is not None else None
    title = str(outcome.get("title") or "Diagram").strip()[:200] or "Diagram"
    diagram_type = str(outcome.get("diagram_type") or "mind_map").strip() or "mind_map"
    language = str(outcome.get("language") or "zh").strip() or "zh"

    saved_id = await try_save_diagram_to_library(
        int(current_user.id),
        title=title,
        diagram_type=diagram_type,
        spec=spec,
        language=language,
        organization_id=org_id,
        log_prefix="generation_library_claim",
    )
    if saved_id == SAVE_LIMIT_REACHED:
        return None, CLAIM_ERROR_LIMIT
    if not saved_id:
        return None, CLAIM_ERROR_SAVE

    await update_generation_preview_diagram_id(uid, saved_id)
    logger.info(
        "[GenerateDingTalk] library_claim_ok preview=%s user=%s diagram=%s",
        uid,
        int(current_user.id),
        saved_id,
    )
    return saved_id, ""
