"""Collection (Favorites) Module.

Handles WeChat favorites/collection operations: sync, get content, and delete.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, Protocol


class _GeweClientProtocol(Protocol):
    """Protocol defining the interface expected by CollectionMixin"""
    token: str

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Gewe API"""
        raise NotImplementedError


class CollectionMixin:
    """Mixin for collection/favorites APIs"""

    async def sync_collection(
        self: "_GeweClientProtocol",
        app_id: str,
        sync_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sync collection/favorites.
        
        Note: Response includes deleted collection records (flag=1 indicates deleted).
        Use syncKey for pagination - pass empty string first time, then use returned syncKey.
        """
        payload = {"appId": app_id}
        if sync_key:
            payload["syncKey"] = sync_key
        else:
            payload["syncKey"] = ""
        return await self._request("POST", "/gewe/v2/api/favor/sync", json_data=payload)

    async def get_collection_content(
        self: "_GeweClientProtocol",
        app_id: str,
        fav_id: int
    ) -> Dict[str, Any]:
        """Get collection content by favId."""
        payload = {
            "appId": app_id,
            "favId": fav_id
        }
        return await self._request("POST", "/gewe/v2/api/favor/getContent", json_data=payload)

    async def delete_collection(
        self: "_GeweClientProtocol",
        app_id: str,
        fav_id: int
    ) -> Dict[str, Any]:
        """Delete collection item."""
        payload = {
            "appId": app_id,
            "favId": fav_id
        }
        return await self._request("POST", "/gewe/v2/api/favor/delete", json_data=payload)
