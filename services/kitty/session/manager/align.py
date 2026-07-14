"""Session alignment snapshot and verified-edit gate.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import time
from typing import List, Optional

from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.kitty.session.canvas_owner import canvas_owner_available
from services.kitty.session.manager.action_journal import append_journal_simple
from services.kitty.session.manager.redis_sot import (
    sot_get_desktop_focus,
    sot_read_mobile_active,
)
from services.kitty.session.manager.types import (
    KittyAlignResult,
    KittyAlignment,
    KittyIngressOwner,
    KittySessionSnapshot,
)

# Desktop focus trusted only when recently refreshed (matches FE DESKTOP_FOCUS_FRESH_SEC).
_DESKTOP_FOCUS_FRESH_SEC = 180


def _focus_is_fresh(updated_at: Optional[int]) -> bool:
    if updated_at is None:
        return False
    age = int(time.time()) - int(updated_at)
    return 0 <= age <= _DESKTOP_FOCUS_FRESH_SEC


def _scopes_list(mobile: dict) -> List[str]:
    raw = mobile.get("scopes")
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


async def build_kitty_session_snapshot(
    user_id: int,
    requested_scope: str,
) -> KittySessionSnapshot:
    """Build alignment snapshot for ``user_id`` + requested diagram scope."""
    scope = normalize_kitty_diagram_session_id(requested_scope) or str(requested_scope).strip()
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        uid = 0

    focus_lib, focus_ts = (None, None)
    if uid > 0:
        focus_lib, focus_ts = await sot_get_desktop_focus(uid)
        if focus_lib is not None and not _focus_is_fresh(focus_ts):
            focus_lib = None

    if uid > 0:
        mobile = await sot_read_mobile_active(uid)
    else:
        mobile = {"active": False, "scopes": [], "primary_scope": None}

    mobile_active = bool(mobile.get("active"))
    mobile_scopes = _scopes_list(mobile)
    primary = mobile.get("primary_scope")
    mobile_primary = primary.strip() if isinstance(primary, str) and primary.strip() else None
    mobile_on_scope = bool(scope) and mobile_active and scope in mobile_scopes

    owner_present = False
    if uid > 0 and scope:
        owner_present = await canvas_owner_available(uid, scope)

    cross_library = bool(mobile_active and mobile_primary and focus_lib and mobile_primary != focus_lib)

    ingress_owner = KittyIngressOwner.MOBILE if mobile_on_scope else KittyIngressOwner.DESKTOP
    error_code: Optional[str] = None

    if not scope:
        alignment = KittyAlignment.EMPTY
        error_code = "empty_scope"
    elif cross_library and scope in (mobile_primary, focus_lib):
        alignment = KittyAlignment.SCOPE_DIVERGENCE
        error_code = "scope_divergence"
    elif owner_present and mobile_on_scope:
        alignment = KittyAlignment.ALIGNED_LIBRARY if focus_lib == scope else KittyAlignment.ALIGNED_EPHEMERAL
    elif owner_present and not mobile_active:
        alignment = KittyAlignment.DESKTOP_ONLY
    elif owner_present and mobile_active and not mobile_on_scope:
        alignment = KittyAlignment.MISMATCH
        error_code = "scope_mismatch"
    elif mobile_on_scope and not owner_present:
        alignment = KittyAlignment.NO_OWNER
        error_code = "no_owner"
    elif mobile_active and not owner_present:
        alignment = KittyAlignment.MOBILE_ONLY
        error_code = "no_owner"
    else:
        alignment = KittyAlignment.EMPTY
        error_code = "no_owner"

    return KittySessionSnapshot(
        user_id=uid,
        requested_scope=scope,
        desktop_focus_library_id=focus_lib,
        desktop_focus_updated_at=focus_ts,
        mobile_active=mobile_active,
        mobile_scopes=mobile_scopes,
        mobile_primary_scope=mobile_primary,
        canvas_owner_present=owner_present,
        alignment=alignment,
        ingress_owner=ingress_owner,
        error_code=error_code,
    )


async def require_aligned_for_verified_edit(
    user_id: int,
    requested_scope: str,
    *,
    voice_session_id: Optional[str] = None,
    request_id: Optional[str] = None,
    action: Optional[str] = None,
) -> KittyAlignResult:
    """
    Gate verified diagram mutations.

    Requires a live canvas owner for ``requested_scope``. Cross-library divergence
    is reported on the snapshot for FE sync UI; edits still fail closed with
    ``no_owner`` when the owner is not on this scope.
    """
    snapshot = await build_kitty_session_snapshot(user_id, requested_scope)

    if snapshot.canvas_owner_present:
        if snapshot.alignment == KittyAlignment.SCOPE_DIVERGENCE:
            # Owner is on this scope but devices disagree on pairing focus —
            # allow apply on this scope; FE should still nudge sync.
            await append_journal_simple(
                kind="align_warn",
                user_id=user_id,
                diagram_scope=snapshot.requested_scope,
                voice_session_id=voice_session_id,
                request_id=request_id,
                action=action,
                outcome="scope_divergence_owner_ok",
                detail={
                    "mobile_primary_scope": snapshot.mobile_primary_scope,
                    "desktop_focus_library_id": snapshot.desktop_focus_library_id,
                },
            )
        return KittyAlignResult(ok=True, snapshot=snapshot)

    code = snapshot.error_code or "no_owner"
    if snapshot.alignment == KittyAlignment.SCOPE_DIVERGENCE:
        code = "scope_divergence"
    await append_journal_simple(
        kind="align_reject",
        user_id=user_id,
        diagram_scope=snapshot.requested_scope,
        voice_session_id=voice_session_id,
        request_id=request_id,
        action=action,
        outcome=code,
        detail={
            "mobile_primary_scope": snapshot.mobile_primary_scope,
            "desktop_focus_library_id": snapshot.desktop_focus_library_id,
        },
    )
    message = (
        "Mobile and desktop are on different library diagrams"
        if code == "scope_divergence"
        else "Desktop canvas owner not connected for this scope"
    )
    return KittyAlignResult(
        ok=False,
        snapshot=snapshot,
        error_code=code,
        message=message,
    )


def resolve_promote_target(
    snapshot: KittySessionSnapshot,
    ephemeral_scope: str,
) -> Optional[str]:
    """
    If mobile still holds ``ephemeral_scope`` but desktop focus has a fresh library id,
    return that library id as the promote target.
    """
    ephemeral = str(ephemeral_scope or "").strip()
    if not ephemeral:
        return None
    lib = snapshot.desktop_focus_library_id
    if not lib or lib == ephemeral:
        return None
    if snapshot.mobile_primary_scope == ephemeral or ephemeral in snapshot.mobile_scopes:
        return lib
    return None
