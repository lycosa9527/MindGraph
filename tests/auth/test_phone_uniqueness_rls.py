"""Phone uniqueness helpers use global system RLS lookups."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.auth.phone_uniqueness import any_user_id_with_phone, other_user_id_with_email


def _compiled_phone_sql(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True})).lower()


@pytest.mark.asyncio
async def test_any_user_id_with_phone_uses_system_rls_session():
    """Test any user id with phone uses system rls session."""
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
    sql = _compiled_phone_sql(mock_db.execute.await_args.args[0])
    assert "13800138000" in sql
    assert "lower(" not in sql


@pytest.mark.asyncio
async def test_xiaozhi_uuid_lookup_uses_one_spelling():
    """Uppercase and braced userIds collide with the lowercase UUID 小致 login stores."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=7)))

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "services.auth.phone_uniqueness.system_rls_session",
        return_value=mock_cm,
    ):
        user_id = await any_user_id_with_phone("{ED2D998E-495E-46CC-AB7D-2D64CCBA4B92}")

    assert user_id == 7
    sql = _compiled_phone_sql(mock_db.execute.await_args.args[0])
    assert "ed2d998e-495e-46cc-ab7d-2d64ccba4b92" in sql
    assert "lower(" in sql


@pytest.mark.asyncio
async def test_other_user_id_with_email_uses_system_rls_session():
    """Test other user id with email uses system rls session."""
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
