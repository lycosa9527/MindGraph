"""Login /me session user JSON includes thinking-coin eligibility."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from routers.auth.session_user_payload import (
    build_session_user_payload,
    thinking_coins_session_summary,
)


def _session_user() -> User:
    """Minimal user for session payload tests."""
    user = User(id=6, password_hash="x")
    user.phone = "13800000000"
    user.email = None
    user.name = "Tester"
    user.avatar = None
    user.role = "teacher"
    user.organization_id = 5
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
async def test_thinking_coins_summary_off_when_flag_disabled() -> None:
    """Feature off must not bootstrap a wallet."""
    user = _session_user()
    org = MagicMock()
    db = MagicMock(spec=AsyncSession)
    bootstrap = AsyncMock()
    with (
        patch(
            "routers.auth.session_user_payload.feature_thinking_coins_enabled",
            return_value=False,
        ),
        patch(
            "routers.auth.session_user_payload.ensure_wallet_bootstrap",
            bootstrap,
        ),
    ):
        summary = await thinking_coins_session_summary(db, user, org)

    assert summary == {"balance": 0, "eligible": False}
    bootstrap.assert_not_awaited()


@pytest.mark.asyncio
async def test_thinking_coins_summary_bootstraps_when_eligible() -> None:
    """Eligible login must create the wallet so the sidebar can show coins."""
    user = _session_user()
    org = MagicMock()
    db = MagicMock(spec=AsyncSession)
    bootstrap = AsyncMock()
    wallet = AsyncMock(return_value={"balance": 42, "eligible": True})
    with (
        patch(
            "routers.auth.session_user_payload.feature_thinking_coins_enabled",
            return_value=True,
        ),
        patch(
            "routers.auth.session_user_payload.user_eligible_for_thinking_coins",
            return_value=True,
        ),
        patch(
            "routers.auth.session_user_payload.ensure_wallet_bootstrap",
            bootstrap,
        ),
        patch(
            "routers.auth.session_user_payload.build_wallet_payload",
            wallet,
        ),
    ):
        summary = await thinking_coins_session_summary(db, user, org)

    assert summary == {"balance": 42, "eligible": True}
    bootstrap.assert_awaited_once_with(db, user, org)
    wallet.assert_awaited_once_with(db, user, org)


@pytest.mark.asyncio
async def test_session_user_payload_includes_thinking_coins() -> None:
    """Login JSON must carry thinking_coins so the SPA does not wait for /me."""
    user = _session_user()
    org = MagicMock()
    org.id = 5
    db = MagicMock(spec=AsyncSession)
    tokens = AsyncMock(return_value={"cap": 0, "used_today": 0, "remaining_today": 0})
    with (
        patch(
            "routers.auth.session_user_payload.thinking_coins_session_summary",
            AsyncMock(return_value={"balance": 12, "eligible": True}),
        ),
        patch(
            "routers.auth.session_user_payload.current_user_daily_token_payload",
            tokens,
        ),
        patch(
            "routers.auth.session_user_payload.get_user_role",
            return_value="teacher",
        ),
        patch(
            "routers.auth.session_user_payload.organization_session_payload",
            return_value={"id": 5, "name": "思源智教"},
        ),
    ):
        payload = await build_session_user_payload(db, user, org)

    assert payload["id"] == 6
    assert payload["thinking_coins"] == {"balance": 12, "eligible": True}
    assert payload["daily_tokens"] == {"cap": 0, "used_today": 0, "remaining_today": 0}
    tokens.assert_awaited_once_with(6)
