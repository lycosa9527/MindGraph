"""Tests for GeoLite COS sync role routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.infrastructure.sync import geolite_cos_sync


@pytest.mark.asyncio
async def test_sync_geolite_for_role_consumer():
    with patch.object(geolite_cos_sync, "is_cos_consumer", return_value=True):
        with patch.object(
            geolite_cos_sync,
            "install_geolite_from_cos",
            new=AsyncMock(return_value={"ok": True, "source": "cos"}),
        ) as install:
            result = await geolite_cos_sync.sync_geolite_for_role()
    assert result["source"] == "cos"
    install.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_geolite_for_role_publisher():
    with patch.object(geolite_cos_sync, "is_cos_consumer", return_value=False):
        with patch.object(geolite_cos_sync, "is_cos_publisher", return_value=True):
            with patch.object(
                geolite_cos_sync,
                "publish_geolite_to_cos",
                new=AsyncMock(return_value={"ok": True, "source": "local"}),
            ) as publish:
                result = await geolite_cos_sync.sync_geolite_for_role()
    assert result["source"] == "local"
    publish.assert_awaited_once()


@pytest.mark.asyncio
async def test_sync_geolite_for_role_off():
    with patch.object(geolite_cos_sync, "is_cos_consumer", return_value=False):
        with patch.object(geolite_cos_sync, "is_cos_publisher", return_value=False):
            result = await geolite_cos_sync.sync_geolite_for_role()
    assert result["error"] == "role_off"
    assert result["skipped"] is True
