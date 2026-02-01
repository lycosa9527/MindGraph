"""Download Service Module.

Handles downloading files, images, voice, video, emoji, and CDN content.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any

from services.gewe.protocols import GeweServiceBase


class DownloadServiceMixin(GeweServiceBase):
    """Mixin for download-related service methods"""

    async def download_file(
        self,
        app_id: str,
        xml: str
    ) -> Dict[str, Any]:
        """Download file from message."""
        client = self._get_gewe_client()
        return await client.download_file(app_id=app_id, xml=xml)

    async def download_image(
        self,
        app_id: str,
        xml: str,
        image_type: int = 2
    ) -> Dict[str, Any]:
        """Download image from message."""
        client = self._get_gewe_client()
        return await client.download_image(app_id=app_id, xml=xml, image_type=image_type)

    async def download_voice(
        self,
        app_id: str,
        xml: str,
        msg_id: int
    ) -> Dict[str, Any]:
        """Download voice from message."""
        client = self._get_gewe_client()
        return await client.download_voice(app_id=app_id, xml=xml, msg_id=msg_id)

    async def download_video(
        self,
        app_id: str,
        xml: str
    ) -> Dict[str, Any]:
        """Download video from message."""
        client = self._get_gewe_client()
        return await client.download_video(app_id=app_id, xml=xml)

    async def download_emoji_md5(
        self,
        app_id: str,
        emoji_md5: str
    ) -> Dict[str, Any]:
        """Download emoji by MD5."""
        client = self._get_gewe_client()
        return await client.download_emoji_md5(app_id=app_id, emoji_md5=emoji_md5)

    async def download_cdn(
        self,
        app_id: str,
        aes_key: str,
        file_id: str,
        file_type: str,
        total_size: str,
        suffix: str
    ) -> Dict[str, Any]:
        """Download file from CDN."""
        client = self._get_gewe_client()
        return await client.download_cdn(
            app_id=app_id,
            aes_key=aes_key,
            file_id=file_id,
            file_type=file_type,
            total_size=total_size,
            suffix=suffix
        )
