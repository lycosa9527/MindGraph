"""Group Service Module.

Handles group-related service operations with database caching.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, List
import logging

from services.gewe.protocols import GeweServiceBase

logger = logging.getLogger(__name__)


class GroupServiceMixin(GeweServiceBase):
    """Mixin for group-related service methods"""

    async def create_chatroom(
        self,
        app_id: str,
        wxids: list
    ) -> Dict[str, Any]:
        """Create WeChat group."""
        client = self._get_gewe_client()
        return await client.create_chatroom(app_id=app_id, wxids=wxids)

    async def modify_chatroom_name(
        self,
        app_id: str,
        chatroom_id: str,
        chatroom_name: str
    ) -> Dict[str, Any]:
        """Modify group name."""
        client = self._get_gewe_client()
        return await client.modify_chatroom_name(
            app_id=app_id,
            chatroom_id=chatroom_id,
            chatroom_name=chatroom_name
        )

    async def modify_chatroom_remark(
        self,
        app_id: str,
        chatroom_id: str,
        chatroom_remark: str
    ) -> Dict[str, Any]:
        """Modify group remark (only visible to self)."""
        client = self._get_gewe_client()
        return await client.modify_chatroom_remark(
            app_id=app_id,
            chatroom_id=chatroom_id,
            chatroom_remark=chatroom_remark
        )

    async def modify_chatroom_nick_name_for_self(
        self,
        app_id: str,
        chatroom_id: str,
        nick_name: str
    ) -> Dict[str, Any]:
        """Modify my nickname in group."""
        client = self._get_gewe_client()
        return await client.modify_chatroom_nick_name_for_self(
            app_id=app_id,
            chatroom_id=chatroom_id,
            nick_name=nick_name
        )

    async def invite_member(
        self,
        app_id: str,
        chatroom_id: str,
        wxids: str,
        reason: str = ""
    ) -> Dict[str, Any]:
        """Invite members to group."""
        client = self._get_gewe_client()
        return await client.invite_member(
            app_id=app_id,
            chatroom_id=chatroom_id,
            wxids=wxids,
            reason=reason
        )

    async def remove_member(
        self,
        app_id: str,
        chatroom_id: str,
        wxids: str
    ) -> Dict[str, Any]:
        """Remove members from group."""
        client = self._get_gewe_client()
        return await client.remove_member(
            app_id=app_id,
            chatroom_id=chatroom_id,
            wxids=wxids
        )

    async def quit_chatroom(
        self,
        app_id: str,
        chatroom_id: str
    ) -> Dict[str, Any]:
        """Quit group."""
        client = self._get_gewe_client()
        return await client.quit_chatroom(app_id=app_id, chatroom_id=chatroom_id)

    async def disband_chatroom(
        self,
        app_id: str,
        chatroom_id: str
    ) -> Dict[str, Any]:
        """Disband group (only group owner can disband)."""
        client = self._get_gewe_client()
        return await client.disband_chatroom(app_id=app_id, chatroom_id=chatroom_id)

    async def get_chatroom_info(
        self,
        app_id: str,
        chatroom_id: str
    ) -> Dict[str, Any]:
        """Get group information."""
        client = self._get_gewe_client()
        return await client.get_chatroom_info(app_id=app_id, chatroom_id=chatroom_id)

    async def get_chatroom_member_list(
        self,
        app_id: str,
        chatroom_id: str
    ) -> Dict[str, Any]:
        """
        Get group member list from API and cache in database.

        Args:
            app_id: Gewe app ID
            chatroom_id: Group wxid

        Returns:
            API response with member list
        """
        client = self._get_gewe_client()
        response = await client.get_chatroom_member_list(app_id=app_id, chatroom_id=chatroom_id)

        # Cache group members in database
        if response and response.get("code") == 0:
            members = response.get("data", {}).get("members", [])
            if members:
                try:
                    saved_count = self._group_member_db.save_group_members(
                        app_id=app_id,
                        group_wxid=chatroom_id,
                        members=members
                    )
                    logger.info("Cached %d members for group %s", saved_count, chatroom_id)
                except Exception as e:
                    logger.warning("Failed to cache group members: %s", e)

        return response

    def get_cached_group_members(
        self,
        app_id: str,
        group_wxid: str
    ) -> List[Dict[str, Any]]:
        """
        Get group members from cache.

        Args:
            app_id: Gewe app ID
            group_wxid: Group wxid

        Returns:
            List of member dictionaries
        """
        return self._group_member_db.get_group_members(
            app_id=app_id,
            group_wxid=group_wxid
        )

    def get_cached_group_member(
        self,
        app_id: str,
        group_wxid: str,
        member_wxid: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get single group member from cache.

        Args:
            app_id: Gewe app ID
            group_wxid: Group wxid
            member_wxid: Member wxid

        Returns:
            Member dictionary or None if not cached
        """
        return self._group_member_db.get_group_member(
            app_id=app_id,
            group_wxid=group_wxid,
            member_wxid=member_wxid
        )

    async def get_chatroom_member_detail(
        self,
        app_id: str,
        chatroom_id: str,
        wxid: str
    ) -> Dict[str, Any]:
        """Get group member detail."""
        client = self._get_gewe_client()
        return await client.get_chatroom_member_detail(
            app_id=app_id,
            chatroom_id=chatroom_id,
            wxid=wxid
        )

    async def get_chatroom_announcement(
        self,
        app_id: str,
        chatroom_id: str
    ) -> Dict[str, Any]:
        """Get group announcement."""
        client = self._get_gewe_client()
        return await client.get_chatroom_announcement(
            app_id=app_id,
            chatroom_id=chatroom_id
        )

    async def set_chatroom_announcement(
        self,
        app_id: str,
        chatroom_id: str,
        content: str
    ) -> Dict[str, Any]:
        """Set group announcement (only group owner or admin can publish)."""
        client = self._get_gewe_client()
        return await client.set_chatroom_announcement(
            app_id=app_id,
            chatroom_id=chatroom_id,
            content=content
        )

    async def get_chatroom_qr_code(
        self,
        app_id: str,
        chatroom_id: str
    ) -> Dict[str, Any]:
        """Get group QR code."""
        client = self._get_gewe_client()
        return await client.get_chatroom_qr_code(
            app_id=app_id,
            chatroom_id=chatroom_id
        )

    async def admin_operate(
        self,
        app_id: str,
        chatroom_id: str,
        oper_type: int,
        wxids: list
    ) -> Dict[str, Any]:
        """Admin operations: add/remove admins, transfer ownership."""
        client = self._get_gewe_client()
        return await client.admin_operate(
            app_id=app_id,
            chatroom_id=chatroom_id,
            oper_type=oper_type,
            wxids=wxids
        )

    async def pin_chat(
        self,
        app_id: str,
        chatroom_id: str,
        top: bool
    ) -> Dict[str, Any]:
        """Pin/unpin chat."""
        client = self._get_gewe_client()
        return await client.pin_chat(
            app_id=app_id,
            chatroom_id=chatroom_id,
            top=top
        )

    async def set_msg_silence(
        self,
        app_id: str,
        chatroom_id: str,
        silence: bool
    ) -> Dict[str, Any]:
        """Set message do not disturb."""
        client = self._get_gewe_client()
        return await client.set_msg_silence(
            app_id=app_id,
            chatroom_id=chatroom_id,
            silence=silence
        )
