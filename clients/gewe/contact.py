"""Contact Management Module.

Handles contact/friend operations: search, add, delete, modify, and phone contacts.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, Protocol


class _GeweClientProtocol(Protocol):
    """Protocol defining the interface expected by ContactMixin"""
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Gewe API"""
        raise NotImplementedError


class ContactMixin:
    """Mixin for contact/friend management APIs"""

    async def fetch_contacts_list(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """Get contacts list (friends, chatrooms, ghs)."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/contacts/fetchContactsList", json_data=payload)

    async def get_contacts_list_cache(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """Get contacts list cache (faster than fetch_contacts_list)."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/contacts/fetchContactsListCache", json_data=payload)

    async def get_brief_info(
        self: "_GeweClientProtocol",
        app_id: str,
        wxids: list
    ) -> Dict[str, Any]:
        """Get brief info for contacts."""
        payload = {
            "appId": app_id,
            "wxids": wxids
        }
        return await self._request("POST", "/gewe/v2/api/contacts/getBriefInfo", json_data=payload)

    async def get_detailed_info(
        self: "_GeweClientProtocol",
        app_id: str,
        wxids: list
    ) -> Dict[str, Any]:
        """Get detailed contact/group information."""
        payload = {
            "appId": app_id,
            "wxids": wxids
        }
        return await self._request("POST", "/gewe/v2/api/contacts/getDetailInfo", json_data=payload)

    async def search_contacts(
        self: "_GeweClientProtocol",
        app_id: str,
        contacts_info: str
    ) -> Dict[str, Any]:
        """Search contacts. Returns v3, v4, nickname, etc."""
        payload = {
            "appId": app_id,
            "contactsInfo": contacts_info
        }
        return await self._request("POST", "/gewe/v2/api/contacts/search", json_data=payload)

    async def add_contacts(
        self: "_GeweClientProtocol",
        app_id: str,
        scene: int,
        option: int,
        v3: str,
        v4: str,
        content: str
    ) -> Dict[str, Any]:
        """Add contact or agree to friend request. Option: 2=add, 3=agree, 4=reject."""
        payload = {
            "appId": app_id,
            "scene": scene,
            "option": option,
            "v3": v3,
            "v4": v4,
            "content": content
        }
        return await self._request("POST", "/gewe/v2/api/contacts/addContacts", json_data=payload)

    async def delete_friend(
        self: "_GeweClientProtocol",
        app_id: str,
        wxid: str
    ) -> Dict[str, Any]:
        """Delete friend."""
        payload = {
            "appId": app_id,
            "wxid": wxid
        }
        return await self._request("POST", "/gewe/v2/api/contacts/deleteFriend", json_data=payload)

    async def set_friend_permissions(
        self: "_GeweClientProtocol",
        app_id: str,
        wxid: str,
        chat_only: bool
    ) -> Dict[str, Any]:
        """Set friend chat only permissions."""
        payload = {
            "appId": app_id,
            "wxid": wxid,
            "chatOnly": chat_only
        }
        return await self._request("POST", "/gewe/v2/api/contacts/setFriendPermissions", json_data=payload)

    async def set_friend_remark(
        self: "_GeweClientProtocol",
        app_id: str,
        wxid: str,
        remark: str
    ) -> Dict[str, Any]:
        """Set friend remark."""
        payload = {
            "appId": app_id,
            "wxid": wxid,
            "remark": remark
        }
        return await self._request("POST", "/gewe/v2/api/contacts/setFriendRemark", json_data=payload)

    async def get_phone_contacts(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """Get phone contacts."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/contacts/getPhoneAddressList", json_data=payload)

    async def upload_phone_contacts(
        self: "_GeweClientProtocol",
        app_id: str,
        contacts: list
    ) -> Dict[str, Any]:
        """Upload phone contacts."""
        payload = {
            "appId": app_id,
            "contacts": contacts
        }
        return await self._request("POST", "/gewe/v2/api/contacts/uploadPhoneAddressList", json_data=payload)

    async def check_friend_relationship(
        self: "_GeweClientProtocol",
        app_id: str,
        wxids: list
    ) -> Dict[str, Any]:
        """
        Check friend relationship.
        
        Args:
            wxids: List of wxids to check (1-20 items)
        
        Returns:
            List of relationship statuses:
            - 0: Normal
            - 1: Deleted
            - 2: Blocked by friend
            - 3: Blocked friend
            - 4: Function error
            - 5: Check too frequent
            - 6: Unknown status
            - 7: Unknown error
            - 99: Other
        """
        payload = {
            "appId": app_id,
            "wxids": wxids
        }
        return await self._request("POST", "/gewe/v2/api/contacts/checkRelation", json_data=payload)
