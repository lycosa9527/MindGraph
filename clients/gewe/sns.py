"""Social Network (Moments) Module.

Handles moments/SNS operations: like, comment, publish, delete, and manage visibility.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, List, Optional, Protocol


class _GeweClientProtocol(Protocol):
    """Protocol defining the interface expected by SNSMixin"""
    async def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Gewe API"""
        raise NotImplementedError


class SNSMixin:
    """Mixin for social network (moments) APIs"""

    async def like_sns(
        self: "_GeweClientProtocol",
        app_id: str,
        sns_id: int,
        oper_type: int,
        wxid: str
    ) -> Dict[str, Any]:
        """
        Like or unlike a moment.
        
        Cannot be used within 1-3 days after login.
        operType: 1=like, 2=unlike
        """
        payload = {
            "appId": app_id,
            "snsId": sns_id,
            "operType": oper_type,
            "wxid": wxid
        }
        return await self._request("POST", "/gewe/v2/api/sns/likeSns", json_data=payload)

    async def delete_sns(
        self: "_GeweClientProtocol",
        app_id: str,
        sns_id: int
    ) -> Dict[str, Any]:
        """Delete a moment. Cannot be used within 1-3 days after login."""
        payload = {
            "appId": app_id,
            "snsId": sns_id
        }
        return await self._request("POST", "/gewe/v2/api/sns/delSns", json_data=payload)

    async def set_sns_visibility(
        self: "_GeweClientProtocol",
        app_id: str,
        option: int
    ) -> Dict[str, Any]:
        """
        Set moment visibility range.
        
        Option values:
        - 1: All
        - 2: Last 6 months
        - 3: Last month
        - 4: Last 3 days
        """
        payload = {
            "appId": app_id,
            "option": option
        }
        return await self._request("POST", "/gewe/v2/api/sns/snsVisibleScope", json_data=payload)

    async def set_allow_stranger_view_sns(
        self: "_GeweClientProtocol",
        app_id: str,
        enabled: bool
    ) -> Dict[str, Any]:
        """Set whether strangers can view moments."""
        payload = {
            "appId": app_id,
            "enabled": enabled
        }
        return await self._request("POST", "/gewe/v2/api/sns/strangerVisibilityEnabled", json_data=payload)

    async def set_sns_privacy(
        self: "_GeweClientProtocol",
        app_id: str,
        sns_id: int,
        is_open: bool
    ) -> Dict[str, Any]:
        """Set moment as private or public."""
        payload = {
            "appId": app_id,
            "snsId": sns_id,
            "open": is_open
        }
        return await self._request("POST", "/gewe/v2/api/sns/snsSetPrivacy", json_data=payload)

    async def download_sns_video(
        self: "_GeweClientProtocol",
        app_id: str,
        sns_xml: str
    ) -> Dict[str, Any]:
        """Download moment video."""
        payload = {
            "appId": app_id,
            "snsXml": sns_xml
        }
        return await self._request("POST", "/gewe/v2/api/sns/downloadSnsVideo", json_data=payload)

    async def send_text_sns(
        self: "_GeweClientProtocol",
        app_id: str,
        content: str,
        allow_wx_ids: Optional[List[str]] = None,
        at_wx_ids: Optional[List[str]] = None,
        disable_wx_ids: Optional[List[str]] = None,
        privacy: bool = False,
        allow_tag_ids: Optional[List[str]] = None,
        disable_tag_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send text moment.
        
        Cannot be used within 1-3 days after login.
        """
        payload = {
            "appId": app_id,
            "content": content,
            "privacy": privacy
        }
        if allow_wx_ids is not None:
            payload["allowWxIds"] = allow_wx_ids
        if at_wx_ids is not None:
            payload["atWxIds"] = at_wx_ids
        if disable_wx_ids is not None:
            payload["disableWxIds"] = disable_wx_ids
        if allow_tag_ids is not None:
            payload["allowTagIds"] = allow_tag_ids
        if disable_tag_ids is not None:
            payload["disableTagIds"] = disable_tag_ids
        return await self._request("POST", "/gewe/v2/api/sns/sendTextSns", json_data=payload)

    async def send_image_sns(
        self: "_GeweClientProtocol",
        app_id: str,
        img_infos: List[Dict[str, Any]],
        content: Optional[str] = None,
        allow_wx_ids: Optional[List[str]] = None,
        at_wx_ids: Optional[List[str]] = None,
        disable_wx_ids: Optional[List[str]] = None,
        privacy: bool = False,
        allow_tag_ids: Optional[List[str]] = None,
        disable_tag_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send image moment.
        
        imgInfos should be obtained from upload_sns_image.
        Cannot be used within 1-3 days after login.
        """
        payload = {
            "appId": app_id,
            "imgInfos": img_infos,
            "privacy": privacy
        }
        if content:
            payload["content"] = content
        if allow_wx_ids is not None:
            payload["allowWxIds"] = allow_wx_ids
        if at_wx_ids is not None:
            payload["atWxIds"] = at_wx_ids
        if disable_wx_ids is not None:
            payload["disableWxIds"] = disable_wx_ids
        if allow_tag_ids is not None:
            payload["allowTagIds"] = allow_tag_ids
        if disable_tag_ids is not None:
            payload["disableTagIds"] = disable_tag_ids
        return await self._request("POST", "/gewe/v2/api/sns/sendImgSns", json_data=payload)

    async def send_video_sns(
        self: "_GeweClientProtocol",
        app_id: str,
        video_info: Dict[str, Any],
        content: Optional[str] = None,
        allow_wx_ids: Optional[List[str]] = None,
        at_wx_ids: Optional[List[str]] = None,
        disable_wx_ids: Optional[List[str]] = None,
        privacy: bool = False,
        allow_tag_ids: Optional[List[str]] = None,
        disable_tag_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send video moment.
        
        videoInfo should be obtained from upload_sns_video.
        Cannot be used within 1-3 days after login.
        """
        payload = {
            "appId": app_id,
            "videoInfo": video_info,
            "privacy": privacy
        }
        if content:
            payload["content"] = content
        if allow_wx_ids is not None:
            payload["allowWxIds"] = allow_wx_ids
        if at_wx_ids is not None:
            payload["atWxIds"] = at_wx_ids
        if disable_wx_ids is not None:
            payload["disableWxIds"] = disable_wx_ids
        if allow_tag_ids is not None:
            payload["allowTagIds"] = allow_tag_ids
        if disable_tag_ids is not None:
            payload["disableTagIds"] = disable_tag_ids
        return await self._request("POST", "/gewe/v2/api/sns/sendVideoSns", json_data=payload)

    async def send_link_sns(
        self: "_GeweClientProtocol",
        app_id: str,
        link_url: str,
        title: str,
        description: str,
        thumb_url: str,
        content: Optional[str] = None,
        allow_wx_ids: Optional[List[str]] = None,
        at_wx_ids: Optional[List[str]] = None,
        disable_wx_ids: Optional[List[str]] = None,
        privacy: bool = False,
        allow_tag_ids: Optional[List[str]] = None,
        disable_tag_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send link moment.
        
        Cannot be used within 1-3 days after login.
        """
        payload = {
            "appId": app_id,
            "linkUrl": link_url,
            "title": title,
            "description": description,
            "thumbUrl": thumb_url,
            "privacy": privacy
        }
        if content:
            payload["content"] = content
        if allow_wx_ids is not None:
            payload["allowWxIds"] = allow_wx_ids
        if at_wx_ids is not None:
            payload["atWxIds"] = at_wx_ids
        if disable_wx_ids is not None:
            payload["disableWxIds"] = disable_wx_ids
        if allow_tag_ids is not None:
            payload["allowTagIds"] = allow_tag_ids
        if disable_tag_ids is not None:
            payload["disableTagIds"] = disable_tag_ids
        return await self._request("POST", "/gewe/v2/api/sns/sendUrlSns", json_data=payload)

    async def upload_sns_image(
        self: "_GeweClientProtocol",
        app_id: str,
        img_urls: List[str]
    ) -> Dict[str, Any]:
        """Upload images for moment. Returns imgInfos array for use in send_image_sns."""
        payload = {
            "appId": app_id,
            "imgUrls": img_urls
        }
        return await self._request("POST", "/gewe/v2/api/sns/uploadSnsImage", json_data=payload)

    async def upload_sns_video(
        self: "_GeweClientProtocol",
        app_id: str,
        video_url: str,
        thumb_url: str
    ) -> Dict[str, Any]:
        """Upload video for moment. Returns videoInfo object for use in send_video_sns."""
        payload = {
            "appId": app_id,
            "videoUrl": video_url,
            "thumbUrl": thumb_url
        }
        return await self._request("POST", "/gewe/v2/api/sns/uploadSnsVideo", json_data=payload)

    async def forward_sns(
        self: "_GeweClientProtocol",
        app_id: str,
        sns_xml: str,
        allow_wx_ids: Optional[List[str]] = None,
        at_wx_ids: Optional[List[str]] = None,
        disable_wx_ids: Optional[List[str]] = None,
        privacy: bool = False
    ) -> Dict[str, Any]:
        """Forward moment. Cannot be used within 1-3 days after login."""
        payload = {
            "appId": app_id,
            "snsXml": sns_xml,
            "privacy": privacy
        }
        if allow_wx_ids is not None:
            payload["allowWxIds"] = allow_wx_ids
        if at_wx_ids is not None:
            payload["atWxIds"] = at_wx_ids
        if disable_wx_ids is not None:
            payload["disableWxIds"] = disable_wx_ids
        return await self._request("POST", "/gewe/v2/api/sns/forwardSns", json_data=payload)

    async def get_own_sns_list(
        self: "_GeweClientProtocol",
        app_id: str,
        max_id: int = 0,
        decrypt: bool = True,
        first_page_md5: str = ""
    ) -> Dict[str, Any]:
        """Get own moments list."""
        payload = {
            "appId": app_id,
            "maxId": max_id,
            "decrypt": decrypt,
            "firstPageMd5": first_page_md5
        }
        return await self._request("POST", "/gewe/v2/api/sns/snsList", json_data=payload)

    async def get_contact_sns_list(
        self: "_GeweClientProtocol",
        app_id: str,
        wxid: str,
        max_id: int = 0,
        decrypt: bool = True,
        first_page_md5: str = ""
    ) -> Dict[str, Any]:
        """Get contact's moments list."""
        payload = {
            "appId": app_id,
            "wxid": wxid,
            "maxId": max_id,
            "decrypt": decrypt,
            "firstPageMd5": first_page_md5
        }
        return await self._request("POST", "/gewe/v2/api/sns/contactsSnsList", json_data=payload)

    async def get_sns_detail(
        self: "_GeweClientProtocol",
        app_id: str,
        sns_id: int
    ) -> Dict[str, Any]:
        """Get moment detail."""
        payload = {
            "appId": app_id,
            "snsId": sns_id
        }
        return await self._request("POST", "/gewe/v2/api/sns/snsDetails", json_data=payload)

    async def comment_sns(
        self: "_GeweClientProtocol",
        app_id: str,
        sns_id: int,
        oper_type: int,
        wxid: str,
        comment_id: str = "0",
        content: str = ""
    ) -> Dict[str, Any]:
        """
        Comment on or delete comment from moment.
        
        operType: 1=comment, 2=delete comment
        Cannot be used within 1-3 days after login.
        """
        payload = {
            "appId": app_id,
            "snsId": sns_id,
            "operType": oper_type,
            "wxid": wxid,
            "commentId": comment_id,
            "content": content
        }
        return await self._request("POST", "/gewe/v2/api/sns/commentSns", json_data=payload)
