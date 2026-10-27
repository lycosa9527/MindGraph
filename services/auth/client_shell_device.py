"""
Read and write the mobile or desktop shell for the current browser device.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.client_shell_device import CLIENT_SHELLS, ClientShellDevice
from services.utils.error_types import DATABASE_ERRORS

_DEVICE_GUC = "app.client_shell_device_id"


async def _bind_client_shell_device(db: AsyncSession, device_id: str) -> None:
    """Limit this transaction's RLS policy to one device id."""
    await db.execute(
        text("SELECT set_config(:name, :device_id, true)"),
        {"name": _DEVICE_GUC, "device_id": device_id},
    )


async def load_client_shell(db: AsyncSession, device_id: str) -> str | None:
    """Return the stored shell, or None when this device has no row."""
    await _bind_client_shell_device(db, device_id)
    result = await db.execute(select(ClientShellDevice.shell).where(ClientShellDevice.device_id == device_id))
    shell = result.scalar_one_or_none()
    if shell not in CLIENT_SHELLS:
        return None
    return shell


async def save_client_shell(
    db: AsyncSession,
    device_id: str,
    shell: str,
    user_id: int,
) -> None:
    """Insert or replace this device's shell. ``shell`` must already be valid."""
    await _bind_client_shell_device(db, device_id)
    now = datetime.now(UTC)
    stmt = insert(ClientShellDevice).values(
        device_id=device_id,
        shell=shell,
        updated_by_user_id=user_id,
        updated_at=now,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[ClientShellDevice.device_id],
        set_={
            "shell": shell,
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
