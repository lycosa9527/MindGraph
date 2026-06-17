"""Expert invited-org lookup uses system RLS (not authenticated panel bootstrap)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from utils.auth.admin_scope import load_expert_invited_org_ids


@pytest.mark.asyncio
async def test_load_expert_invited_org_ids_uses_system_rls_session():
    """Test load expert invited org ids uses system rls session."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [10, 20]
    mock_db.execute = AsyncMock(return_value=mock_result)

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_db)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "utils.db.session_open.system_rls_session",
        return_value=mock_cm,
    ):
        org_ids = await load_expert_invited_org_ids(7)

    assert org_ids == frozenset({10, 20})
    mock_db.execute.assert_awaited_once()
