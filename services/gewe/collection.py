"""Collection Service Module.

Handles collection/favorites-related service operations.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional

from services.gewe.protocols import GeweServiceBase


class CollectionServiceMixin(GeweServiceBase):
    """Mixin for collection/favorites-related service methods"""

    async def sync_collection(
        self,
        app_id: str,
        sync_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Sync collection/favorites."""
        client = self._get_gewe_client()
        return await client.sync_collection(app_id=app_id, sync_key=sync_key)

    async def get_collection_content(
        self,
        app_id: str,
        fav_id: int
    ) -> Dict[str, Any]:
        """Get collection content by favId."""
        client = self._get_gewe_client()
        return await client.get_collection_content(app_id=app_id, fav_id=fav_id)

    async def delete_collection(
        self,
        app_id: str,
        fav_id: int
    ) -> Dict[str, Any]:
        """Delete collection item."""
        client = self._get_gewe_client()
        return await client.delete_collection(app_id=app_id, fav_id=fav_id)
