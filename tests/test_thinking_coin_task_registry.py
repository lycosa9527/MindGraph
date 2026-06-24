"""Tests for thinking coin task registry helpers."""

from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.auth.thinking_coin import task_registry as registry_mod
from utils.auth.thinking_coin_config import (
    THINKING_COIN_COST_MINDMATE_TURN_DEFAULT,
    THINKING_COIN_SIGNUP_GRANT_DEFAULT,
)


@pytest.mark.asyncio
async def test_get_cost_for_request_type_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Spend costs fall back to code defaults when DB settings empty."""
    registry_mod.invalidate_task_cache()

    async def empty_settings(_db) -> dict[str, int]:
        return {}

    monkeypatch.setattr(registry_mod, "load_settings_map", empty_settings)
    cost = await registry_mod.get_cost_for_request_type(cast(AsyncSession, None), "mindmate")
    assert cost == THINKING_COIN_COST_MINDMATE_TURN_DEFAULT


@pytest.mark.asyncio
async def test_get_signup_grant_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Signup grant falls back to default when unset."""
    registry_mod.invalidate_task_cache()

    async def empty_settings(_db) -> dict[str, int]:
        return {}

    monkeypatch.setattr(registry_mod, "load_settings_map", empty_settings)
    grant = await registry_mod.get_signup_grant(cast(AsyncSession, None))
    assert grant == THINKING_COIN_SIGNUP_GRANT_DEFAULT


def test_invalidate_task_cache_is_idempotent() -> None:
    """Admin save can call invalidate repeatedly without error."""
    registry_mod.invalidate_task_cache()
    registry_mod.invalidate_task_cache()
