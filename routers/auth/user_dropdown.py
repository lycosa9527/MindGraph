"""Signed-in user menu: functions configured in system settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from models.domain.auth import User
from services.features.user_dropdown.store import (
    course_for_item,
    get_item,
    list_items,
    locale_of,
    public_menu_payload,
)
from utils.auth import get_current_user
from utils.db.session_open import system_rls_session

router = APIRouter(prefix="/user-dropdown", tags=["user-dropdown"])


@router.get("")
async def list_public_user_dropdown(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Menu functions that already link a course."""
    async with system_rls_session() as db:
        items = await list_items(db)
    return public_menu_payload(items, locale_of(current_user))


@router.get("/{item_id}/course")
async def get_user_dropdown_course(
    item_id: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Course walkthrough for one menu function."""
    async with system_rls_session() as db:
        item = await get_item(db, item_id)
        if item is None or not item.course_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_dropdown_not_found")
        try:
            return course_for_item(item, locale_of(current_user))
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_dropdown_course_missing") from exc
