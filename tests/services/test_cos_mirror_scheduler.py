"""Tests for COS mirror scheduler startup and consumer pull."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.infrastructure.sync import cos_mirror_scheduler


@pytest.mark.asyncio
async def test_run_cos_mirror_startup_consumer_pulls_when_newer():
    with patch.object(cos_mirror_scheduler, "cos_sync_enabled", return_value=True):
        with patch.object(cos_mirror_scheduler, "is_cos_consumer", return_value=True):
            with patch.object(
                cos_mirror_scheduler,
                "_run_consumer_cos_pull",
                new=AsyncMock(),
            ) as pull:
                await cos_mirror_scheduler.run_cos_mirror_startup()
    pull.assert_awaited_once_with(force_blocklists=False)


@pytest.mark.asyncio
async def test_run_cos_mirror_startup_skips_when_sync_disabled():
    with (
        patch.object(cos_mirror_scheduler, "cos_sync_enabled", return_value=False),
        patch.object(
            cos_mirror_scheduler,
            "_run_consumer_cos_pull",
            new=AsyncMock(),
        ) as pull,
    ):
        await cos_mirror_scheduler.run_cos_mirror_startup()
    pull.assert_not_awaited()
