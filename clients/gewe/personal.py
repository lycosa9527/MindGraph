"""Personal/Profile Module.

Handles personal profile, QR code, device records, privacy settings, and avatar operations.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any


class PersonalMixin:
    """Mixin for personal/profile APIs"""

    async def get_profile(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Get personal profile."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/personal/getProfile", json_data=payload)

    async def get_qr_code(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Get own QR code."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/personal/getQrCode", json_data=payload)

    async def get_safety_info(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Get device records."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/personal/getSafetyInfo", json_data=payload)

    async def get_privacy_settings(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Get privacy settings."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/personal/getPrivacySettings", json_data=payload)

    async def modify_personal_info(
        self,
        app_id: str,
        field: str,
        value: str
    ) -> Dict[str, Any]:
        """Modify personal information."""
        payload = {
            "appId": app_id,
            "field": field,
            "value": value
        }
        return await self._request("POST", "/gewe/v2/api/personal/modifyPersonalInfo", json_data=payload)

    async def modify_avatar(
        self,
        app_id: str,
        avatar_url: str
    ) -> Dict[str, Any]:
        """Modify avatar."""
        payload = {
            "appId": app_id,
            "avatarUrl": avatar_url
        }
        return await self._request("POST", "/gewe/v2/api/personal/modifyAvatar", json_data=payload)
