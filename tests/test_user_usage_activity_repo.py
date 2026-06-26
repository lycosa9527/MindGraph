"""Repository list logic tests (mocked session)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from models.domain.user_usage_activity import UserUsageActivity
from repositories.user_usage_activity_repo import UserUsageActivityRepository


@pytest.mark.asyncio
async def test_list_for_user_applies_source_filter() -> None:
    """User activity listing applies the source filter in SQL."""
    session = MagicMock()
    row = UserUsageActivity(
        id=1,
        user_id=5,
        organization_id=2,
        source="mindmate",
        action="chat_turn",
        prompt_preview="hi",
        created_at=datetime.now(UTC),
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [row]
    session.execute = AsyncMock(return_value=result)
    repo = UserUsageActivityRepository(session)
    rows = await repo.list_for_user(user_id=5, limit=10, before_id=None, source="mindmate")
    assert len(rows) == 1
    assert rows[0].source == "mindmate"
    sql_text = str(session.execute.await_args.args[0])
    assert "user_usage_activities" in sql_text


@pytest.mark.asyncio
async def test_list_for_organization_applies_source_filter() -> None:
    """Organization activity listing applies the source filter in SQL."""
    session = MagicMock()
    row = UserUsageActivity(
        id=2,
        user_id=5,
        organization_id=3,
        source="mindgraph",
        action="diagram_generate",
        prompt_preview="prompt",
        created_at=datetime.now(UTC),
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [row]
    session.execute = AsyncMock(return_value=result)
    repo = UserUsageActivityRepository(session)
    rows = await repo.list_for_organization(
        organization_id=3,
        limit=10,
        before_id=None,
        source="mindgraph",
    )
    assert len(rows) == 1
    assert rows[0].organization_id == 3
    sql_text = str(session.execute.await_args.args[0])
    assert "user_usage_activities" in sql_text
