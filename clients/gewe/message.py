"""Message Sending Module.

Handles sending various types of messages (text, file, image, voice, video, etc.).

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, Protocol


class _GeweClientProtocol(Protocol):
    """Protocol defining the interface expected by MessageMixin"""
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Gewe API"""
        raise NotImplementedError


class MessageMixin:
    """Mixin for message sending APIs"""

    async def post_text(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        content: str,
        ats: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send text message."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "content": content
        }
        if ats:
            payload["ats"] = ats
        return await self._request("POST", "/gewe/v2/api/message/postText", json_data=payload)

    async def post_file(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        file_url: str,
        file_name: str
    ) -> Dict[str, Any]:
        """Send file message."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "fileUrl": file_url,
            "fileName": file_name
        }
        return await self._request("POST", "/gewe/v2/api/message/postFile", json_data=payload)

    async def post_image(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        img_url: str
    ) -> Dict[str, Any]:
        """Send image message. Returns CDN info for forwarding."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "imgUrl": img_url
        }
        return await self._request("POST", "/gewe/v2/api/message/postImage", json_data=payload)

    async def post_voice(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        voice_url: str,
        voice_duration: int
    ) -> Dict[str, Any]:
        """Send voice message (SILK format)."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "voiceUrl": voice_url,
            "voiceDuration": voice_duration
        }
        return await self._request("POST", "/gewe/v2/api/message/postVoice", json_data=payload)

    async def post_video(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        video_url: str,
        thumb_url: str,
        video_duration: int
    ) -> Dict[str, Any]:
        """Send video message. Returns CDN info for forwarding."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "videoUrl": video_url,
            "thumbUrl": thumb_url,
            "videoDuration": video_duration
        }
        return await self._request("POST", "/gewe/v2/api/message/postVideo", json_data=payload)

    async def post_link(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        title: str,
        desc: str,
        link_url: str,
        thumb_url: str
    ) -> Dict[str, Any]:
        """Send link message."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "title": title,
            "desc": desc,
            "linkUrl": link_url,
            "thumbUrl": thumb_url
        }
        return await self._request("POST", "/gewe/v2/api/message/postLink", json_data=payload)

    async def post_name_card(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        nick_name: str,
        name_card_wxid: str
    ) -> Dict[str, Any]:
        """Send name card (contact card) message."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "nickName": nick_name,
            "nameCardWxid": name_card_wxid
        }
        return await self._request("POST", "/gewe/v2/api/message/postNameCard", json_data=payload)

    async def post_emoji(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        emoji_md5: str,
        emoji_size: int
    ) -> Dict[str, Any]:
        """Send emoji message."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "emojiMd5": emoji_md5,
            "emojiSize": emoji_size
        }
        return await self._request("POST", "/gewe/v2/api/message/postEmoji", json_data=payload)

    async def post_app_msg(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        appmsg: str
    ) -> Dict[str, Any]:
        """Send app message (mini-program, music share, video channel, etc.)."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "appmsg": appmsg
        }
        return await self._request("POST", "/gewe/v2/api/message/postAppMsg", json_data=payload)

    async def forward_file(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        xml: str
    ) -> Dict[str, Any]:
        """Forward file message using CDN info."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "xml": xml
        }
        return await self._request("POST", "/gewe/v2/api/message/forwardFile", json_data=payload)

    async def forward_image(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        xml: str
    ) -> Dict[str, Any]:
        """Forward image message using CDN info."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "xml": xml
        }
        return await self._request("POST", "/gewe/v2/api/message/forwardImage", json_data=payload)

    async def forward_video(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        xml: str
    ) -> Dict[str, Any]:
        """Forward video message using CDN info."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "xml": xml
        }
        return await self._request("POST", "/gewe/v2/api/message/forwardVideo", json_data=payload)

    async def forward_link(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        xml: str
    ) -> Dict[str, Any]:
        """Forward link message using CDN info."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "xml": xml
        }
        return await self._request("POST", "/gewe/v2/api/message/forwardUrl", json_data=payload)

    async def forward_mini_program(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        xml: str,
        cover_img_url: str
    ) -> Dict[str, Any]:
        """Forward mini-program message using CDN info."""
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "xml": xml,
            "coverImgUrl": cover_img_url
        }
        return await self._request("POST", "/gewe/v2/api/message/forwardMiniApp", json_data=payload)

    async def revoke_message(
        self: "_GeweClientProtocol",
        app_id: str,
        to_wxid: str,
        msg_id: str,
        new_msg_id: str,
        create_time: str
    ) -> Dict[str, Any]:
        """
        Revoke (recall) a sent message.
        
        Requires msgId, newMsgId, and createTime from the original send response.
        """
        payload = {
            "appId": app_id,
            "toWxid": to_wxid,
            "msgId": msg_id,
            "newMsgId": new_msg_id,
            "createTime": create_time
        }
        return await self._request("POST", "/gewe/v2/api/message/revokeMsg", json_data=payload)
