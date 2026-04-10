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

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import Organization
from services.auth.geo_cn_mainland_cookie import set_geo_cn_mainland_cookie

_stamp_geo_cn_mainland_cookie = set_geo_cn_mainland_cookie
from services.auth.geoip_country import resolve_country_iso_from_request
from utils.auth import AUTH_MODE, is_https

router = APIRouter()

CLIENT_REGION_COOKIE = "mg_client_region"
CLIENT_REGION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


@router.get("/client-region")
async def get_client_region(request: Request, response: Response):
    """
    Detect whether the client is likely in mainland China (ISO country CN).

    Used by the registration UI to show phone+invitation vs email-only flows.
    Sets a short-lived readable cookie when country is known so repeat visits
    skip GeoIP work. Prefer Cloudflare CF-IPCountry when present.
    """
    code = resolve_country_iso_from_request(request)
    if code is None:
        response.set_cookie(
            key=CLIENT_REGION_COOKIE,
            value="both",
            max_age=CLIENT_REGION_MAX_AGE_SECONDS,
            path="/",
            samesite="lax",
            httponly=False,
            secure=is_https(request),
        )
        return {"mainland_china": None, "region": "unknown"}

    mainland_china = code == "CN"
    cookie_val = "cn" if mainland_china else "intl"
    response.set_cookie(
        key=CLIENT_REGION_COOKIE,
        value=cookie_val,
        max_age=CLIENT_REGION_MAX_AGE_SECONDS,
        path="/",
        samesite="lax",
        httponly=False,
        secure=is_https(request),
    )
    if mainland_china:
        _stamp_geo_cn_mainland_cookie(response, request)
    return {
        "mainland_china": mainland_china,
        "region": "cn" if mainland_china else "intl",
    }


@router.get("/mode")
async def get_auth_mode():
    """
    Get current authentication mode

    Allows frontend to detect and adapt to different auth modes.
    """
    return {"mode": AUTH_MODE}


@router.get("/organizations")
async def list_organizations(db: AsyncSession = Depends(get_async_db)):
    """
    Get list of all organizations (public endpoint for registration)

    Returns basic organization info for registration form dropdown.
    """
    result = await db.execute(select(Organization))
    orgs = result.scalars().all()
    return [{"code": org.code, "name": org.name} for org in orgs]
