"""Tests for LLMService daily token cap pre-flight."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.infrastructure.http.error_handler import UserDailyTokenCapExceededError
from services.llm import LLMService


@pytest.mark.asyncio
async def test_chat_raises_when_daily_cap_exceeded() -> None:
    """chat() propagates UserDailyTokenCapExceededError from budget check."""
    service = LLMService()
    cap_error = UserDailyTokenCapExceededError(cap=1_000_000, used=1_000_000, user_message="limit")

    with patch(
        "services.llm.assert_llm_usage_budget",
        new=AsyncMock(side_effect=cap_error),
    ):
        with pytest.raises(UserDailyTokenCapExceededError):
            await service.chat(prompt="hello", model="qwen", user_id=99, max_tokens=100)


@pytest.mark.asyncio
async def test_chat_invokes_budget_check_with_user_id_none() -> None:
    """chat() always invokes budget check; None user_id is a no-op inside assert."""
    cap_error = UserDailyTokenCapExceededError(cap=1, used=1)
    mock_assert = AsyncMock(side_effect=cap_error)

    with patch("services.llm.assert_llm_usage_budget", new=mock_assert):
        service = LLMService()
        with pytest.raises(UserDailyTokenCapExceededError):
            await service.chat(prompt="hello", model="qwen", user_id=None)

    mock_assert.assert_awaited_once_with(
        None,
        None,
        "diagram_generation",
        estimated_tokens=2000,
    )
