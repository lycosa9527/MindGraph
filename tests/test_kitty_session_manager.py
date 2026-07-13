"""Unit tests for Kitty Session Manager align + promote helpers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from services.kitty.session.manager.align import (
    build_kitty_session_snapshot,
    require_aligned_for_verified_edit,
    resolve_promote_target,
)
from services.kitty.session.manager.api import KittySessionManager
from services.kitty.session.manager.types import (
    KittyAlignment,
    KittyIngressOwner,
    KittySessionSnapshot,
)
from tests.typing_helpers import mock_await_kwargs


@pytest.mark.asyncio
async def test_snapshot_desktop_only_when_owner_present() -> None:
    """Desktop canvas owner without mobile → desktop_only."""
    with (
        patch(
            "services.kitty.session.manager.align.sot_get_desktop_focus",
            AsyncMock(return_value=("lib-a", int(time.time()))),
        ),
        patch(
            "services.kitty.session.manager.align.sot_read_mobile_active",
            AsyncMock(return_value={"active": False, "scopes": [], "primary_scope": None}),
        ),
        patch(
            "services.kitty.session.manager.align.canvas_owner_available",
            AsyncMock(return_value=True),
        ),
    ):
        snap = await build_kitty_session_snapshot(3, "lib-a")

    assert snap.alignment == KittyAlignment.DESKTOP_ONLY
    assert snap.canvas_owner_present is True
    assert snap.ingress_owner == KittyIngressOwner.DESKTOP


@pytest.mark.asyncio
async def test_snapshot_scope_divergence_mobile_a_desktop_b() -> None:
    """Mobile primary A + fresh focus B → scope_divergence."""
    with (
        patch(
            "services.kitty.session.manager.align.sot_get_desktop_focus",
            AsyncMock(return_value=("lib-b", int(time.time()))),
        ),
        patch(
            "services.kitty.session.manager.align.sot_read_mobile_active",
            AsyncMock(
                return_value={
                    "active": True,
                    "scopes": ["lib-a"],
                    "primary_scope": "lib-a",
                }
            ),
        ),
        patch(
            "services.kitty.session.manager.align.canvas_owner_available",
            AsyncMock(return_value=False),
        ),
    ):
        snap = await build_kitty_session_snapshot(3, "lib-a")

    assert snap.alignment == KittyAlignment.SCOPE_DIVERGENCE
    assert snap.error_code == "scope_divergence"
    assert snap.ingress_owner == KittyIngressOwner.MOBILE


@pytest.mark.asyncio
async def test_snapshot_same_scope_mobile_owns_ingress() -> None:
    """Same library + mobile active + owner → aligned, mobile ingress."""
    with (
        patch(
            "services.kitty.session.manager.align.sot_get_desktop_focus",
            AsyncMock(return_value=("lib-a", int(time.time()))),
        ),
        patch(
            "services.kitty.session.manager.align.sot_read_mobile_active",
            AsyncMock(
                return_value={
                    "active": True,
                    "scopes": ["lib-a"],
                    "primary_scope": "lib-a",
                }
            ),
        ),
        patch(
            "services.kitty.session.manager.align.canvas_owner_available",
            AsyncMock(return_value=True),
        ),
    ):
        snap = await build_kitty_session_snapshot(3, "lib-a")

    assert snap.alignment == KittyAlignment.ALIGNED_LIBRARY
    assert snap.ingress_owner == KittyIngressOwner.MOBILE


@pytest.mark.asyncio
async def test_require_aligned_fails_without_owner() -> None:
    """Verified edit gate fails closed with no_owner."""
    with (
        patch(
            "services.kitty.session.manager.align.sot_get_desktop_focus",
            AsyncMock(return_value=(None, None)),
        ),
        patch(
            "services.kitty.session.manager.align.sot_read_mobile_active",
            AsyncMock(
                return_value={
                    "active": True,
                    "scopes": ["ephem-1"],
                    "primary_scope": "ephem-1",
                }
            ),
        ),
        patch(
            "services.kitty.session.manager.align.canvas_owner_available",
            AsyncMock(return_value=False),
        ),
        patch(
            "services.kitty.session.manager.align.append_journal_simple",
            AsyncMock(),
        ),
    ):
        result = await require_aligned_for_verified_edit(3, "ephem-1", action="add_node")

    assert result.ok is False
    assert result.error_code == "no_owner"


@pytest.mark.asyncio
async def test_require_aligned_ok_with_owner() -> None:
    """Owner present → verified edit allowed."""
    with (
        patch(
            "services.kitty.session.manager.align.sot_get_desktop_focus",
            AsyncMock(return_value=("lib-a", int(time.time()))),
        ),
        patch(
            "services.kitty.session.manager.align.sot_read_mobile_active",
            AsyncMock(
                return_value={
                    "active": True,
                    "scopes": ["lib-a"],
                    "primary_scope": "lib-a",
                }
            ),
        ),
        patch(
            "services.kitty.session.manager.align.canvas_owner_available",
            AsyncMock(return_value=True),
        ),
    ):
        result = await require_aligned_for_verified_edit(3, "lib-a")

    assert result.ok is True


def test_resolve_promote_target_from_ephemeral() -> None:
    """Desktop focus library promotes mobile ephemeral session."""
    snap = KittySessionSnapshot(
        user_id=3,
        requested_scope="ephem-1",
        desktop_focus_library_id="lib-saved",
        desktop_focus_updated_at=int(time.time()),
        mobile_active=True,
        mobile_scopes=["ephem-1"],
        mobile_primary_scope="ephem-1",
        canvas_owner_present=True,
        alignment=KittyAlignment.ALIGNED_EPHEMERAL,
        ingress_owner=KittyIngressOwner.MOBILE,
    )
    assert resolve_promote_target(snap, "ephem-1") == "lib-saved"
    assert resolve_promote_target(snap, "other") is None


@pytest.mark.asyncio
async def test_begin_ingress_and_link_mutation_journal() -> None:
    """Ingress + mutation_out share request_id in the action journal."""
    mgr = KittySessionManager()
    calls: list[dict] = []

    async def _capture(**kwargs: object) -> None:
        calls.append(dict(kwargs))

    with patch(
        "services.kitty.session.manager.api.append_journal_simple",
        AsyncMock(side_effect=_capture),
    ):
        await mgr.begin_ingress(
            user_id=3,
            scope="lib-a",
            request_id="req-1",
            source="asr",
            text="加一个分支",
            lane="mobile",
            voice_session_id="vs-1",
            utterance_id="utt-1",
        )
        await mgr.link_mutation(
            user_id=3,
            scope="lib-a",
            mutation_id="mut-9",
            request_id="req-1",
            action="add_node",
            voice_session_id="vs-1",
            lane="mobile",
            outcome="out",
        )
        await mgr.link_mutation(
            user_id=3,
            scope="lib-a",
            mutation_id="mut-9",
            request_id="req-1",
            voice_session_id="vs-1",
            outcome="ack",
            detail={"verified": True},
        )

    assert calls[0]["kind"] == "ingress"
    assert calls[0]["request_id"] == "req-1"
    assert calls[0]["ingress_source"] == "asr"
    assert calls[0]["utterance_id"] == "utt-1"
    assert calls[1]["kind"] == "mutation_out"
    assert calls[1]["mutation_id"] == "mut-9"
    assert calls[1]["request_id"] == "req-1"
    assert calls[2]["kind"] == "mutation_ack"
    assert calls[2]["outcome"] == "ack"


@pytest.mark.asyncio
async def test_require_desktop_ingress_rejected_when_mobile_owns() -> None:
    """S14: desktop text blocked when mobile owns same-scope ingress."""
    mgr = KittySessionManager()
    with (
        patch(
            "services.kitty.session.manager.api.build_kitty_session_snapshot",
            AsyncMock(
                return_value=KittySessionSnapshot(
                    user_id=3,
                    requested_scope="lib-a",
                    desktop_focus_library_id="lib-a",
                    desktop_focus_updated_at=int(time.time()),
                    mobile_active=True,
                    mobile_scopes=["lib-a"],
                    mobile_primary_scope="lib-a",
                    canvas_owner_present=True,
                    alignment=KittyAlignment.ALIGNED_LIBRARY,
                    ingress_owner=KittyIngressOwner.MOBILE,
                )
            ),
        ),
        patch(
            "services.kitty.session.manager.api.append_journal_simple",
            AsyncMock(),
        ) as journal,
    ):
        result = await mgr.require_desktop_ingress_allowed(3, "lib-a", request_id="req-x")

    assert result.ok is False
    assert result.error_code == "mobile_owns_ingress"
    journal.assert_awaited()
    assert mock_await_kwargs(journal)["kind"] == "ingress_rejected"


@pytest.mark.asyncio
async def test_journal_promote_records_from_scope() -> None:
    """S3 promote journals from_scope → library_id."""
    mgr = KittySessionManager()
    with patch(
        "services.kitty.session.manager.api.append_journal_simple",
        AsyncMock(),
    ) as journal:
        await mgr.journal_promote(
            user_id=3,
            from_scope="ephem-1",
            library_id="lib-saved",
            lane="mobile",
        )

    journal.assert_awaited_once()
    promote_kwargs = mock_await_kwargs(journal)
    assert promote_kwargs["kind"] == "promote"
    assert promote_kwargs["library_id"] == "lib-saved"
    assert promote_kwargs["detail"]["from_scope"] == "ephem-1"
