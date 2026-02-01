"""Group Management Module.

Handles group creation, modification, member management, announcements, and settings.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, Protocol


class _GeweClientProtocol(Protocol):
    """Protocol defining the interface expected by GroupMixin"""
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Gewe API"""
        raise NotImplementedError


class GroupMixin:
    """Mixin for group management APIs"""

    async def create_chatroom(
        self: "_GeweClientProtocol",
        app_id: str,
        wxids: list
    ) -> Dict[str, Any]:
        """Create WeChat group. Minimum 2 friends required."""
        payload = {
            "appId": app_id,
            "wxids": wxids
        }
        return await self._request("POST", "/gewe/v2/api/group/createChatroom", json_data=payload)

    async def modify_chatroom_name(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        chatroom_name: str
    ) -> Dict[str, Any]:
        """Modify group name."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "chatroomName": chatroom_name
        }
        return await self._request("POST", "/gewe/v2/api/group/modifyChatroomName", json_data=payload)

    async def modify_chatroom_remark(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        chatroom_remark: str
    ) -> Dict[str, Any]:
        """Modify group remark (only visible to self)."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "chatroomRemark": chatroom_remark
        }
        return await self._request("POST", "/gewe/v2/api/group/modifyChatroomRemark", json_data=payload)

    async def modify_chatroom_nick_name_for_self(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        nick_name: str
    ) -> Dict[str, Any]:
        """Modify my nickname in group."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "nickName": nick_name
        }
        return await self._request("POST", "/gewe/v2/api/group/modifyChatroomNickNameForSelf", json_data=payload)

    async def invite_member(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        wxids: str,
        reason: str = ""
    ) -> Dict[str, Any]:
        """Invite members to group."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "wxids": wxids,
            "reason": reason
        }
        return await self._request("POST", "/gewe/v2/api/group/inviteMember", json_data=payload)

    async def remove_member(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        wxids: str
    ) -> Dict[str, Any]:
        """Remove members from group."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "wxids": wxids
        }
        return await self._request("POST", "/gewe/v2/api/group/removeMember", json_data=payload)

    async def quit_chatroom(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str
    ) -> Dict[str, Any]:
        """Quit group."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id
        }
        return await self._request("POST", "/gewe/v2/api/group/quitChatroom", json_data=payload)

    async def disband_chatroom(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str
    ) -> Dict[str, Any]:
        """Disband group (only group owner can disband)."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id
        }
        return await self._request("POST", "/gewe/v2/api/group/disbandChatroom", json_data=payload)

    async def get_chatroom_info(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str
    ) -> Dict[str, Any]:
        """Get group information."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id
        }
        return await self._request("POST", "/gewe/v2/api/group/getChatroomInfo", json_data=payload)

    async def get_chatroom_member_list(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str
    ) -> Dict[str, Any]:
        """Get group member list."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id
        }
        return await self._request("POST", "/gewe/v2/api/group/getChatroomMemberList", json_data=payload)

    async def get_chatroom_member_detail(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        wxid: str
    ) -> Dict[str, Any]:
        """Get group member detail."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "wxid": wxid
        }
        return await self._request("POST", "/gewe/v2/api/group/getChatroomMemberDetail", json_data=payload)

    async def get_chatroom_announcement(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str
    ) -> Dict[str, Any]:
        """Get group announcement."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id
        }
        return await self._request("POST", "/gewe/v2/api/group/getChatroomAnnouncement", json_data=payload)

    async def set_chatroom_announcement(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        content: str
    ) -> Dict[str, Any]:
        """Set group announcement (only group owner or admin can publish)."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "content": content
        }
        return await self._request("POST", "/gewe/v2/api/group/setChatroomAnnouncement", json_data=payload)

    async def agree_join_room(
        self: "_GeweClientProtocol",
        app_id: str,
        url: str
    ) -> Dict[str, Any]:
        """Agree to join group."""
        payload = {
            "appId": app_id,
            "url": url
        }
        return await self._request("POST", "/gewe/v2/api/group/agreeJoinRoom", json_data=payload)

    async def add_group_member_as_friend(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        member_wxid: str,
        content: str
    ) -> Dict[str, Any]:
        """Add group member as friend."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "memberWxid": member_wxid,
            "content": content
        }
        return await self._request("POST", "/gewe/v2/api/group/addGroupMemberAsFriend", json_data=payload)

    async def get_chatroom_qr_code(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str
    ) -> Dict[str, Any]:
        """Get group QR code. Cannot be used within 1-3 days after login. Valid for 7 days."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id
        }
        return await self._request("POST", "/gewe/v2/api/group/getChatroomQrCode", json_data=payload)

    async def save_to_contacts(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        oper_type: int
    ) -> Dict[str, Any]:
        """Save group to contacts (3) or remove from contacts (2)."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "operType": oper_type
        }
        return await self._request("POST", "/gewe/v2/api/group/saveContractList", json_data=payload)

    async def admin_operate(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        oper_type: int,
        wxids: list
    ) -> Dict[str, Any]:
        """Admin operations: 1=add admin, 2=remove admin, 3=transfer ownership."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "operType": oper_type,
            "wxids": wxids
        }
        return await self._request("POST", "/gewe/v2/api/group/adminOperate", json_data=payload)

    async def pin_chat(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        top: bool
    ) -> Dict[str, Any]:
        """Pin/unpin chat."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "top": top
        }
        return await self._request("POST", "/gewe/v2/api/group/pinChat", json_data=payload)

    async def set_msg_silence(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        silence: bool
    ) -> Dict[str, Any]:
        """Set message do not disturb."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "silence": silence
        }
        return await self._request("POST", "/gewe/v2/api/group/setMsgSilence", json_data=payload)

    async def join_room_using_qr_code(
        self: "_GeweClientProtocol",
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Join group using QR code."""
        payload = {
            "appId": app_id,
            "qrUrl": qr_url
        }
        return await self._request("POST", "/gewe/v2/api/group/joinRoomUsingQRCode", json_data=payload)

    async def room_access_apply_check_approve(
        self: "_GeweClientProtocol",
        app_id: str,
        chatroom_id: str,
        new_msg_id: str,
        msg_content: str
    ) -> Dict[str, Any]:
        """Approve group join request."""
        payload = {
            "appId": app_id,
            "chatroomId": chatroom_id,
            "newMsgId": new_msg_id,
            "msgContent": msg_content
        }
        return await self._request("POST", "/gewe/v2/api/group/roomAccessApplyCheckApprove", json_data=payload)
