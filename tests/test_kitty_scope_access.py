"""Tests for Kitty WebSocket scope access control."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.kitty.infra.scope.kitty_scope_access import (
    scope_looks_like_library_uuid,
    user_may_access_kitty_scope,
)


def test_scope_looks_like_library_uuid() -> None:
    """Test scope looks like library uuid."""
    assert scope_looks_like_library_uuid("550e8400-e29b-41d4-a716-446655440000") is True
    assert scope_looks_like_library_uuid("ephemeral-scope-1") is False


@pytest.mark.asyncio
async def test_user_may_access_owned_library_scope() -> None:
    """Test user may access owned library scope."""
    scope = "550e8400-e29b-41d4-a716-446655440000"
    cache = AsyncMock()
    cache.get_diagram = AsyncMock(return_value={"id": scope})
    with patch("services.kitty.infra.scope.kitty_scope_access.get_diagram_cache", return_value=cache):
        allowed = await user_may_access_kitty_scope(7, scope)
    assert allowed is True


@pytest.mark.asyncio
async def test_user_denied_other_users_library_scope() -> None:
    """Test user denied other users library scope."""
    scope = "550e8400-e29b-41d4-a716-446655440000"
    cache = AsyncMock()
    cache.get_diagram = AsyncMock(return_value=None)
    with (
        patch("services.kitty.infra.scope.kitty_scope_access.get_diagram_cache", return_value=cache),
        patch(
            "services.kitty.infra.scope.kitty_scope_access._library_diagram_owner_id",
            new=AsyncMock(return_value=99),
        ),
    ):
        allowed = await user_may_access_kitty_scope(7, scope)
    assert allowed is False


@pytest.mark.asyncio
async def test_ephemeral_uuid_scope_allowed_when_not_in_library() -> None:
    """Test ephemeral uuid scope allowed when not in library."""
    scope = "550e8400-e29b-41d4-a716-446655440000"
    cache = AsyncMock()
    cache.get_diagram = AsyncMock(return_value=None)
    with (
        patch("services.kitty.infra.scope.kitty_scope_access.get_diagram_cache", return_value=cache),
        patch(
            "services.kitty.infra.scope.kitty_scope_access._library_diagram_owner_id",
            new=AsyncMock(return_value=None),
        ),
    ):
        allowed = await user_may_access_kitty_scope(7, scope)
    assert allowed is True
