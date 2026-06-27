"""Tests for thinking coin event hub."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from services.auth.thinking_coin.event_hub import (
    empty_mutation,
    merge_mutation_footers,
    mutation_to_footer,
    track_client_event,
)


@pytest.mark.asyncio
async def test_empty_mutation_footer_is_ineligible() -> None:
    """Ineligible users get minimal footer."""
    footer = mutation_to_footer(empty_mutation())
    assert footer == {"eligible": False, "balance": 0}


def test_merge_mutation_footers_prefers_last_eligible() -> None:
    """Earn footer after spend footer wins (includes updated balance)."""
    spend = {"eligible": True, "balance": 90, "debited": 10, "credited": 0}
    earn = {"eligible": True, "balance": 100, "debited": 10, "credited": 10}
    merged = merge_mutation_footers(spend, earn)
    assert merged["balance"] == 100
    assert merged["credited"] == 10


def test_merge_mutation_footers_skips_ineligible() -> None:
    """Empty merge when no eligible footer."""
    assert not merge_mutation_footers({}, {"eligible": False})


@pytest.mark.asyncio
async def test_track_client_event_no_credit_when_ineligible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-eligible users return empty mutation without DB writes."""
    user = MagicMock()
    org = MagicMock()
    db = AsyncMock()
    monkeypatch.setattr(
        "services.auth.thinking_coin.event_hub.feature_thinking_coins_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.auth.thinking_coin.event_hub.user_eligible_for_thinking_coins",
        lambda _user, _org: False,
    )
    mutation = await track_client_event(db, user, org, "diagram_export")
    assert mutation.eligible is False


@pytest.mark.asyncio
async def test_mutation_footer_includes_completed_slugs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Footer exposes completed slugs for UI sync."""
    user = MagicMock()
    user.id = 7
    org = MagicMock()
    db = AsyncMock()
    monkeypatch.setattr(
        "services.auth.thinking_coin.event_hub.feature_thinking_coins_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "services.auth.thinking_coin.event_hub.user_eligible_for_thinking_coins",
        lambda _user, _org: True,
    )
    monkeypatch.setattr(
        "services.auth.thinking_coin.event_hub.try_client_event_earn",
        AsyncMock(return_value=(10, "daily_diagram_export")),
    )
    monkeypatch.setattr(
        "services.auth.thinking_coin.event_hub.get_balance",
        AsyncMock(return_value=120),
    )
    monkeypatch.setattr(
        "services.auth.thinking_coin.event_hub.safe_commit",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "services.auth.thinking_coin.event_hub._completed_slugs_for_user",
        AsyncMock(return_value=("daily_diagram_export",)),
    )
    mutation = await track_client_event(db, user, org, "diagram_export")
    footer = mutation_to_footer(mutation)
    assert footer["balance"] == 120
    assert footer["credited"] == 10
    assert "daily_diagram_export" in footer["completed_slugs_today"]
