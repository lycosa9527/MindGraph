"""Tag Management Module.

Handles friend tag operations: add, delete, list, and modify friend tags.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, List, Optional, Protocol


class _GeweClientProtocol(Protocol):
    """Protocol defining the interface expected by TagMixin"""
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Gewe API"""
        raise NotImplementedError


class TagMixin:
    """Mixin for tag management APIs"""

    async def add_tag(
        self: "_GeweClientProtocol",
        app_id: str,
        label_name: str
    ) -> Dict[str, Any]:
        """
        Add a new tag.
        
        Note: If tag name already exists, returns existing tag info.
        """
        payload = {
            "appId": app_id,
            "labelName": label_name
        }
        return await self._request("POST", "/gewe/v2/api/label/add", json_data=payload)

    async def delete_tag(
        self: "_GeweClientProtocol",
        app_id: str,
        label_ids: str
    ) -> Dict[str, Any]:
        """
        Delete tag(s).
        
        label_ids: Comma-separated label IDs (e.g., "1,2,3")
        """
        payload = {
            "appId": app_id,
            "labelIds": label_ids
        }
        return await self._request("POST", "/gewe/v2/api/label/delete", json_data=payload)

    async def get_tag_list(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """Get tag list."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/label/list", json_data=payload)

    async def modify_friend_tags(
        self: "_GeweClientProtocol",
        app_id: str,
        wx_ids: List[str],
        label_ids: str
    ) -> Dict[str, Any]:
        """
        Modify friend tags.
        
        Note: This requires full tag list (additive). To add tag 3 to friend with tags 1,2,
        pass labelIds="1,2,3". To remove tag 1, pass labelIds="2,3".
        
        label_ids: Comma-separated label IDs (e.g., "1,2,3")
        wx_ids: List of friend wxids
        """
        payload = {
            "appId": app_id,
            "wxIds": wx_ids,
            "labelIds": label_ids
        }
        return await self._request("POST", "/gewe/v2/api/label/modifyMemberList", json_data=payload)
