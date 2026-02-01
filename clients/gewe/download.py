"""Message Download Module.

Handles downloading files, images, voice, video, emoji, and CDN content.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, Protocol


class _GeweClientProtocol(Protocol):
    """Protocol defining the interface expected by DownloadMixin"""
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Gewe API"""
        raise NotImplementedError


class DownloadMixin:
    """Mixin for message download APIs"""

    async def download_file(
        self: "_GeweClientProtocol",
        app_id: str,
        xml: str
    ) -> Dict[str, Any]:
        """Download file from message. Returns fileUrl valid for 7 days."""
        payload = {
            "appId": app_id,
            "xml": xml
        }
        return await self._request("POST", "/gewe/v2/api/message/downloadFile", json_data=payload)

    async def download_image(
        self: "_GeweClientProtocol",
        app_id: str,
        xml: str,
        image_type: int = 2
    ) -> Dict[str, Any]:
        """Download image from message. Type: 1=HD, 2=Regular, 3=Thumbnail."""
        payload = {
            "appId": app_id,
            "xml": xml,
            "type": image_type
        }
        return await self._request("POST", "/gewe/v2/api/message/downloadImage", json_data=payload)

    async def download_voice(
        self: "_GeweClientProtocol",
        app_id: str,
        xml: str,
        msg_id: int
    ) -> Dict[str, Any]:
        """Download voice from message. Returns fileUrl in SILK format, valid for 7 days."""
        payload = {
            "appId": app_id,
            "xml": xml,
            "msgId": msg_id
        }
        return await self._request("POST", "/gewe/v2/api/message/downloadVoice", json_data=payload)

    async def download_video(
        self: "_GeweClientProtocol",
        app_id: str,
        xml: str
    ) -> Dict[str, Any]:
        """Download video from message. Returns fileUrl valid for 7 days."""
        payload = {
            "appId": app_id,
            "xml": xml
        }
        return await self._request("POST", "/gewe/v2/api/message/downloadVideo", json_data=payload)

    async def download_emoji_md5(
        self: "_GeweClientProtocol",
        app_id: str,
        emoji_md5: str
    ) -> Dict[str, Any]:
        """Download emoji by MD5. Returns url valid for 7 days."""
        payload = {
            "appId": app_id,
            "emojiMd5": emoji_md5
        }
        return await self._request("POST", "/gewe/v2/api/message/downloadEmojiMd5", json_data=payload)

    async def download_cdn(
        self: "_GeweClientProtocol",
        app_id: str,
        aes_key: str,
        file_id: str,
        file_type: str,
        total_size: str,
        suffix: str
    ) -> Dict[str, Any]:
        """Download file from CDN. Type: 1=HD image, 2=Regular image, 3=Thumbnail, 4=Video, 5=File."""
        payload = {
            "appId": app_id,
            "aesKey": aes_key,
            "fileId": file_id,
            "type": file_type,
            "totalSize": total_size,
            "suffix": suffix
        }
        return await self._request("POST", "/gewe/v2/api/message/downloadCdn", json_data=payload)
