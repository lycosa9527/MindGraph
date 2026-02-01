"""Video Channel Service Module.

Handles video channel-related service operations.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional

from services.gewe.protocols import GeweServiceBase


class VideoChannelServiceMixin(GeweServiceBase):
    """Mixin for video channel-related service methods"""

    async def follow_video_channel(
        self,
        app_id: str,
        finder_username: str
    ) -> Dict[str, Any]:
        """Follow a video channel."""
        client = self._get_gewe_client()
        return await client.follow_video_channel(
            app_id=app_id,
            finder_username=finder_username
        )

    async def comment_video_channel(
        self,
        app_id: str,
        object_id: str,
        content: str,
        reply_to_comment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Comment on a video."""
        client = self._get_gewe_client()
        return await client.comment_video_channel(
            app_id=app_id,
            object_id=object_id,
            content=content,
            reply_to_comment_id=reply_to_comment_id
        )

    async def browse_video_channel(
        self,
        app_id: str,
        object_id: str
    ) -> Dict[str, Any]:
        """Browse a video (mark as viewed)."""
        client = self._get_gewe_client()
        return await client.browse_video_channel(
            app_id=app_id,
            object_id=object_id
        )

    async def publish_video(
        self,
        app_id: str,
        video_url: str,
        thumb_url: str,
        title: Optional[str] = None,
        desc: Optional[str] = None
    ) -> Dict[str, Any]:
        """Publish a video to video channel."""
        client = self._get_gewe_client()
        return await client.publish_video(
            app_id=app_id,
            video_url=video_url,
            thumb_url=thumb_url,
            title=title,
            desc=desc
        )

    async def get_video_channel_user_home(
        self,
        app_id: str,
        finder_username: str
    ) -> Dict[str, Any]:
        """Get video channel user homepage."""
        client = self._get_gewe_client()
        return await client.get_video_channel_user_home(
            app_id=app_id,
            finder_username=finder_username
        )

    async def get_follow_list(
        self,
        app_id: str,
        start_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get follow list."""
        client = self._get_gewe_client()
        return await client.get_follow_list(
            app_id=app_id,
            start_id=start_id
        )

    async def get_message_list(
        self,
        app_id: str,
        start_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get message list."""
        client = self._get_gewe_client()
        return await client.get_message_list(
            app_id=app_id,
            start_id=start_id
        )

    async def get_comment_list(
        self,
        app_id: str,
        object_id: str,
        start_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get comment list for a video."""
        client = self._get_gewe_client()
        return await client.get_comment_list(
            app_id=app_id,
            object_id=object_id,
            start_id=start_id
        )

    async def get_liked_and_favorited_videos(
        self,
        app_id: str,
        start_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get liked and favorited videos list."""
        client = self._get_gewe_client()
        return await client.get_liked_and_favorited_videos(
            app_id=app_id,
            start_id=start_id
        )

    async def search_video_channel(
        self,
        app_id: str,
        keyword: str
    ) -> Dict[str, Any]:
        """Search video channel."""
        client = self._get_gewe_client()
        return await client.search_video_channel(
            app_id=app_id,
            keyword=keyword
        )

    async def create_video_channel(
        self,
        app_id: str,
        nickname: str,
        signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a video channel."""
        client = self._get_gewe_client()
        return await client.create_video_channel(
            app_id=app_id,
            nickname=nickname,
            signature=signature
        )

    async def sync_private_messages(
        self,
        app_id: str,
        start_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Sync private messages."""
        client = self._get_gewe_client()
        return await client.sync_private_messages(
            app_id=app_id,
            start_id=start_id
        )

    async def like_video_by_id(
        self,
        app_id: str,
        object_id: str
    ) -> Dict[str, Any]:
        """Like a video by ID."""
        client = self._get_gewe_client()
        return await client.like_video_by_id(
            app_id=app_id,
            object_id=object_id
        )

    async def favorite_video_by_id(
        self,
        app_id: str,
        object_id: str
    ) -> Dict[str, Any]:
        """Favorite (small heart) a video by ID."""
        client = self._get_gewe_client()
        return await client.favorite_video_by_id(
            app_id=app_id,
            object_id=object_id
        )

    async def get_my_video_channel_info(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Get my video channel information."""
        client = self._get_gewe_client()
        return await client.get_my_video_channel_info(app_id=app_id)

    async def update_my_video_channel_info(
        self,
        app_id: str,
        nickname: Optional[str] = None,
        signature: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update my video channel information."""
        client = self._get_gewe_client()
        return await client.update_my_video_channel_info(
            app_id=app_id,
            nickname=nickname,
            signature=signature,
            avatar_url=avatar_url
        )

    async def send_video_channel_message(
        self,
        app_id: str,
        finder_username: str,
        content: str
    ) -> Dict[str, Any]:
        """Send video channel message."""
        client = self._get_gewe_client()
        return await client.send_video_channel_message(
            app_id=app_id,
            finder_username=finder_username,
            content=content
        )

    async def send_video_channel_moment(
        self,
        app_id: str,
        object_id: str
    ) -> Dict[str, Any]:
        """Send video channel moment."""
        client = self._get_gewe_client()
        return await client.send_video_channel_moment(
            app_id=app_id,
            object_id=object_id
        )

    async def get_private_message_user_info(
        self,
        app_id: str,
        finder_username: str
    ) -> Dict[str, Any]:
        """Get private message user information."""
        client = self._get_gewe_client()
        return await client.get_private_message_user_info(
            app_id=app_id,
            finder_username=finder_username
        )

    async def send_private_text_message(
        self,
        app_id: str,
        finder_username: str,
        content: str
    ) -> Dict[str, Any]:
        """Send private text message."""
        client = self._get_gewe_client()
        return await client.send_private_text_message(
            app_id=app_id,
            finder_username=finder_username,
            content=content
        )

    async def send_private_image_message(
        self,
        app_id: str,
        finder_username: str,
        image_url: str
    ) -> Dict[str, Any]:
        """Send private image message."""
        client = self._get_gewe_client()
        return await client.send_private_image_message(
            app_id=app_id,
            finder_username=finder_username,
            image_url=image_url
        )

    async def scan_qr_follow(
        self,
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Follow video channel by scanning QR code."""
        client = self._get_gewe_client()
        return await client.scan_qr_follow(
            app_id=app_id,
            qr_url=qr_url
        )

    async def search_and_follow(
        self,
        app_id: str,
        keyword: str
    ) -> Dict[str, Any]:
        """Search and follow video channel."""
        client = self._get_gewe_client()
        return await client.search_and_follow(
            app_id=app_id,
            keyword=keyword
        )

    async def scan_qr_browse(
        self,
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Browse video by scanning QR code."""
        client = self._get_gewe_client()
        return await client.scan_qr_browse(
            app_id=app_id,
            qr_url=qr_url
        )

    async def scan_qr_comment(
        self,
        app_id: str,
        qr_url: str,
        content: str
    ) -> Dict[str, Any]:
        """Comment on video by scanning QR code."""
        client = self._get_gewe_client()
        return await client.scan_qr_comment(
            app_id=app_id,
            qr_url=qr_url,
            content=content
        )

    async def scan_qr_like(
        self,
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Like video by scanning QR code."""
        client = self._get_gewe_client()
        return await client.scan_qr_like(
            app_id=app_id,
            qr_url=qr_url
        )

    async def scan_qr_favorite(
        self,
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Favorite video by scanning QR code."""
        client = self._get_gewe_client()
        return await client.scan_qr_favorite(
            app_id=app_id,
            qr_url=qr_url
        )

    async def delayed_like_favorite(
        self,
        app_id: str,
        object_id: str,
        delay_seconds: int,
        like: bool = True,
        favorite: bool = False
    ) -> Dict[str, Any]:
        """Delayed like/favorite video."""
        client = self._get_gewe_client()
        return await client.delayed_like_favorite(
            app_id=app_id,
            object_id=object_id,
            delay_seconds=delay_seconds,
            like=like,
            favorite=favorite
        )

    async def scan_qr_login_video_helper(
        self,
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Login video channel helper by scanning QR code."""
        client = self._get_gewe_client()
        return await client.scan_qr_login_video_helper(
            app_id=app_id,
            qr_url=qr_url
        )

    async def scan_qr_get_video_detail(
        self,
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Get video detail by scanning QR code."""
        client = self._get_gewe_client()
        return await client.scan_qr_get_video_detail(
            app_id=app_id,
            qr_url=qr_url
        )

    async def get_my_video_channel_qr_code(
        self,
        app_id: str
    ) -> Dict[str, Any]:
        """Get my video channel QR code."""
        client = self._get_gewe_client()
        return await client.get_my_video_channel_qr_code(app_id=app_id)

    async def upload_cdn_video(
        self,
        app_id: str,
        video_url: str,
        thumb_url: str
    ) -> Dict[str, Any]:
        """Upload video to CDN."""
        client = self._get_gewe_client()
        return await client.upload_cdn_video(
            app_id=app_id,
            video_url=video_url,
            thumb_url=thumb_url
        )

    async def publish_cdn_video(
        self,
        app_id: str,
        cdn_video_id: str,
        title: Optional[str] = None,
        desc: Optional[str] = None
    ) -> Dict[str, Any]:
        """Publish CDN video."""
        client = self._get_gewe_client()
        return await client.publish_cdn_video(
            app_id=app_id,
            cdn_video_id=cdn_video_id,
            title=title,
            desc=desc
        )
