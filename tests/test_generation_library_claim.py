"""Tests for MindMate reclaim of generate_dingtalk previews."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.diagram.generation_library_claim import (
    CLAIM_ERROR_NOT_FOUND,
    CLAIM_ERROR_NO_SPEC,
    claim_generation_preview_for_user,
)


@pytest.mark.asyncio
async def test_claim_returns_existing_diagram_id() -> None:
    """When outcome already has diagram_id, return it without saving."""
    user = MagicMock()
    user.id = 3
    user.organization_id = 5
    with patch(
        "services.diagram.generation_library_claim.get_generation_preview_outcome",
        new=AsyncMock(
            return_value={
                "diagram_id": "550e8400-e29b-41d4-a716-446655440000",
                "spec": None,
            }
        ),
    ):
        diagram_id, err = await claim_generation_preview_for_user("deadbeef", user)
    assert err == ""
    assert diagram_id == "550e8400-e29b-41d4-a716-446655440000"


@pytest.mark.asyncio
async def test_claim_missing_preview() -> None:
    """Missing Redis outcome returns preview_not_found."""
    user = MagicMock()
    user.id = 3
    with patch(
        "services.diagram.generation_library_claim.get_generation_preview_outcome",
        new=AsyncMock(return_value=None),
    ):
        diagram_id, err = await claim_generation_preview_for_user("missing", user)
    assert diagram_id is None
    assert err == CLAIM_ERROR_NOT_FOUND


@pytest.mark.asyncio
async def test_claim_without_spec_not_reclaimable() -> None:
    """Outcome without spec cannot be reclaimed."""
    user = MagicMock()
    user.id = 3
    with patch(
        "services.diagram.generation_library_claim.get_generation_preview_outcome",
        new=AsyncMock(return_value={"reason": "no_user", "spec": None}),
    ):
        diagram_id, err = await claim_generation_preview_for_user("deadbeef", user)
    assert diagram_id is None
    assert err == CLAIM_ERROR_NO_SPEC
