"""Tests for CrowdSec COS sync."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.infrastructure.sync import crowdsec_cos_sync


def test_compare_crowdsec_sync_state_in_sync():
    local = {"last_merge_unix": 2000.0}
    cos = {"last_merge_unix": 1000.0}
    assert crowdsec_cos_sync.compare_crowdsec_sync_state(local, cos) == "in_sync"


def test_compare_crowdsec_sync_state_missing_on_cos():
    assert crowdsec_cos_sync.compare_crowdsec_sync_state({}, None) == "missing_on_cos"


@pytest.mark.asyncio
async def test_merge_crowdsec_blocklist_for_role_consumer():
    with patch.object(crowdsec_cos_sync, "is_cos_consumer", return_value=True):
        with patch.object(
            crowdsec_cos_sync,
            "merge_crowdsec_blocklist_from_cos",
            new=AsyncMock(return_value={"ok": True, "source": "cos"}),
        ) as cos_merge:
            result = await crowdsec_cos_sync.merge_crowdsec_blocklist_for_role()
    assert result["source"] == "cos"
    cos_merge.assert_awaited_once()
