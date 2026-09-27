"""User dropdown admin and public routes."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from models.domain.auth import User
from models.domain.user_dropdown import UserDropdownItem
from routers.auth.admin.user_dropdown import UserDropdownCreate, create_user_dropdown_item
from routers.auth.user_dropdown import get_user_dropdown_course, list_public_user_dropdown
from services.features.user_dropdown.store import clean_label, public_menu_payload, serialize_menu_item
from utils.auth.admin_scope import AdminScope


def _user() -> User:
    return cast(User, SimpleNamespace(id=1, role="superadmin", preferred_language="zh"))


def _scope() -> AdminScope:
    return AdminScope(
        actor=_user(),
        role="superadmin",
        capabilities=frozenset({"tab.settings.user_dropdown"}),
        org_ids=None,
        effective_org_id=None,
        read_only=False,
    )


def _rls(db: AsyncMock) -> AsyncMock:
    context = AsyncMock()
    context.__aenter__ = AsyncMock(return_value=db)
    context.__aexit__ = AsyncMock(return_value=None)
    return context


def test_clean_label_strips_and_rejects_blank() -> None:
    """Labels are trimmed; whitespace-only names are rejected."""
    assert clean_label("  新手引导  ") == "新手引导"
    with pytest.raises(ValueError, match="user_dropdown_label_required"):
        clean_label("   ")


def test_public_menu_hides_unlinked_functions() -> None:
    """The avatar menu only lists functions that already point at a course."""
    linked = cast(
        UserDropdownItem,
        SimpleNamespace(id="a", label="引导", course_id="course-1", course=None, sort_order=1),
    )
    loose = cast(
        UserDropdownItem,
        SimpleNamespace(id="b", label="空", course_id=None, course=None, sort_order=2),
    )
    body = public_menu_payload([linked, loose], "zh")
    assert [row["id"] for row in body["items"]] == ["a"]
    assert serialize_menu_item(linked, "zh")["label"] == "引导"


@pytest.mark.asyncio
async def test_create_returns_catalog() -> None:
    """Adding a function commits and returns the admin catalog."""
    db = AsyncMock()
    catalog = {"items": [{"id": "1", "label": "引导"}], "courses": []}
    with (
        patch("routers.auth.admin.user_dropdown.system_rls_session", return_value=_rls(db)),
        patch("routers.auth.admin.user_dropdown.create_item", new_callable=AsyncMock) as create,
        patch("routers.auth.admin.user_dropdown.list_items", new_callable=AsyncMock, return_value=[]),
        patch("routers.auth.admin.user_dropdown.list_courses", new_callable=AsyncMock, return_value=[]),
        patch("routers.auth.admin.user_dropdown.menu_payload", return_value=catalog),
    ):
        body = await create_user_dropdown_item(UserDropdownCreate(label="引导"), _scope())
    create.assert_awaited()
    db.commit.assert_awaited()
    assert body == catalog


@pytest.mark.asyncio
async def test_public_course_requires_a_link() -> None:
    """A menu row with no course cannot be opened as a walkthrough."""
    db = AsyncMock()
    item = SimpleNamespace(id="a", course_id=None, course=None)
    with (
        patch("routers.auth.user_dropdown.system_rls_session", return_value=_rls(db)),
        patch("routers.auth.user_dropdown.get_item", new_callable=AsyncMock, return_value=item),
    ):
        with pytest.raises(HTTPException) as exc:
            await get_user_dropdown_course("a", _user())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_public_list_uses_signed_in_locale() -> None:
    """The menu payload is built for the signed-in user."""
    db = AsyncMock()
    with (
        patch("routers.auth.user_dropdown.system_rls_session", return_value=_rls(db)),
        patch("routers.auth.user_dropdown.list_items", new_callable=AsyncMock, return_value=[]),
        patch("routers.auth.user_dropdown.public_menu_payload", return_value={"items": []}) as payload,
    ):
        body = await list_public_user_dropdown(_user())
    payload.assert_called_once()
    assert body == {"items": []}
