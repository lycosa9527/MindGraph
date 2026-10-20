"""
Read and write the canvas input mode for the current browser device.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.canvas_input_device import CANVAS_INPUT_MODES, CanvasInputDevice
from services.utils.error_types import DATABASE_ERRORS

_DEVICE_GUC = "app.canvas_device_id"


async def _bind_canvas_device(db: AsyncSession, device_id: str) -> None:
    """Limit this transaction's RLS policy to one device id."""
    await db.execute(
        text("SELECT set_config(:name, :device_id, true)"),
        {"name": _DEVICE_GUC, "device_id": device_id},
    )


async def load_canvas_input_mode(db: AsyncSession, device_id: str) -> str | None:
    """Return the stored mode, or None when this device has no row."""
    await _bind_canvas_device(db, device_id)
    result = await db.execute(select(CanvasInputDevice.input_mode).where(CanvasInputDevice.device_id == device_id))
    mode = result.scalar_one_or_none()
    if mode not in CANVAS_INPUT_MODES:
        return None
    return mode


async def save_canvas_input_mode(
    db: AsyncSession,
    device_id: str,
    input_mode: str,
    user_id: int,
) -> None:
    """Insert or replace this device's mode. ``input_mode`` must already be valid."""
    await _bind_canvas_device(db, device_id)
    now = datetime.now(UTC)
    stmt = insert(CanvasInputDevice).values(
        device_id=device_id,
        input_mode=input_mode,
        updated_by_user_id=user_id,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[CanvasInputDevice.device_id],
        set_={
            "input_mode": input_mode,
            "updated_by_user_id": user_id,
            "updated_at": now,
        },
    )
    try:
        await db.execute(stmt)
        await db.commit()
    except DATABASE_ERRORS:
        await db.rollback()
        raise
