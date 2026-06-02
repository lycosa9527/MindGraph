"""Phone uniqueness helpers use global system RLS lookups."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.auth.phone_uniqueness import any_user_id_with_phone, other_user_id_with_email


@pytest.mark.asyncio
async def test_any_user_id_with_phone_uses_system_rls_session():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=42)))

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "services.auth.phone_uniqueness.system_rls_session",
        return_value=mock_cm,
    ):
        user_id = await any_user_id_with_phone("+8613800138000")

    assert user_id == 42


@pytest.mark.asyncio
async def test_other_user_id_with_email_uses_system_rls_session():
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "services.auth.phone_uniqueness.system_rls_session",
        return_value=mock_cm,
    ):
        conflict = await other_user_id_with_email("other@example.com", 1)

    assert conflict is None
