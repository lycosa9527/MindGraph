"""
Public Authentication Endpoints
================================

Public endpoints (no authentication required):
- /mode - Get authentication mode
- /organizations - List organizations (for registration form)

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import Organization
from utils.auth import AUTH_MODE

router = APIRouter()


@router.get("/mode")
async def get_auth_mode():
    """
    Get current authentication mode

    Allows frontend to detect and adapt to different auth modes.
    """
    return {"mode": AUTH_MODE}


@router.get("/organizations")
async def list_organizations(db: Session = Depends(get_db)):
    """
    Get list of all organizations (public endpoint for registration)

    Returns basic organization info for registration form dropdown.
    """
    orgs = db.query(Organization).all()
    return [
        {
            "code": org.code,
            "name": org.name
        }
        for org in orgs
    ]

