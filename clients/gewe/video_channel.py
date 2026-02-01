"""Video Channel Module.

Handles WeChat Video Channel (视频号) operations: follow, comment, browse, publish, etc.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, Optional, Protocol


class _GeweClientProtocol(Protocol):
    """Protocol defining the interface expected by VideoChannelMixin"""
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Gewe API"""
        raise NotImplementedError


class VideoChannelMixin:
    """Mixin for video channel APIs"""

    async def follow_video_channel(
        self: "_GeweClientProtocol",
        app_id: str,
        finder_username: str
    ) -> Dict[str, Any]:
        """Follow a video channel."""
        payload = {
            "appId": app_id,
            "finderUsername": finder_username
        }
        return await self._request("POST", "/gewe/v2/api/video/follow", json_data=payload)

    async def comment_video_channel(
        self: "_GeweClientProtocol",
        app_id: str,
        object_id: str,
        content: str,
        reply_to_comment_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Comment on a video."""
        payload = {
            "appId": app_id,
            "objectId": object_id,
            "content": content
        }
        if reply_to_comment_id:
            payload["replyToCommentId"] = reply_to_comment_id
        return await self._request("POST", "/gewe/v2/api/video/comment", json_data=payload)

    async def browse_video_channel(
        self: "_GeweClientProtocol",
        app_id: str,
        object_id: str
    ) -> Dict[str, Any]:
        """Browse a video (mark as viewed)."""
        payload = {
            "appId": app_id,
            "objectId": object_id
        }
        return await self._request("POST", "/gewe/v2/api/video/browse", json_data=payload)

    async def publish_video(
        self: "_GeweClientProtocol",
        app_id: str,
        video_url: str,
        thumb_url: str,
        title: Optional[str] = None,
        desc: Optional[str] = None
    ) -> Dict[str, Any]:
        """Publish a video to video channel."""
        payload = {
            "appId": app_id,
            "videoUrl": video_url,
            "thumbUrl": thumb_url
        }
        if title:
            payload["title"] = title
        if desc:
            payload["desc"] = desc
        return await self._request("POST", "/gewe/v2/api/video/publishVideo", json_data=payload)

    async def get_video_channel_user_home(
        self: "_GeweClientProtocol",
        app_id: str,
        finder_username: str
    ) -> Dict[str, Any]:
        """
        Get video channel user homepage.
        
        Note: Video IDs in response may have precision loss (ending in 000).
        Use Raw or Text response format to avoid precision loss.
        """
        payload = {
            "appId": app_id,
            "finderUsername": finder_username
        }
        return await self._request("POST", "/gewe/v2/api/video/userHome", json_data=payload)

    async def get_follow_list(
        self: "_GeweClientProtocol",
        app_id: str,
        start_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get follow list."""
        payload = {"appId": app_id}
        if start_id:
            payload["startId"] = str(start_id)
        return await self._request("POST", "/gewe/v2/api/video/followList", json_data=payload)

    async def get_message_list(
        self: "_GeweClientProtocol",
        app_id: str,
        start_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get message list."""
        payload = {"appId": app_id}
        if start_id:
            payload["startId"] = str(start_id)
        return await self._request("POST", "/gewe/v2/api/video/messageList", json_data=payload)

    async def get_comment_list(
        self: "_GeweClientProtocol",
        app_id: str,
        object_id: str,
        start_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get comment list for a video."""
        payload = {
            "appId": app_id,
            "objectId": object_id
        }
        if start_id:
            payload["startId"] = str(start_id)
        return await self._request("POST", "/gewe/v2/api/video/commentList", json_data=payload)

    async def get_liked_and_favorited_videos(
        self: "_GeweClientProtocol",
        app_id: str,
        start_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Get liked and favorited videos list."""
        payload = {"appId": app_id}
        if start_id:
            payload["startId"] = str(start_id)
        return await self._request("POST", "/gewe/v2/api/video/getLikedAndFavoritedVideos", json_data=payload)

    async def search_video_channel(
        self: "_GeweClientProtocol",
        app_id: str,
        keyword: str
    ) -> Dict[str, Any]:
        """Search video channel."""
        payload = {
            "appId": app_id,
            "keyword": keyword
        }
        return await self._request("POST", "/gewe/v2/api/video/searchVideoChannel", json_data=payload)

    async def create_video_channel(
        self: "_GeweClientProtocol",
        app_id: str,
        nickname: str,
        signature: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a video channel."""
        payload = {
            "appId": app_id,
            "nickname": nickname
        }
        if signature:
            payload["signature"] = signature
        return await self._request("POST", "/gewe/v2/api/video/createVideoChannel", json_data=payload)

    async def sync_private_messages(
        self: "_GeweClientProtocol",
        app_id: str,
        start_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Sync private messages."""
        payload = {"appId": app_id}
        if start_id:
            payload["startId"] = str(start_id)
        return await self._request("POST", "/gewe/v2/api/video/syncPrivateMessages", json_data=payload)

    async def like_video_by_id(
        self: "_GeweClientProtocol",
        app_id: str,
        object_id: str
    ) -> Dict[str, Any]:
        """Like a video by ID."""
        payload = {
            "appId": app_id,
            "objectId": object_id
        }
        return await self._request("POST", "/gewe/v2/api/video/likeById", json_data=payload)

    async def favorite_video_by_id(
        self: "_GeweClientProtocol",
        app_id: str,
        object_id: str
    ) -> Dict[str, Any]:
        """Favorite (small heart) a video by ID."""
        payload = {
            "appId": app_id,
            "objectId": object_id
        }
        return await self._request("POST", "/gewe/v2/api/video/favoriteById", json_data=payload)

    async def get_my_video_channel_info(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """Get my video channel information."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/video/getMyVideoChannelInfo", json_data=payload)

    async def update_my_video_channel_info(
        self: "_GeweClientProtocol",
        app_id: str,
        nickname: Optional[str] = None,
        signature: Optional[str] = None,
        avatar_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update my video channel information."""
        payload = {"appId": app_id}
        if nickname:
            payload["nickname"] = nickname
        if signature:
            payload["signature"] = signature
        if avatar_url:
            payload["avatarUrl"] = avatar_url
        return await self._request("POST", "/gewe/v2/api/video/updateMyVideoChannelInfo", json_data=payload)

    async def send_video_channel_message(
        self: "_GeweClientProtocol",
        app_id: str,
        finder_username: str,
        content: str
    ) -> Dict[str, Any]:
        """Send video channel message."""
        payload = {
            "appId": app_id,
            "finderUsername": finder_username,
            "content": content
        }
        return await self._request("POST", "/gewe/v2/api/video/sendVideoChannelMessage", json_data=payload)

    async def send_video_channel_moment(
        self: "_GeweClientProtocol",
        app_id: str,
        object_id: str
    ) -> Dict[str, Any]:
        """Send video channel moment."""
        payload = {
            "appId": app_id,
            "objectId": object_id
        }
        return await self._request("POST", "/gewe/v2/api/video/sendVideoChannelMoment", json_data=payload)

    async def get_private_message_user_info(
        self: "_GeweClientProtocol",
        app_id: str,
        finder_username: str
    ) -> Dict[str, Any]:
        """Get private message user information."""
        payload = {
            "appId": app_id,
            "finderUsername": finder_username
        }
        return await self._request("POST", "/gewe/v2/api/video/getPrivateMessageUserInfo", json_data=payload)

    async def send_private_text_message(
        self: "_GeweClientProtocol",
        app_id: str,
        finder_username: str,
        content: str
    ) -> Dict[str, Any]:
        """Send private text message."""
        payload = {
            "appId": app_id,
            "finderUsername": finder_username,
            "content": content
        }
        return await self._request("POST", "/gewe/v2/api/video/sendPrivateTextMessage", json_data=payload)

    async def send_private_image_message(
        self: "_GeweClientProtocol",
        app_id: str,
        finder_username: str,
        image_url: str
    ) -> Dict[str, Any]:
        """Send private image message."""
        payload = {
            "appId": app_id,
            "finderUsername": finder_username,
            "imageUrl": image_url
        }
        return await self._request("POST", "/gewe/v2/api/video/sendPrivateImageMessage", json_data=payload)

    async def scan_qr_follow(
        self: "_GeweClientProtocol",
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Follow video channel by scanning QR code."""
        payload = {
            "appId": app_id,
            "qrUrl": qr_url
        }
        return await self._request("POST", "/gewe/v2/api/video/scanQrFollow", json_data=payload)

    async def search_and_follow(
        self: "_GeweClientProtocol",
        app_id: str,
        keyword: str
    ) -> Dict[str, Any]:
        """Search and follow video channel."""
        payload = {
            "appId": app_id,
            "keyword": keyword
        }
        return await self._request("POST", "/gewe/v2/api/video/searchAndFollow", json_data=payload)

    async def scan_qr_browse(
        self: "_GeweClientProtocol",
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Browse video by scanning QR code."""
        payload = {
            "appId": app_id,
            "qrUrl": qr_url
        }
        return await self._request("POST", "/gewe/v2/api/video/scanQrBrowse", json_data=payload)

    async def scan_qr_comment(
        self: "_GeweClientProtocol",
        app_id: str,
        qr_url: str,
        content: str
    ) -> Dict[str, Any]:
        """Comment on video by scanning QR code."""
        payload = {
            "appId": app_id,
            "qrUrl": qr_url,
            "content": content
        }
        return await self._request("POST", "/gewe/v2/api/video/scanQrComment", json_data=payload)

    async def scan_qr_like(
        self: "_GeweClientProtocol",
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Like video by scanning QR code."""
        payload = {
            "appId": app_id,
            "qrUrl": qr_url
        }
        return await self._request("POST", "/gewe/v2/api/video/scanQrLike", json_data=payload)

    async def scan_qr_favorite(
        self: "_GeweClientProtocol",
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Favorite video by scanning QR code."""
        payload = {
            "appId": app_id,
            "qrUrl": qr_url
        }
        return await self._request("POST", "/gewe/v2/api/video/scanQrFavorite", json_data=payload)

    async def delayed_like_favorite(
        self: "_GeweClientProtocol",
        app_id: str,
        object_id: str,
        delay_seconds: int,
        like: bool = True,
        favorite: bool = False
    ) -> Dict[str, Any]:
        """Delayed like/favorite video."""
        payload = {
            "appId": app_id,
            "objectId": object_id,
            "delaySeconds": delay_seconds,
            "like": like,
            "favorite": favorite
        }
        return await self._request("POST", "/gewe/v2/api/video/delayedLikeFavorite", json_data=payload)

    async def scan_qr_login_video_helper(
        self: "_GeweClientProtocol",
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Login video channel helper by scanning QR code."""
        payload = {
            "appId": app_id,
            "qrUrl": qr_url
        }
        return await self._request("POST", "/gewe/v2/api/video/scanQrLoginVideoHelper", json_data=payload)

    async def scan_qr_get_video_detail(
        self: "_GeweClientProtocol",
        app_id: str,
        qr_url: str
    ) -> Dict[str, Any]:
        """Get video detail by scanning QR code."""
        payload = {
            "appId": app_id,
            "qrUrl": qr_url
        }
        return await self._request("POST", "/gewe/v2/api/video/scanQrGetVideoDetail", json_data=payload)

    async def get_my_video_channel_qr_code(
        self: "_GeweClientProtocol",
        app_id: str
    ) -> Dict[str, Any]:
        """Get my video channel QR code."""
        payload = {"appId": app_id}
        return await self._request("POST", "/gewe/v2/api/video/getMyVideoChannelQrCode", json_data=payload)

    async def upload_cdn_video(
        self: "_GeweClientProtocol",
        app_id: str,
        video_url: str,
        thumb_url: str
    ) -> Dict[str, Any]:
        """
        Upload video to CDN.
        
        For batch publishing: upload once, then use publishCdnVideo for other accounts.
        """
        payload = {
            "appId": app_id,
            "videoUrl": video_url,
            "thumbUrl": thumb_url
        }
        return await self._request("POST", "/gewe/v2/api/video/uploadCdnVideo", json_data=payload)

    async def publish_cdn_video(
        self: "_GeweClientProtocol",
        app_id: str,
        cdn_video_id: str,
        title: Optional[str] = None,
        desc: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publish CDN video.
        
        For batch publishing: upload once with uploadCdnVideo, then publish with this endpoint.
        """
        payload = {
            "appId": app_id,
            "cdnVideoId": cdn_video_id
        }
        if title:
            payload["title"] = title
        if desc:
            payload["desc"] = desc
        return await self._request("POST", "/gewe/v2/api/video/publishCdnVideo", json_data=payload)
