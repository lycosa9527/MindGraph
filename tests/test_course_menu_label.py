"""Course info publishes one name into the user avatar menu."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from services.features.user_dropdown.store import set_course_menu_label


@pytest.mark.asyncio
async def test_blank_label_removes_the_menu_row() -> None:
    """An empty name hides the course from the avatar menu."""
    existing = SimpleNamespace(id="item-1", label="十月更新介绍", course_id="course-1")
    with (
        patch(
            "services.features.user_dropdown.store.get_course",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(id="course-1"),
        ),
        patch(
            "services.features.user_dropdown.store.list_items",
            new_callable=AsyncMock,
            return_value=[existing],
        ),
        patch(
            "services.features.user_dropdown.store.delete_item",
            new_callable=AsyncMock,
        ) as delete,
    ):
        label = await set_course_menu_label(AsyncMock(), "course-1", "  ")
    assert label == ""
    delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_label_links_the_course() -> None:
    """A name creates a menu row that starts this course."""
    created = SimpleNamespace(id="item-1", label="十月更新介绍", course_id=None)
    with (
        patch(
            "services.features.user_dropdown.store.get_course",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(id="course-1"),
        ),
        patch(
            "services.features.user_dropdown.store.list_items",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "services.features.user_dropdown.store.create_item",
            new_callable=AsyncMock,
            return_value=created,
        ) as create,
        patch(
            "services.features.user_dropdown.store.assign_course",
            new_callable=AsyncMock,
        ) as assign,
    ):
        label = await set_course_menu_label(AsyncMock(), "course-1", "  十月更新介绍  ")
    assert label == "十月更新介绍"
    create.assert_awaited_once()
    assign.assert_awaited_once()


@pytest.mark.asyncio
async def test_existing_label_is_renamed() -> None:
    """Saving again updates the name already shown for this course."""
    existing = SimpleNamespace(id="item-1", label="旧名称", course_id="course-1")
    with (
        patch(
            "services.features.user_dropdown.store.get_course",
            new_callable=AsyncMock,
            return_value=SimpleNamespace(id="course-1"),
        ),
        patch(
            "services.features.user_dropdown.store.list_items",
            new_callable=AsyncMock,
            return_value=[existing],
        ),
    ):
        label = await set_course_menu_label(AsyncMock(), "course-1", "十月更新介绍")
    assert label == "十月更新介绍"
    assert existing.label == "十月更新介绍"
