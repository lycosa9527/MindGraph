"""Public feature flags must not leak workshop preview org ids to guests."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from routers.api import config as config_mod


@pytest.mark.asyncio
async def test_anonymous_workshop_preview_org_ids_are_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Doc hardening: guests see an empty preview-org list."""
    monkeypatch.setattr(
        config_mod,
        "load_feature_org_access_map",
        AsyncMock(return_value={}),
    )
    response = await config_mod.get_feature_flags(current_user=None)
    assert response.workshop_chat_preview_org_ids == []
