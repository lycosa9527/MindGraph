"""Built-in and saved diagram specs for the quick-access inspiration prompts."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from services.redis.cache.redis_user_cache import user_cache
from services.utils.error_types import DATABASE_ERRORS, REDIS_ERRORS
from services.utils.quick_access_prompts import QUICK_ACCESS_PROMPT_KEYS
from services.utils.quick_access_specs import (
    QUICK_ACCESS_SPEC_DIAGRAM_TYPES,
    QUICK_ACCESS_SPEC_TEXT_MAX,
    clean_quick_access_saved_specs,
    default_quick_access_specs,
)
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class QuickAccessSpecSave(BaseModel):
    """One inspiration box: the prompt text and the diagram it produced."""

    model_config = ConfigDict(populate_by_name=True)

    key: str
    text: str = Field(max_length=QUICK_ACCESS_SPEC_TEXT_MAX)
    diagram_type: str = Field(alias="diagramType")
    spec: dict[str, Any]

    def cleaned(self) -> dict[str, Any] | None:
        """Return the stored entry, or None when the payload is not a known prompt."""
        if self.key not in QUICK_ACCESS_PROMPT_KEYS:
            return None
        if self.diagram_type not in QUICK_ACCESS_SPEC_DIAGRAM_TYPES or not self.spec:
            return None
        text = str(self.text).strip()
        if not text:
            return None
        entry = {"text": text, "diagramType": self.diagram_type, "spec": self.spec}
        saved = clean_quick_access_saved_specs({self.key: entry})
        return saved.get(self.key)


@router.get("/quick-access-specs")
async def read_quick_access_specs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Built-in demo diagrams plus this account's edited-prompt diagrams."""
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    saved = clean_quick_access_saved_specs(getattr(user, "quick_access_prompt_specs", None))
    return {"defaults": default_quick_access_specs(), "saved": saved}


@router.put("/quick-access-specs")
async def save_quick_access_spec(
    body: QuickAccessSpecSave,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Store the diagram produced for one edited inspiration prompt."""
    entry = body.cleaned()
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="quick-access spec must name a known prompt and a diagram",
        )
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    current = clean_quick_access_saved_specs(getattr(user, "quick_access_prompt_specs", None))
    current[body.key] = entry
    user.quick_access_prompt_specs = current
    try:
        await db.commit()
        await db.refresh(user)
    except DATABASE_ERRORS as exc:
        logger.error(
            "Failed to save quick-access spec for user %s: %s",
            user.id,
            exc,
            exc_info=True,
        )
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save preferences",
        ) from exc
    try:
        await user_cache.invalidate(user.id, user.phone, getattr(user, "email", None))
        await user_cache.cache_user(user)
    except REDIS_ERRORS as exc:
        logger.warning(
            "Saved quick-access spec for user %s but the session cache did not refresh: %s",
            user.id,
            exc,
        )
    saved = clean_quick_access_saved_specs(getattr(user, "quick_access_prompt_specs", None))
    return {"saved": saved}
