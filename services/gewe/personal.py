"""Personal Service Module.

Handles personal/profile-related service operations.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional

from services.gewe.protocols import GeweServiceBase


class PersonalServiceMixin(GeweServiceBase):
    """Mixin for personal/profile-related service methods"""

    async def get_profile(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Get personal profile."""
        client = self._get_gewe_client()
        return await client.get_profile(app_id=app_id)

    async def get_qr_code(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Get own QR code."""
        client = self._get_gewe_client()
        return await client.get_qr_code(app_id=app_id)

    async def get_safety_info(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Get device records."""
        client = self._get_gewe_client()
        return await client.get_safety_info(app_id=app_id)

    async def get_privacy_settings(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Get privacy settings."""
        client = self._get_gewe_client()
        return await client.get_privacy_settings(app_id=app_id)

    async def set_privacy_settings(
        self,
        app_id: str,
        option: int,
        open_flag: bool
    ) -> Dict[str, Any]:
        """Set privacy settings."""
        client = self._get_gewe_client()
        return await client.set_privacy_settings(
            app_id=app_id,
            option=option,
            open_flag=open_flag
        )

    async def update_profile(
        self,
        app_id: str,
        nick_name: Optional[str] = None,
        country: Optional[str] = None,
        province: Optional[str] = None,
        city: Optional[str] = None,
        signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update personal profile."""
        client = self._get_gewe_client()
        return await client.update_profile(
            app_id=app_id,
            nick_name=nick_name,
            country=country,
            province=province,
            city=city,
            signature=signature
        )

    async def update_head_img(
        self,
        app_id: str,
        avatar_url: str
    ) -> Dict[str, Any]:
        """Update avatar/head image."""
        client = self._get_gewe_client()
        return await client.update_head_img(
            app_id=app_id,
            avatar_url=avatar_url
        )
