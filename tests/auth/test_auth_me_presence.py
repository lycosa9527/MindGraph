"""GET /api/auth/me must pin signed-in presence without failing the profile."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from routers.auth.session import get_me


def _profile_user() -> User:
    """Minimal user object for the /me payload."""
    user = User(id=3, password_hash="x")
    user.phone = "13800000000"
    user.email = None
    user.name = "Tester"
    user.avatar = None
    user.role = "teacher"
    user.organization_id = None
    user.login_password_set = True
    user.last_login = None
    user.ui_language = "zh"
    user.prompt_language = "zh"
    user.ui_version = "chinese"
    user.match_prompt_to_ui = True
    user.allows_simplified_chinese = True
    user.education_stage = None
    user.ai_content_level = None
    return user


@pytest.mark.asyncio
async def test_get_me_touches_signed_in_presence() -> None:
    """Identity heartbeat starts or reuses the national-map session."""
    user = _profile_user()
    request = MagicMock()
    db = MagicMock(spec=AsyncSession)
    touch = AsyncMock()
    tokens = AsyncMock(return_value={"cap": 0, "used_today": 0, "remaining_today": 0})

    with (
        patch("routers.auth.session.touch_signed_in_presence", touch),
        patch("routers.auth.session.feature_thinking_coins_enabled", return_value=False),
        patch("routers.auth.session.get_user_role", return_value="teacher"),
        patch("routers.auth.session.current_user_daily_token_payload", tokens),
        patch("routers.auth.session.organization_session_payload", return_value=None),
    ):
        payload = await get_me(request, user, db)

    touch.assert_awaited_once_with(user=user, request=request)
    assert payload["id"] == 3
    assert payload["phone"] == "13800000000"
    assert payload["role"] == "teacher"
    tokens.assert_awaited_once_with(3)


@pytest.mark.asyncio
async def test_get_me_returns_profile_if_presence_raises() -> None:
    """A leak from presence must not become a profile 500."""
    user = _profile_user()
    request = MagicMock()
    db = MagicMock(spec=AsyncSession)
    tokens = AsyncMock(return_value={"cap": 0, "used_today": 0, "remaining_today": 0})

    with (
        patch(
            "routers.auth.session.touch_signed_in_presence",
            AsyncMock(side_effect=RuntimeError("tracker down")),
        ),
        patch("routers.auth.session.feature_thinking_coins_enabled", return_value=False),
        patch("routers.auth.session.get_user_role", return_value="teacher"),
        patch("routers.auth.session.current_user_daily_token_payload", tokens),
        patch("routers.auth.session.organization_session_payload", return_value=None),
    ):
        payload = await get_me(request, user, db)

    assert payload["id"] == 3
    tokens.assert_awaited_once_with(3)
