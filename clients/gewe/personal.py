"""Personal/Profile Module.

Handles personal profile, QR code, device records, privacy settings, and avatar operations.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, Protocol


class _GeweClientProtocol(Protocol):
    """Protocol defining the interface expected by PersonalMixin"""
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Gewe API"""
        raise NotImplementedError


class PersonalMixin:
    """Mixin for personal/profile APIs"""

    async def get_profile(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """Get personal profile."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/personal/getProfile", json_data=payload)

    async def get_qr_code(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """Get own QR code."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/personal/getQrCode", json_data=payload)

    async def get_safety_info(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """Get device records."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/personal/getSafetyInfo", json_data=payload)

    async def get_privacy_settings(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """Get privacy settings."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/personal/getPrivacySettings", json_data=payload)

    async def set_privacy_settings(
        self: "_GeweClientProtocol",
        app_id: str,
        option: int,
        open_flag: bool
    ) -> Dict[str, Any]:
        """
        Set privacy settings.
        
        Option values:
        - 4: Require verification when adding me as friend
        - 7: Recommend contacts as friends
        - 8: Add me via phone number
        - 25: Add me via WeChat ID
        - 38: Add me via group chat
        - 39: Add me via QR code
        - 40: Add me via name card
        """
        payload = {
            "appId": app_id,
            "option": option,
            "open": open_flag
        }
        return await self._request("POST", "/gewe/v2/api/personal/privacySettings", json_data=payload)

    async def modify_personal_info(
        self: "_GeweClientProtocol",
        app_id: str,
        field: str,
        value: str
    ) -> Dict[str, Any]:
        """Modify personal information (deprecated, use update_profile instead)."""
        payload = {
            "appId": app_id,
            "field": field,
            "value": value
        }
        return await self._request("POST", "/gewe/v2/api/personal/modifyPersonalInfo", json_data=payload)

    async def update_profile(
        self: "_GeweClientProtocol",
        app_id: str,
        nick_name: Optional[str] = None,
        country: Optional[str] = None,
        province: Optional[str] = None,
        city: Optional[str] = None,
        signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update personal profile.
        
        Note: Each field must be set separately.
        For example, to update nickname only, pass appId and nickName.
        To update region, pass appId, country, province, city.
        """
        payload = {"appId": app_id}
        if nick_name is not None:
            payload["nickName"] = nick_name
        if country is not None:
            payload["country"] = country
        if province is not None:
            payload["province"] = province
        if city is not None:
            payload["city"] = city
        if signature is not None:
            payload["signature"] = signature
        return await self._request("POST", "/gewe/v2/api/personal/updateProfile", json_data=payload)

    async def modify_avatar(
        self: "_GeweClientProtocol",
        app_id: str,
        avatar_url: str
    ) -> Dict[str, Any]:
        """Modify avatar (deprecated, use update_head_img instead)."""
        payload = {
            "appId": app_id,
            "avatarUrl": avatar_url
        }
        return await self._request("POST", "/gewe/v2/api/personal/modifyAvatar", json_data=payload)

    async def update_head_img(
        self: "_GeweClientProtocol",
        app_id: str,
        avatar_url: str
    ) -> Dict[str, Any]:
        """
        Update avatar/head image.
        
        Note: After updating avatar, close WeChat process on phone and restart
        to see the latest avatar.
        """
        payload = {
            "appId": app_id,
            "avatarUrl": avatar_url
        }
        return await self._request("POST", "/gewe/v2/api/personal/updateHeadImg", json_data=payload)
