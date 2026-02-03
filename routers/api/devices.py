"""
Device Management API
Handles ESP32 watch registration, assignment, and status
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session

from models.domain.auth import User
from routers.core.dependencies import get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/devices", tags=["devices"])

Base = declarative_base()


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)
    watch_id = Column(String, unique=True, index=True, nullable=False)
    mac_address = Column(String, unique=True, nullable=True)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String, default="unassigned")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen = Column(DateTime, nullable=True)


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

    class Config:
        from_attributes = True


@router.post("/register", response_model=DeviceResponse)
async def register_device(
    request: DeviceRegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new ESP32 watch device"""
    existing = db.query(Device).filter(Device.watch_id == request.watch_id).first()
    if existing:
        return DeviceResponse.from_orm(existing)

    device = Device(
        watch_id=request.watch_id,
        mac_address=request.mac_address,
        status="unassigned",
    )
    db.add(device)
    db.commit()
    db.refresh(device)

    logger.info("Registered device: %s", request.watch_id)
    return DeviceResponse.from_orm(device)


@router.get("", response_model=List[DeviceResponse])
async def list_devices(
    status_filter: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all devices (admin/manager only)"""
    if not current_user.is_admin and not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or manager access required",
        )

    query = db.query(Device)
    if status_filter:
        query = query.filter(Device.status == status_filter)

    devices = query.all()
    result = []
    for device in devices:
        device_dict = DeviceResponse.from_orm(device).dict()
        if device.student_id:
            student = db.query(User).filter(User.id == device.student_id).first()
            if student:
                device_dict["student_name"] = student.username
        result.append(device_dict)

    return result


@router.get("/unassigned", response_model=List[DeviceResponse])
async def list_unassigned_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List unassigned devices"""
    if not current_user.is_admin and not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or manager access required",
        )

    devices = db.query(Device).filter(Device.status == "unassigned").all()
    return [DeviceResponse.from_orm(d) for d in devices]


@router.get("/{watch_id}", response_model=DeviceResponse)
async def get_device(
    watch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get device details"""
    device = db.query(Device).filter(Device.watch_id == watch_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    result = DeviceResponse.from_orm(device).dict()
    if device.student_id:
        student = db.query(User).filter(User.id == device.student_id).first()
        if student:
            result["student_name"] = student.username

    return result


@router.post("/{watch_id}/assign", response_model=DeviceResponse)
async def assign_device(
    watch_id: str,
    request: DeviceAssignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Assign device to student"""
    if not current_user.is_admin and not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or manager access required",
        )

    device = db.query(Device).filter(Device.watch_id == watch_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    student = db.query(User).filter(User.id == request.student_id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student not found",
        )

    device.student_id = request.student_id
    device.status = "assigned"
    device.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(device)

    logger.info("Assigned device %s to student %d", watch_id, request.student_id)

    result = DeviceResponse.from_orm(device).dict()
    result["student_name"] = student.username
    return result


@router.delete("/{watch_id}/assign")
async def unassign_device(
    watch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Unassign device from student"""
    if not current_user.is_admin and not current_user.is_manager:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or manager access required",
        )

    device = db.query(Device).filter(Device.watch_id == watch_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    device.student_id = None
    device.status = "unassigned"
    device.updated_at = datetime.utcnow()
    db.commit()

    logger.info("Unassigned device %s", watch_id)
    return {"success": True}


@router.get("/{watch_id}/status", response_model=DeviceResponse)
async def get_device_status(
    watch_id: str,
    db: Session = Depends(get_db),
):
    """Get device status (public endpoint for watch polling)"""
    device = db.query(Device).filter(Device.watch_id == watch_id).first()
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Device not found",
        )

    result = DeviceResponse.from_orm(device).dict()
    if device.student_id:
        student = db.query(User).filter(User.id == device.student_id).first()
        if student:
            result["student_name"] = student.username

    return result