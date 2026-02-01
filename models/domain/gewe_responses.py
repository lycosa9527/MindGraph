"""Gewe API Response Models.

Pydantic models for Gewe WeChat API responses based on official API documentation.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


class GeweBaseResponse(BaseModel):
    """Base response model for all Gewe API responses."""
    ret: int = Field(..., description="Return code (200 = success)")
    msg: str = Field(..., description="Response message")
    data: Optional[Union[Dict[str, Any], List[Any], str, int, bool]] = Field(
        None,
        description="Response data (can be dict, list, or primitive)"
    )


class GeweLoginQrCodeData(BaseModel):
    """Login QR code response data."""
    qr_img_base64: str = Field(..., alias="qrImgBase64", description="QR code image in base64")
    uuid: str = Field(..., description="UUID for checking login status")
    app_id: Optional[str] = Field(None, alias="appId", description="Device ID")


class GeweLoginQrCodeResponse(GeweBaseResponse):
    """Response model for get login QR code endpoint."""
    data: Optional[GeweLoginQrCodeData] = None


class GeweLoginStatusData(BaseModel):
    """Login status check response data."""
    status: int = Field(..., description="Login status (0: waiting, 1: scanning, 2: success)")
    app_id: Optional[str] = Field(None, alias="appId", description="Device ID")
    wxid: Optional[str] = Field(None, description="WeChat ID")
    login_info: Optional[Dict[str, Any]] = Field(None, alias="loginInfo", description="Login information")
    qr_img_base64: Optional[str] = Field(None, alias="qrImgBase64", description="Face recognition QR code (iPad)")


class GeweLoginStatusResponse(GeweBaseResponse):
    """Response model for check login endpoint."""
    data: Optional[GeweLoginStatusData] = None


class GeweMessageSendData(BaseModel):
    """Message send response data."""
    to_wxid: str = Field(..., alias="toWxid", description="Recipient wxid")
    create_time: Optional[int] = Field(None, alias="createTime", description="Message creation timestamp")
    msg_id: Optional[int] = Field(None, alias="msgId", description="Message ID")
    new_msg_id: Optional[int] = Field(None, alias="newMsgId", description="New message ID")
    msg_type: Optional[int] = Field(None, alias="type", description="Message type")
    aes_key: Optional[str] = Field(None, alias="aesKey", description="CDN AES key (for media)")
    file_id: Optional[str] = Field(None, alias="fileId", description="CDN file ID (for media)")
    length: Optional[int] = Field(None, description="File size (for media)")


class GeweMessageSendResponse(GeweBaseResponse):
    """Response model for send message endpoints."""
    data: Optional[GeweMessageSendData] = None


class GeweContactInfo(BaseModel):
    """Contact information model."""
    wxid: str = Field(..., description="Contact wxid")
    nickname: Optional[str] = Field(None, description="Nickname")
    remark: Optional[str] = Field(None, description="Remark name")
    avatar: Optional[str] = Field(None, description="Avatar URL")
    alias: Optional[str] = Field(None, description="WeChat alias")
    contact_type: Optional[str] = Field(None, alias="contactType", description="Type: friend, group, official")
    region: Optional[str] = Field(None, description="Region/location")
    v1: Optional[str] = Field(None, description="V1 field")
    v2: Optional[str] = Field(None, description="V2 field")
    v3: Optional[str] = Field(None, description="V3 field (wxid if already friend)")
    v4: Optional[str] = Field(None, description="V4 field")


class GeweContactListResponse(GeweBaseResponse):
    """Response model for get contacts list endpoint."""
    data: Optional[List[GeweContactInfo]] = None


class GeweContactInfoResponse(GeweBaseResponse):
    """Response model for get contact info endpoint."""
    data: Optional[Union[GeweContactInfo, List[GeweContactInfo]]] = None


class GeweCheckOnlineData(BaseModel):
    """Check online response data."""
    online: bool = Field(..., description="True if online, False if offline")


class GeweCheckOnlineResponse(GeweBaseResponse):
    """Response model for check online endpoint."""
    data: Optional[Union[bool, GeweCheckOnlineData]] = None


class GeweCallbackResponse(GeweBaseResponse):
    """Response model for set callback endpoint."""


class GeweLogoutResponse(GeweBaseResponse):
    """Response model for logout endpoint."""


class GeweReconnectionResponse(GeweBaseResponse):
    """Response model for reconnection endpoint."""


class GeweDialogLoginResponse(GeweBaseResponse):
    """Response model for dialog login endpoint."""


class GeweAccountLoginData(BaseModel):
    """Account login response data."""
    app_id: Optional[str] = Field(None, alias="appId", description="Device ID")
    qr_img_base64: Optional[str] = Field(None, alias="qrImgBase64", description="QR code image in base64")
    uuid: Optional[str] = Field(None, description="UUID for checking login status")


class GeweAccountLoginResponse(GeweBaseResponse):
    """Response model for account password login endpoint."""
    data: Optional[GeweAccountLoginData] = None


# Webhook message models
class GeweWebhookStringField(BaseModel):
    """String field wrapper in webhook messages."""
    string: str


class GeweWebhookImgBuf(BaseModel):
    """Image buffer in webhook messages."""
    i_len: int = Field(0, alias="iLen")
    buffer: Optional[str] = None


class GeweWebhookMessageData(BaseModel):
    """Webhook message data structure."""
    msg_id: Optional[int] = Field(None, alias="MsgId")
    from_user_name: Optional[GeweWebhookStringField] = Field(None, alias="FromUserName")
    to_user_name: Optional[GeweWebhookStringField] = Field(None, alias="ToUserName")
    msg_type: Optional[int] = Field(None, alias="MsgType")
    content: Optional[Union[GeweWebhookStringField, Dict[str, Any]]] = Field(None, alias="Content")
    status: Optional[int] = Field(None, alias="Status")
    img_status: Optional[int] = Field(None, alias="ImgStatus")
    img_buf: Optional[GeweWebhookImgBuf] = Field(None, alias="ImgBuf")
    create_time: Optional[int] = Field(None, alias="CreateTime")
    msg_source: Optional[str] = Field(None, alias="MsgSource")
    push_content: Optional[str] = Field(None, alias="PushContent")
    new_msg_id: Optional[int] = Field(None, alias="NewMsgId")
    msg_seq: Optional[int] = Field(None, alias="MsgSeq")
    nick_name: Optional[GeweWebhookStringField] = Field(None, alias="NickName")
    user_name: Optional[GeweWebhookStringField] = Field(None, alias="UserName")


class GeweWebhookMessage(BaseModel):
    """Webhook message structure from Gewe."""
    type_name: str = Field(..., alias="TypeName", description="Message type (AddMsg, ModContacts, etc.)")
    appid: str = Field(..., alias="Appid", description="Device ID")
    wxid: str = Field(..., alias="Wxid", description="WeChat ID")
    data: GeweWebhookMessageData = Field(..., alias="Data", description="Message data")
    token: Optional[str] = Field(None, description="Webhook token")
    test_msg: Optional[str] = Field(None, alias="testMsg", description="Test message")


# Group-related response models
class GeweGroupInfo(BaseModel):
    """Group information model."""
    wxid: str = Field(..., description="Group wxid")
    nickname: Optional[str] = Field(None, description="Group nickname")
    member_count: Optional[int] = Field(None, alias="memberCount", description="Member count")
    owner_wxid: Optional[str] = Field(None, alias="ownerWxid", description="Owner wxid")
    admin_list: Optional[List[str]] = Field(None, alias="adminList", description="Admin wxid list")
    announcement: Optional[str] = Field(None, description="Group announcement")


class GeweGroupListResponse(GeweBaseResponse):
    """Response model for get group list endpoint."""
    data: Optional[List[GeweGroupInfo]] = None


class GeweGroupInfoResponse(GeweBaseResponse):
    """Response model for get group info endpoint."""
    data: Optional[GeweGroupInfo] = None


class GeweGroupMemberInfo(BaseModel):
    """Group member information model."""
    wxid: str = Field(..., description="Member wxid")
    nickname: Optional[str] = Field(None, description="Nickname")
    display_name: Optional[str] = Field(None, alias="displayName", description="Display name in group")
    avatar: Optional[str] = Field(None, description="Avatar URL")
    inviter_wxid: Optional[str] = Field(None, alias="inviterWxid", description="Who invited this member")
    join_time: Optional[int] = Field(None, alias="joinTime", description="Join timestamp")


class GeweGroupMemberListResponse(GeweBaseResponse):
    """Response model for get group member list endpoint."""
    data: Optional[List[GeweGroupMemberInfo]] = None


# Generic response type for endpoints that return various data structures
GeweResponse = Union[
    GeweLoginQrCodeResponse,
    GeweLoginStatusResponse,
    GeweMessageSendResponse,
    GeweContactListResponse,
    GeweContactInfoResponse,
    GeweCheckOnlineResponse,
    GeweCallbackResponse,
    GeweLogoutResponse,
    GeweReconnectionResponse,
    GeweDialogLoginResponse,
    GeweAccountLoginResponse,
    GeweGroupListResponse,
    GeweGroupInfoResponse,
    GeweGroupMemberListResponse,
    GeweBaseResponse
]
