"""Collab workshop blocks canvas AI generation for all users."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from routers.api.diagram_generation import assert_collab_blocks_canvas_ai
from tests.typing_helpers import as_user


@pytest.mark.asyncio
async def test_assert_collab_blocks_non_superadmin_during_workshop() -> None:
    """Non-superadmin users are blocked during live workshop."""
    user = as_user(SimpleNamespace(id=1, role="teacher"))
    with patch(
        "routers.api.diagram_generation._query_diagram_ownership",
        new=AsyncMock(return_value=("WS-CODE", 1)),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await assert_collab_blocks_canvas_ai("diagram-1", user)
    assert exc_info.value.status_code == 403
    assert "live collaboration" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_assert_collab_allows_superadmin_during_workshop() -> None:
    """Superadmin users may use canvas AI during live workshop."""
    user = as_user(SimpleNamespace(id=1, role="superadmin"))
    with patch(
        "routers.api.diagram_generation._query_diagram_ownership",
        new=AsyncMock(return_value=("WS-CODE", 1)),
    ):
        await assert_collab_blocks_canvas_ai("diagram-1", user)


@pytest.mark.asyncio
async def test_assert_collab_allows_when_no_workshop_code() -> None:
    """Canvas AI is allowed when the diagram has no workshop code."""
    user = as_user(SimpleNamespace(id=1, role="teacher"))
    with patch(
        "routers.api.diagram_generation._query_diagram_ownership",
        new=AsyncMock(return_value=(None, 1)),
    ):
        await assert_collab_blocks_canvas_ai("diagram-1", user)
