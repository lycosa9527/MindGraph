"""Social Network (Moments) Module.

Handles moments/SNS operations like liking posts.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any


class SNSMixin:
    """Mixin for social network (moments) APIs"""

    async def like_sns(
        self,
        app_id: str,
        sns_id: int,
        oper_type: int,
        wxid: str
    ) -> Dict[str, Any]:
        """Like or unlike a moment. Cannot be used within 1-3 days after login."""
        payload = {
            "appId": app_id,
            "snsId": sns_id,
            "operType": oper_type,
            "wxid": wxid
        }
        return await self._request("POST", "/gewe/v2/api/sns/likeSns", json_data=payload)
