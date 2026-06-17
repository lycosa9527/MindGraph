"""
Device Management API
Handles ESP32 watch registration, assignment, and status
"""

import logging
from datetime import UTC, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config.database import get_async_db
from models.domain.auth import User
from models.domain.device import Device
from routers.auth.dependencies import require_admin
from utils.auth import get_current_user
from utils.db.rls_request import bind_system_bootstrap_rls_dependency

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceRegisterRequest(BaseModel):
    """DeviceRegisterRequest helper."""
    watch_id: str
    mac_address: Optional[str] = None


class DeviceAssignRequest(BaseModel):
    """DeviceAssignRequest helper."""
    student_id: int
    class_id: Optional[int] = None


class DeviceResponse(BaseModel):
    """DeviceResponse helper."""
    id: int
    watch_id: str
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    status: str
    last_seen: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/register", response_model=DeviceResponse)
async def register_device(
    body: DeviceRegisterRequest,
    _system_rls: None = Depends(bind_system_bootstrap_rls_dependency),
    db: AsyncSession = Depends(get_async_db),
):
    """Register a new ESP32 watch device (system RLS — unauthenticated)."""
    result = await db.execute(select(Device).where(Device.watch_id == body.watch_id))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    device = Device(
        watch_id=body.watch_id,
        mac_address=body.mac_address,
        status="unassigned",
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)

    logger.info("Registered device: %s", body.watch_id)
    return device


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    status_filter: Optional[str] = None,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """List all devices (superadmin only — Smart Response admin panel)."""
    stmt = select(Device).options(selectinload(Device.student))
    if status_filter:
        stmt = stmt.where(Device.status == status_filter)

    result = await db.execute(stmt)
    devices = result.scalars().all()

    response = []
    for device in devices:
        data = DeviceResponse.model_validate(device).model_dump()
        if device.student:
            data["student_name"] = device.student.name
        response.append(data)

    return response


@router.get("/unassigned", response_model=List[DeviceResponse])
async def list_unassigned_devices(
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """List unassigned devices (superadmin only)."""
    result = await db.execute(select(Device).where(Device.status == "unassigned"))
    return result.scalars().all()


@router.get("/{watch_id}", response_model=DeviceResponse)
async def get_device(
    watch_id: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Get device details (authenticated; visible per org/student RLS)."""
    result = await db.execute(select(Device).options(selectinload(Device.student)).where(Device.watch_id == watch_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    data = DeviceResponse.model_validate(device).model_dump()
    if device.student:
        data["student_name"] = device.student.name
    return data


@router.post("/{watch_id}/assign", response_model=DeviceResponse)
async def assign_device(
    watch_id: str,
    body: DeviceAssignRequest,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Assign device to student (superadmin only)."""
    result = await db.execute(select(Device).where(Device.watch_id == watch_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    student_result = await db.execute(select(User).where(User.id == body.student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    device.student_id = body.student_id
    device.status = "assigned"
    device.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(device)

    logger.info("Assigned device %s to student %d", watch_id, body.student_id)

    data = DeviceResponse.model_validate(device).model_dump()
    data["student_name"] = student.name
    return data


@router.delete("/{watch_id}/assign")
async def unassign_device(
    watch_id: str,
    _current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Unassign device from student (superadmin only)."""
    result = await db.execute(select(Device).where(Device.watch_id == watch_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    device.student_id = None
    device.status = "unassigned"
    device.updated_at = datetime.now(UTC)
    await db.commit()

    logger.info("Unassigned device %s", watch_id)
    return {"success": True}


@router.get("/{watch_id}/status", response_model=DeviceResponse)
async def get_device_status(
    watch_id: str,
    _system_rls: None = Depends(bind_system_bootstrap_rls_dependency),
    db: AsyncSession = Depends(get_async_db),
):
    """Get device status (public endpoint for watch polling; system RLS)."""
    result = await db.execute(select(Device).options(selectinload(Device.student)).where(Device.watch_id == watch_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    data = DeviceResponse.model_validate(device).model_dump()
    if device.student:
        data["student_name"] = device.student.name
    return data
