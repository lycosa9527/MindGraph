"""Admin CRUD for functions shown in the user avatar dropdown."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from routers.auth.dependencies import require_settings_user_dropdown
from services.features.training.courses.repository import list_courses
from services.features.user_dropdown.store import (
    assign_course,
    create_item,
    delete_item,
    get_item,
    list_items,
    locale_of,
    menu_payload,
    rename_item,
)
from utils.auth.admin_scope import AdminScope
from utils.db.session_open import system_rls_session

router = APIRouter(prefix="/admin/user-dropdown", tags=["admin-user-dropdown"])


class UserDropdownCreate(BaseModel):
    """New menu function."""

    label: str = Field(min_length=1, max_length=40)


class UserDropdownPatch(BaseModel):
    """Rename and/or relink a course. Omit a field to leave it unchanged."""

    label: Optional[str] = Field(default=None, max_length=40)
    course_id: Optional[str] = None


def _http_for_value_error(exc: ValueError) -> HTTPException:
    detail = str(exc) or "user_dropdown_invalid"
    code = status.HTTP_404_NOT_FOUND if detail == "user_dropdown_not_found" else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=detail)


async def _catalog(db: AsyncSession, scope: AdminScope) -> dict:
    items = await list_items(db)
    courses = await list_courses(db)
    return menu_payload(items, courses, locale_of(scope.actor))


@router.get("")
async def list_user_dropdown(
    scope: AdminScope = Depends(require_settings_user_dropdown),
) -> dict:
    """Functions and the courses they can link."""
    async with system_rls_session() as db:
        return await _catalog(db, scope)


@router.post("")
async def create_user_dropdown_item(
    body: UserDropdownCreate,
    scope: AdminScope = Depends(require_settings_user_dropdown),
) -> dict:
    """Add a function to the user menu."""
    async with system_rls_session() as db:
        try:
            await create_item(db, body.label)
            await db.commit()
        except ValueError as exc:
            raise _http_for_value_error(exc) from exc
        return await _catalog(db, scope)


@router.patch("/{item_id}")
async def patch_user_dropdown_item(
    item_id: str,
    body: UserDropdownPatch,
    scope: AdminScope = Depends(require_settings_user_dropdown),
) -> dict:
    """Rename a function or change its linked course."""
    fields = body.model_fields_set
    if "label" not in fields and "course_id" not in fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="user_dropdown_empty_patch")
    async with system_rls_session() as db:
        item = await get_item(db, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_dropdown_not_found")
        try:
            if "label" in fields and body.label is not None:
                await rename_item(item, body.label)
            if "course_id" in fields:
                await assign_course(db, item, body.course_id)
            await db.commit()
        except ValueError as exc:
            raise _http_for_value_error(exc) from exc
        return await _catalog(db, scope)


@router.delete("/{item_id}")
async def delete_user_dropdown_item(
    item_id: str,
    scope: AdminScope = Depends(require_settings_user_dropdown),
) -> dict:
    """Remove a function from the user menu."""
    async with system_rls_session() as db:
        item = await get_item(db, item_id)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_dropdown_not_found")
        await delete_item(db, item)
        await db.commit()
        return await _catalog(db, scope)
