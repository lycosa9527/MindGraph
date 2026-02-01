"""Message Sending Module.

Handles sending various types of messages (text, file, image, voice, video, etc.).

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional


class MessageMixin:
    """Mixin for message sending APIs"""

    async def post_text(
        self,
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
        self,
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
        self,
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
        self,
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
        self,
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
        self,
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
        self,
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
        self,
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
        self,
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
        self,
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
        self,
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
