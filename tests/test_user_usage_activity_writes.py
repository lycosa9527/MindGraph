"""Write-path tests for user usage activity recording."""

from unittest.mock import AsyncMock, patch

import models.domain.registry  # noqa: F401 — register ORM mappers for tests
import pytest

from services.admin.user_usage_activity import record_user_usage_activity


@pytest.mark.asyncio
async def test_record_skips_invalid_user() -> None:
    with patch("services.admin.user_usage_activity.system_rls_session") as mock_session:
        await record_user_usage_activity(
            user_id=0,
            organization_id=1,
            source="mindgraph",
            action="diagram_save",
            title="x",
        )
        mock_session.assert_not_called()


@pytest.mark.asyncio
async def test_record_persists_row() -> None:
    insert_mock = AsyncMock()
    with patch("services.admin.user_usage_activity.system_rls_session") as mock_session:
        session = AsyncMock()
        session.commit = AsyncMock()
        mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=False)
        with patch(
            "services.admin.user_usage_activity.UserUsageActivityRepository"
        ) as repo_cls:
            repo_cls.return_value.insert = insert_mock
            await record_user_usage_activity(
                user_id=7,
                organization_id=2,
                source="mindmate",
                action="chat_turn",
                prompt_preview="question",
                reply_preview="answer",
                total_tokens=42,
            )
    insert_mock.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_skips_empty_content() -> None:
    with patch("services.admin.user_usage_activity.system_rls_session") as mock_session:
        await record_user_usage_activity(
            user_id=1,
            organization_id=1,
            source="mindgraph",
            action="diagram_save",
        )
        mock_session.assert_not_called()
