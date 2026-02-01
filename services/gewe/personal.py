"""Personal Service Module.

Handles personal/profile-related service operations.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any

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
