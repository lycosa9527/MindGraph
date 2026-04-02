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
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["devices"])


class DeviceRegisterRequest(BaseModel):
    watch_id: str
    mac_address: Optional[str] = None


class DeviceAssignRequest(BaseModel):
    student_id: int
    class_id: Optional[int] = None


class DeviceResponse(BaseModel):
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
    request: DeviceRegisterRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Register a new ESP32 watch device"""
    result = await db.execute(select(Device).where(Device.watch_id == request.watch_id))
    existing = result.scalar_one_or_none()
    if existing:
        return existing

    device = Device(
        watch_id=request.watch_id,
        mac_address=request.mac_address,
        status="unassigned",
    )
    db.add(device)
    await db.commit()
    await db.refresh(device)

    logger.info("Registered device: %s", request.watch_id)
    return device


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List all devices (admin/manager only)"""
    if not current_user.is_admin and not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or manager access required",
        )

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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List unassigned devices"""
    if not current_user.is_admin and not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or manager access required",
        )

    result = await db.execute(select(Device).where(Device.status == "unassigned"))
    return result.scalars().all()


@router.get("/{watch_id}", response_model=DeviceResponse)
async def get_device(
    watch_id: str,
    _current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Get device details"""
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
    request: DeviceAssignRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Assign device to student"""
    if not current_user.is_admin and not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or manager access required",
        )

    result = await db.execute(select(Device).where(Device.watch_id == watch_id))
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    student_result = await db.execute(select(User).where(User.id == request.student_id))
    student = student_result.scalar_one_or_none()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    device.student_id = request.student_id
    device.status = "assigned"
    device.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(device)

    logger.info("Assigned device %s to student %d", watch_id, request.student_id)

    data = DeviceResponse.model_validate(device).model_dump()
    data["student_name"] = student.name
    return data


@router.delete("/{watch_id}/assign")
async def unassign_device(
    watch_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Unassign device from student"""
    if not current_user.is_admin and not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or manager access required",
        )

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
    db: AsyncSession = Depends(get_async_db),
):
    """Get device status (public endpoint for watch polling)"""
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
