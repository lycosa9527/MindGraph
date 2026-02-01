"""Tag Service Module.

Handles tag-related service operations.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, List

from services.gewe.protocols import GeweServiceBase


class TagServiceMixin(GeweServiceBase):
    """Mixin for tag-related service methods"""

    async def add_tag(
        self,
        app_id: str,
        label_name: str
    ) -> Dict[str, Any]:
        """Add a new tag."""
        client = self._get_gewe_client()
        return await client.add_tag(app_id=app_id, label_name=label_name)

    async def delete_tag(
        self,
        app_id: str,
        label_ids: str
    ) -> Dict[str, Any]:
        """Delete tag(s)."""
        client = self._get_gewe_client()
        return await client.delete_tag(app_id=app_id, label_ids=label_ids)

    async def get_tag_list(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Get tag list."""
        client = self._get_gewe_client()
        return await client.get_tag_list(app_id=app_id)

    async def modify_friend_tags(
        self,
        app_id: str,
        wx_ids: List[str],
        label_ids: str
    ) -> Dict[str, Any]:
        """Modify friend tags."""
        client = self._get_gewe_client()
        return await client.modify_friend_tags(
            app_id=app_id,
            wx_ids=wx_ids,
            label_ids=label_ids
        )
