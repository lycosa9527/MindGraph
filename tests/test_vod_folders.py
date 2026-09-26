"""Online video library folders: rename stays unique per school."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from models.domain.vod import VodFolder
from services.features.vod.catalog import VodCatalogError
from services.features.vod.folders import rename_folder


def _folder(name: str = "Intro") -> VodFolder:
    now = datetime.now(UTC)
    return VodFolder(
        id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        organization_id=5,
        name=name,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_rename_folder_updates_name() -> None:
    """Whitespace collapses and the new name is stored."""
    row = _folder()
    db = AsyncMock()
    db.scalar = AsyncMock(return_value=None)
    updated = await rename_folder(db, row, "  lesson   clips ")
    assert updated.name == "lesson clips"
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_rename_folder_skips_unchanged_name() -> None:
    """The same name does not hit the uniqueness check."""
    row = _folder("Intro")
    db = AsyncMock()
    updated = await rename_folder(db, row, "  Intro  ")
    assert updated.name == "Intro"
    db.scalar.assert_not_called()
    db.flush.assert_not_called()


@pytest.mark.asyncio
async def test_rename_folder_rejects_duplicate() -> None:
    """Another folder in the same school keeps its name."""
    row = _folder("Intro")
    db = AsyncMock()
    db.scalar = AsyncMock(return_value="other-id")
    with pytest.raises(VodCatalogError) as caught:
        await rename_folder(db, row, "Taken")
    assert caught.value.code == "folder_exists"
    assert caught.value.http_status == 409
    assert row.name == "Intro"
