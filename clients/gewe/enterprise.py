"""Enterprise WeChat Module.

Handles enterprise WeChat contact operations.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, Protocol


class _GeweClientProtocol(Protocol):
    """Protocol defining the interface expected by EnterpriseMixin"""
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Gewe API"""
        raise NotImplementedError


class EnterpriseMixin:
    """Mixin for enterprise WeChat APIs"""

    async def search_enterprise_wechat(
        self: "_GeweClientProtocol",
        app_id: str,
        keyword: str
    ) -> Dict[str, Any]:
        """Search enterprise WeChat contacts."""
        payload = {
            "appId": app_id,
            "keyword": keyword
        }
        return await self._request("POST", "/gewe/v2/api/enterprise/searchEnterpriseWechat", json_data=payload)

    async def add_enterprise_wechat_friend(
        self: "_GeweClientProtocol",
        app_id: str,
        wxid: str,
        content: str
    ) -> Dict[str, Any]:
        """Add enterprise WeChat friend."""
        payload = {
            "appId": app_id,
            "wxid": wxid,
            "content": content
        }
        return await self._request("POST", "/gewe/v2/api/enterprise/addEnterpriseWechatFriend", json_data=payload)

    async def sync_enterprise_wechat_friends(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """Sync enterprise WeChat friends."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/enterprise/syncEnterpriseWechatFriends", json_data=payload)

    async def get_enterprise_wechat_friend_detail(
        self: "_GeweClientProtocol",
        app_id: str,
        wxid: str
    ) -> Dict[str, Any]:
        """Get enterprise WeChat friend detail."""
        payload = {
            "appId": app_id,
            "wxid": wxid
        }
        return await self._request("POST", "/gewe/v2/api/enterprise/getEnterpriseWechatFriendDetail", json_data=payload)
