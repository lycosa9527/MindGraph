"""SNS (Moments) Service Module.

Handles moments/SNS-related service operations.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, Any, List, Optional

from services.gewe.protocols import GeweServiceBase


class SNSServiceMixin(GeweServiceBase):
    """Mixin for SNS/moments-related service methods"""

    async def like_sns(
        self,
        app_id: str,
        sns_id: int,
        oper_type: int,
        wxid: str
    ) -> Dict[str, Any]:
        """Like or unlike a moment."""
        client = self._get_gewe_client()
        return await client.like_sns(
            app_id=app_id,
            sns_id=sns_id,
            oper_type=oper_type,
            wxid=wxid
        )

    async def delete_sns(
        self,
        app_id: str,
        sns_id: int
    ) -> Dict[str, Any]:
        """Delete a moment."""
        client = self._get_gewe_client()
        return await client.delete_sns(
            app_id=app_id,
            sns_id=sns_id
        )

    async def set_sns_visibility(
        self,
        app_id: str,
        option: int
    ) -> Dict[str, Any]:
        """Set moment visibility range."""
        client = self._get_gewe_client()
        return await client.set_sns_visibility(
            app_id=app_id,
            option=option
        )

    async def set_allow_stranger_view_sns(
        self,
        app_id: str,
        enabled: bool
    ) -> Dict[str, Any]:
        """Set whether strangers can view moments."""
        client = self._get_gewe_client()
        return await client.set_allow_stranger_view_sns(
            app_id=app_id,
            enabled=enabled
        )

    async def set_sns_privacy(
        self,
        app_id: str,
        sns_id: int,
        is_open: bool
    ) -> Dict[str, Any]:
        """Set moment as private or public."""
        client = self._get_gewe_client()
        return await client.set_sns_privacy(
            app_id=app_id,
            sns_id=sns_id,
            is_open=is_open
        )

    async def download_sns_video(
        self,
        app_id: str,
        sns_xml: str
    ) -> Dict[str, Any]:
        """Download moment video."""
        client = self._get_gewe_client()
        return await client.download_sns_video(
            app_id=app_id,
            sns_xml=sns_xml
        )

    async def send_text_sns(
        self,
        app_id: str,
        content: str,
        allow_wx_ids: Optional[List[str]] = None,
        at_wx_ids: Optional[List[str]] = None,
        disable_wx_ids: Optional[List[str]] = None,
        privacy: bool = False,
        allow_tag_ids: Optional[List[str]] = None,
        disable_tag_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Send text moment."""
        client = self._get_gewe_client()
        return await client.send_text_sns(
            app_id=app_id,
            content=content,
            allow_wx_ids=allow_wx_ids,
            at_wx_ids=at_wx_ids,
            disable_wx_ids=disable_wx_ids,
            privacy=privacy,
            allow_tag_ids=allow_tag_ids,
            disable_tag_ids=disable_tag_ids
        )

    async def send_image_sns(
        self,
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
        """Send image moment."""
        client = self._get_gewe_client()
        return await client.send_image_sns(
            app_id=app_id,
            img_infos=img_infos,
            content=content,
            allow_wx_ids=allow_wx_ids,
            at_wx_ids=at_wx_ids,
            disable_wx_ids=disable_wx_ids,
            privacy=privacy,
            allow_tag_ids=allow_tag_ids,
            disable_tag_ids=disable_tag_ids
        )

    async def send_video_sns(
        self,
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
        """Send video moment."""
        client = self._get_gewe_client()
        return await client.send_video_sns(
            app_id=app_id,
            video_info=video_info,
            content=content,
            allow_wx_ids=allow_wx_ids,
            at_wx_ids=at_wx_ids,
            disable_wx_ids=disable_wx_ids,
            privacy=privacy,
            allow_tag_ids=allow_tag_ids,
            disable_tag_ids=disable_tag_ids
        )

    async def send_link_sns(
        self,
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
        """Send link moment."""
        client = self._get_gewe_client()
        return await client.send_link_sns(
            app_id=app_id,
            link_url=link_url,
            title=title,
            description=description,
            thumb_url=thumb_url,
            content=content,
            allow_wx_ids=allow_wx_ids,
            at_wx_ids=at_wx_ids,
            disable_wx_ids=disable_wx_ids,
            privacy=privacy,
            allow_tag_ids=allow_tag_ids,
            disable_tag_ids=disable_tag_ids
        )

    async def upload_sns_image(
        self,
        app_id: str,
        img_urls: List[str]
    ) -> Dict[str, Any]:
        """Upload images for moment."""
        client = self._get_gewe_client()
        return await client.upload_sns_image(
            app_id=app_id,
            img_urls=img_urls
        )

    async def upload_sns_video(
        self,
        app_id: str,
        video_url: str,
        thumb_url: str
    ) -> Dict[str, Any]:
        """Upload video for moment."""
        client = self._get_gewe_client()
        return await client.upload_sns_video(
            app_id=app_id,
            video_url=video_url,
            thumb_url=thumb_url
        )

    async def forward_sns(
        self,
        app_id: str,
        sns_xml: str,
        allow_wx_ids: Optional[List[str]] = None,
        at_wx_ids: Optional[List[str]] = None,
        disable_wx_ids: Optional[List[str]] = None,
        privacy: bool = False
    ) -> Dict[str, Any]:
        """Forward moment."""
        client = self._get_gewe_client()
        return await client.forward_sns(
            app_id=app_id,
            sns_xml=sns_xml,
            allow_wx_ids=allow_wx_ids,
            at_wx_ids=at_wx_ids,
            disable_wx_ids=disable_wx_ids,
            privacy=privacy
        )

    async def get_own_sns_list(
        self,
        app_id: str,
        max_id: int = 0,
        decrypt: bool = True,
        first_page_md5: str = ""
    ) -> Dict[str, Any]:
        """Get own moments list."""
        client = self._get_gewe_client()
        return await client.get_own_sns_list(
            app_id=app_id,
            max_id=max_id,
            decrypt=decrypt,
            first_page_md5=first_page_md5
        )

    async def get_contact_sns_list(
        self,
        app_id: str,
        wxid: str,
        max_id: int = 0,
        decrypt: bool = True,
        first_page_md5: str = ""
    ) -> Dict[str, Any]:
        """Get contact's moments list."""
        client = self._get_gewe_client()
        return await client.get_contact_sns_list(
            app_id=app_id,
            wxid=wxid,
            max_id=max_id,
            decrypt=decrypt,
            first_page_md5=first_page_md5
        )

    async def get_sns_detail(
        self,
        app_id: str,
        sns_id: int
    ) -> Dict[str, Any]:
        """Get moment detail."""
        client = self._get_gewe_client()
        return await client.get_sns_detail(
            app_id=app_id,
            sns_id=sns_id
        )

    async def comment_sns(
        self,
        app_id: str,
        sns_id: int,
        oper_type: int,
        wxid: str,
        comment_id: str = "0",
        content: str = ""
    ) -> Dict[str, Any]:
        """Comment on or delete comment from moment."""
        client = self._get_gewe_client()
        return await client.comment_sns(
            app_id=app_id,
            sns_id=sns_id,
            oper_type=oper_type,
            wxid=wxid,
            comment_id=comment_id,
            content=content
        )
