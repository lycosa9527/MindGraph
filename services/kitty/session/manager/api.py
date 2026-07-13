"""Public Kitty Session Manager facade.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from services.kitty.session.manager.action_journal import (
    append_journal_simple,
    read_session_journal,
)
from services.kitty.session.manager.align import (
    build_kitty_session_snapshot,
    require_aligned_for_verified_edit,
    resolve_promote_target,
)
from services.kitty.session.manager.redis_sot import (
    sot_get_desktop_focus,
    sot_set_desktop_focus,
)
from services.kitty.session.manager.types import (
    KittyAlignResult,
    KittyIngressOwner,
    KittySessionSnapshot,
)
from services.kitty.session.manager.ws_control import attach_lane, detach_lane


class KittySessionManager:
    """Control-plane facade for alignment, journal, and WS pairing leases."""

    async def snapshot(self, user_id: int, scope: str) -> KittySessionSnapshot:
        """Build pairing/alignment snapshot."""
        return await build_kitty_session_snapshot(user_id, scope)

    async def require_aligned_for_verified_edit(
        self,
        user_id: int,
        scope: str,
        *,
        voice_session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        action: Optional[str] = None,
    ) -> KittyAlignResult:
        """Gate verified diagram mutations."""
        return await require_aligned_for_verified_edit(
            user_id,
            scope,
            voice_session_id=voice_session_id,
            request_id=request_id,
            action=action,
        )

    async def require_desktop_ingress_allowed(
        self,
        user_id: int,
        scope: str,
        *,
        voice_session_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> KittyAlignResult:
        """
        S14: when mobile owns same-scope ingress, desktop typed/ASR text is rejected.

        Canvas-owner mutation apply is unaffected (separate WS path).
        """
        snapshot = await build_kitty_session_snapshot(user_id, scope)
        scope_key = snapshot.requested_scope
        mobile_on_scope = bool(
            snapshot.mobile_active
            and (
                snapshot.mobile_primary_scope == scope_key
                or scope_key in snapshot.mobile_scopes
            )
        )
        if (
            snapshot.ingress_owner == KittyIngressOwner.MOBILE
            and mobile_on_scope
        ):
            await append_journal_simple(
                kind="ingress_rejected",
                user_id=user_id,
                diagram_scope=scope_key,
                voice_session_id=voice_session_id,
                request_id=request_id,
                lane="desktop",
                outcome="mobile_owns_ingress",
                detail={"ingress_owner": "mobile"},
            )
            return KittyAlignResult(
                ok=False,
                snapshot=snapshot,
                error_code="mobile_owns_ingress",
                message="Mobile Kitty owns edit input for this diagram",
            )
        return KittyAlignResult(ok=True, snapshot=snapshot)

    def resolve_promote_target(
        self,
        snapshot: KittySessionSnapshot,
        ephemeral_scope: str,
    ) -> Optional[str]:
        """Library id to promote into when desktop saved an ephemeral session."""
        return resolve_promote_target(snapshot, ephemeral_scope)

    async def get_desktop_focus(
        self,
        user_id: int,
    ) -> Tuple[Optional[str], Optional[int]]:
        """Read Redis desktop_focus via SoT wrapper."""
        return await sot_get_desktop_focus(user_id)

    async def set_desktop_focus(
        self,
        user_id: int,
        diagram_library_id: Optional[str],
    ) -> Tuple[Optional[str], Optional[int]]:
        """Write Redis desktop_focus via SoT wrapper; return current value."""
        await sot_set_desktop_focus(user_id, diagram_library_id)
        return await sot_get_desktop_focus(user_id)

    async def attach(
        self,
        *,
        user_id: int,
        scope: str,
        lane: str,
        voice_session_id: Optional[str] = None,
        canvas_owner: bool = False,
    ) -> None:
        """WS start: mark Redis pairing leases."""
        await attach_lane(
            user_id=user_id,
            scope=scope,
            lane=lane,
            voice_session_id=voice_session_id,
            canvas_owner=canvas_owner,
        )

    async def detach(
        self,
        *,
        user_id: int,
        scope: str,
        lane: str,
        voice_session_id: Optional[str] = None,
        canvas_owner: bool = False,
    ) -> None:
        """WS end: clear Redis pairing leases."""
        await detach_lane(
            user_id=user_id,
            scope=scope,
            lane=lane,
            voice_session_id=voice_session_id,
            canvas_owner=canvas_owner,
        )

    async def begin_ingress(
        self,
        *,
        user_id: int,
        scope: str,
        request_id: str,
        source: str,
        text: str,
        lane: Optional[str] = None,
        voice_session_id: Optional[str] = None,
        utterance_id: Optional[str] = None,
    ) -> None:
        """Record user ASR/typed ingress before route/apply."""
        await append_journal_simple(
            kind="ingress",
            user_id=user_id,
            diagram_scope=scope,
            lane=lane,
            voice_session_id=voice_session_id,
            request_id=request_id,
            utterance_id=utterance_id,
            ingress_source=source,
            text=text,
        )

    async def reject_ingress(
        self,
        *,
        user_id: int,
        scope: str,
        request_id: Optional[str],
        reason: str,
        text: Optional[str] = None,
        lane: Optional[str] = None,
        voice_session_id: Optional[str] = None,
        ingress_source: Optional[str] = None,
    ) -> None:
        """Journal a blocked ingress attempt (create-phase, mobile-owns, etc.)."""
        await append_journal_simple(
            kind="ingress_rejected",
            user_id=user_id,
            diagram_scope=scope,
            lane=lane,
            voice_session_id=voice_session_id,
            request_id=request_id,
            ingress_source=ingress_source,
            text=text,
            outcome=reason,
        )

    async def journal_promote(
        self,
        *,
        user_id: int,
        from_scope: str,
        library_id: str,
        lane: Optional[str] = None,
        voice_session_id: Optional[str] = None,
    ) -> None:
        """Record ephemeral → library promote (S3)."""
        await append_journal_simple(
            kind="promote",
            user_id=user_id,
            diagram_scope=library_id,
            lane=lane,
            voice_session_id=voice_session_id,
            library_id=library_id,
            outcome="promoted",
            detail={"from_scope": from_scope, "to_library_id": library_id},
        )

    async def link_mutation(
        self,
        *,
        user_id: int,
        scope: str,
        mutation_id: str,
        request_id: Optional[str] = None,
        action: Optional[str] = None,
        voice_session_id: Optional[str] = None,
        lane: Optional[str] = None,
        outcome: str = "out",
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Correlate ``mutation_id`` with the active ``request_id`` (out or ack)."""
        kind = "mutation_ack" if outcome == "ack" else "mutation_out"
        await append_journal_simple(
            kind=kind,
            user_id=user_id,
            diagram_scope=scope,
            lane=lane,
            voice_session_id=voice_session_id,
            request_id=request_id,
            action=action,
            mutation_id=mutation_id,
            outcome=outcome,
            detail=detail,
        )

    async def journal_actions(
        self,
        user_id: int,
        scope: str,
        *,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Read hot journal for debug / FE."""
        return await read_session_journal(user_id, scope, limit=limit)


_MANAGER = KittySessionManager()


def get_kitty_session_manager() -> KittySessionManager:
    """Process-wide Session Manager singleton."""
    return _MANAGER
