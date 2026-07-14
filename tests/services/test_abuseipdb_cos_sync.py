"""Tests for AbuseIPDB COS sync routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.infrastructure.sync import abuseipdb_cos_sync


@pytest.mark.asyncio
async def test_sync_blacklist_for_role_consumer():
    with patch.object(abuseipdb_cos_sync, "is_cos_consumer", return_value=True):
        with patch.object(
            abuseipdb_cos_sync,
            "merge_abuseipdb_blocklist_from_cos",
            new=AsyncMock(return_value={"ok": True, "source": "cos", "count": 3}),
        ) as cos_merge:
            with patch.object(
                abuseipdb_cos_sync,
                "merge_crowdsec_after_abuseipdb_sync",
                new=AsyncMock(return_value={"ok": True, "count": 1, "skipped": False}),
            ):
                with patch.object(
                    abuseipdb_cos_sync,
                    "log_shared_blacklist_redis_size_async",
                    new=AsyncMock(),
                ):
                    result = await abuseipdb_cos_sync.sync_blacklist_for_role(force=True)
    assert result["source"] == "cos"
    assert result["crowdsec"]["count"] == 1
    cos_merge.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_blacklist_for_role_publisher_publishes():
    with patch.object(abuseipdb_cos_sync, "is_cos_consumer", return_value=False):
        with patch.object(abuseipdb_cos_sync, "is_cos_publisher", return_value=True):
            with patch.object(
                abuseipdb_cos_sync,
                "sync_blacklist_to_redis",
                new=AsyncMock(return_value={"ok": True, "count": 10}),
            ):
                with patch.object(
                    abuseipdb_cos_sync,
                    "take_last_abuseipdb_network_sync_payload",
                    return_value=("1.2.3.4\n", 1),
                ):
                    with patch.object(
                        abuseipdb_cos_sync,
                        "publish_abuseipdb_blocklist_to_cos",
                        new=AsyncMock(return_value=True),
                    ) as publish:
                        result = await abuseipdb_cos_sync.sync_blacklist_for_role(force=True)
    assert result["ok"] is True
    assert result["cos_published"] is True
    publish.assert_awaited_once()
