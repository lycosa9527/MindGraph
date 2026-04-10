"""
Admin GeoLite2 Country MMDB status (operators).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from pydantic import BaseModel

from fastapi import APIRouter, Depends

from services.auth.geoip_country import (
    GEOIP_GEOLITE_DOWNLOAD_URL,
    get_geolite_country_mmdb_path,
    is_geolite_country_mmdb_file_present,
)

from ..dependencies import require_admin

router = APIRouter()


class GeoliteStatusResponse(BaseModel):
    """GeoLite2 Country file presence for admin UI."""

    geolite_country_mmdb_present: bool
    expected_path: str
    download_url: str


@router.get(
    "/admin/system/geolite",
    response_model=GeoliteStatusResponse,
    dependencies=[Depends(require_admin)],
)
async def get_geolite_status() -> GeoliteStatusResponse:
    """Return whether GeoLite2-Country.mmdb exists and where it is expected."""
    path = get_geolite_country_mmdb_path()
    return GeoliteStatusResponse(
        geolite_country_mmdb_present=is_geolite_country_mmdb_file_present(),
        expected_path=str(path),
        download_url=GEOIP_GEOLITE_DOWNLOAD_URL,
    )
