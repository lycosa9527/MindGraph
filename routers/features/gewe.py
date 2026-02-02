"""Gewe WeChat Router.

API endpoints for Gewe WeChat integration with Dify AI responses (admin only).

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Optional
import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from models.domain.gewe_responses import (
    GeweLoginQrCodeResponse,
    GeweLoginStatusResponse,
    GeweMessageSendResponse,
    GeweContactListResponse,
    GeweContactInfoResponse,
    GeweCallbackResponse
)
from clients.gewe.base import GeweAPIError
from services.gewe import GeweService
from utils.auth import get_current_user
from utils.auth.roles import is_admin


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gewe", tags=["Gewe WeChat"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin access."""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# =============================================================================
# Helper Functions
# =============================================================================

def _extract_client_ip(request: Request) -> str:
    """Extract client IP from request, handling reverse proxy scenarios."""
    return (
        request.headers.get('X-Real-IP') or
        request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or
        (request.client.host if request.client else None) or
        "unknown"
    )


def _verify_webhook_token(request: Request, message_data: dict, client_ip: str) -> str:
    """
    Verify webhook token from header or body.
    
    Returns:
        Token source ("header" or "body")
    
    Raises:
        HTTPException: If token verification fails
    """
    expected_token = os.getenv('GEWE_TOKEN', '').strip()
    if not expected_token:
        logger.error(
            "GEWE_TOKEN not configured - webhook token verification is mandatory. "
            "Rejecting request from IP: %s",
            client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook token verification not configured"
        )

    # Check token in header first
    header_token = request.headers.get('X-GEWE-TOKEN') or request.headers.get('Authorization')
    if header_token:
        if header_token.startswith('Bearer '):
            header_token = header_token[7:]
        if header_token == expected_token:
            logger.debug("Token verified from header")
            return "header"

    # Check token in body (Gewe sends token in JSON)
    body_token = message_data.get('token', '')
    if body_token == expected_token:
        logger.debug("Token verified from body")
        return "body"

    # Token verification failed
    logger.warning(
        "Invalid webhook token from IP: %s. "
        "Header token present: %s, Body token present: %s",
        client_ip,
        bool(header_token), bool(body_token)
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token"
    )


# =============================================================================
# Pydantic Models
# =============================================================================

class GeweLoginQrCodeRequest(BaseModel):
    """Request model for getting login QR code"""
    app_id: str = Field(
        "",
        alias="appId",
        description="Device ID (empty string for first login, required field)"
    )
    region_id: str = Field("320000", alias="regionId", description="Region ID (required)")
    device_type: str = Field(
        "ipad",
        alias="deviceType",
        description="Device type: ipad (recommended) or mac (required)"
    )
    proxy_ip: Optional[str] = Field(
        None,
        alias="proxyIp",
        description="Custom proxy IP (format: socks5://username:password@123.2.2.2:8932)"
    )
    ttuid: Optional[str] = Field(
        None,
        alias="ttuid",
        description="Proxy ID download URL (must be used with regionId/proxyIp)"
    )
    aid: Optional[str] = Field(
        None,
        alias="aid",
        description="Aid download URL (local computer proxy)"
    )


class GeweCheckLoginRequest(BaseModel):
    """Request model for checking login status"""
    app_id: str = Field(..., alias="appId", description="Device ID (required)")
    uuid: str = Field(..., description="UUID from QR code response (required)")
    auto_sliding: bool = Field(
        False,
        alias="autoSliding",
        description=(
            "Auto sliding verification (optional). "
            "For iPad login: MUST be False (generates face recognition QR code). "
            "For Mac login: True (auto, ~90% success) or False (manual slider app). "
            "When using ttuid (network method 3): MUST be False."
        )
    )
    proxy_ip: Optional[str] = Field(
        None,
        alias="proxyIp",
        description="Proxy IP (format: socks5://username:password@123.2.2.2)"
    )
    captch_code: Optional[str] = Field(
        None,
        alias="captchCode",
        description="Captcha code if phone prompts for verification code"
    )


class GeweSetCallbackRequest(BaseModel):
    """Request model for setting callback URL"""
    callback_url: str = Field(..., alias="callbackUrl", description="Callback URL for receiving messages")


class GeweSendMessageRequest(BaseModel):
    """Request model for sending text message"""
    app_id: str = Field(..., alias="appId", description="Device ID (required)")
    to_wxid: str = Field(
        ...,
        alias="toWxid",
        description="Recipient wxid (friend/group ID, required)"
    )
    content: str = Field(
        ...,
        min_length=1,
        description=(
            "Message content (required, must include @xxx when @mentioning in group)"
        )
    )
    ats: Optional[str] = Field(
        None,
        alias="ats",
        description="@ mentions (comma-separated wxids, or 'notify@all' for all members)"
    )


class GeweGetContactsRequest(BaseModel):
    """Request model for getting contacts"""
    app_id: str = Field(..., alias="appId", description="Device ID")


class GeweGetContactsInfoRequest(BaseModel):
    """Request model for getting contacts info"""
    app_id: str = Field(..., alias="appId", description="Device ID")
    wxids: List[str] = Field(..., description="List of wxids to get info for")


class GeweSavePreferencesRequest(BaseModel):
    """Request model for saving user preferences"""
    region_id: str = Field(..., alias="regionId", description="Region ID")
    device_type: str = Field(..., alias="deviceType", description="Device type: ipad or mac")


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/login/qrcode", response_model=GeweLoginQrCodeResponse)
async def get_gewe_login_qrcode(
    data: GeweLoginQrCodeRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get login QR code for WeChat (admin only).
    
    If the provided app_id doesn't exist on Gewe's side, automatically retries
    with empty app_id to create a new device.
    
    Returns:
        Response containing QR code image (base64) and UUID for login checking.
    """
    service = GeweService(db)
    app_id = data.app_id or ""

    try:
        # Try with provided app_id first
        result = await service.get_login_qr_code(
            app_id=app_id,
            region_id=data.region_id,
            device_type=data.device_type,
            proxy_ip=data.proxy_ip,
            ttuid=data.ttuid,
            aid=data.aid
        )
        return GeweLoginQrCodeResponse(**result)
    except GeweAPIError as e:
        # Check if error indicates device doesn't exist
        error_msg = str(e.message).lower()
        # Also check response_data for detailed error message
        detailed_msg = ""
        if e.response_data:
            data = e.response_data.get('data', {})
            if isinstance(data, dict):
                detailed_msg = str(data.get('msg', '')).lower()

        is_device_not_found = (
            "设备不存在" in error_msg or
            "device does not exist" in error_msg or
            "设备不存在" in detailed_msg or
            "设备不存在" in str(e).lower()
        )

        # If device doesn't exist and we had an app_id, retry with empty app_id
        if is_device_not_found and app_id:
            logger.info(
                "Device %s not found on Gewe, retrying with empty app_id to create new device",
                app_id
            )
            try:
                # Clear saved login info since device doesn't exist
                service.reset_device_id()

                # Retry with empty app_id
                result = await service.get_login_qr_code(
                    app_id="",
                    region_id=data.region_id,
                    device_type=data.device_type,
                    proxy_ip=data.proxy_ip,
                    ttuid=data.ttuid,
                    aid=data.aid
                )
                logger.info("Successfully created new device with empty app_id")
                return GeweLoginQrCodeResponse(**result)
            except Exception as retry_error:
                logger.error("Error retrying with empty app_id: %s", retry_error, exc_info=True)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create new device: {str(retry_error)}"
                ) from retry_error
        else:
            # Re-raise the original error
            logger.error("Gewe API error: %s", e, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e.message) or "Failed to get login QR code"
            ) from e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error("Error getting login QR code: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get login QR code"
        ) from e
    finally:
        await service.cleanup()


@router.post("/login/check", response_model=GeweLoginStatusResponse)
async def check_gewe_login(
    data: GeweCheckLoginRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Check login status (admin only).
    
    Poll this endpoint every 5 seconds after getting QR code.
    Status: 0=waiting, 1=scanning, 2=success.
    """
    service = GeweService(db)
    try:
        result = await service.check_login(
            app_id=data.app_id,
            uuid=data.uuid,
            auto_sliding=data.auto_sliding,
            proxy_ip=data.proxy_ip,
            captch_code=data.captch_code
        )
        return GeweLoginStatusResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error("Error checking login: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check login status"
        ) from e
    finally:
        await service.cleanup()


@router.post("/callback/set", response_model=GeweCallbackResponse)
async def set_gewe_callback(
    data: GeweSetCallbackRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Set callback URL for receiving messages (admin only).
    
    The callback URL will receive POST requests with JSON payloads
    containing incoming WeChat messages.
    """
    service = GeweService(db)
    try:
        result = await service.set_callback(callback_url=data.callback_url)
        return GeweCallbackResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error("Error setting callback: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to set callback URL"
        ) from e
    finally:
        await service.cleanup()


@router.post("/message/send", response_model=GeweMessageSendResponse)
async def send_gewe_message(
    data: GeweSendMessageRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Send text message via WeChat (admin only).
    
    Note: When @mentioning in group chats, include @xxx in content.
    """
    service = GeweService(db)
    try:
        result = await service.send_text_message(
            app_id=data.app_id,
            to_wxid=data.to_wxid,
            content=data.content,
            ats=data.ats
        )
        return GeweMessageSendResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error("Error sending message: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send message"
        ) from e
    finally:
        await service.cleanup()


@router.post("/contacts/list", response_model=GeweContactListResponse)
async def get_gewe_contacts(
    data: GeweGetContactsRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get contacts list (admin only).
    
    Note: This is a long-running operation. Time increases with contact count.
    If timeout occurs, use the cached contacts endpoint.
    """
    service = GeweService(db)
    try:
        result = await service.get_contacts_list(app_id=data.app_id)
        return GeweContactListResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error("Error getting contacts: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get contacts list"
        ) from e
    finally:
        await service.cleanup()


@router.post("/contacts/info", response_model=GeweContactInfoResponse)
async def get_gewe_contacts_info(
    data: GeweGetContactsInfoRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get contacts info (admin only).
    
    Returns detailed information for specified contacts (friends/groups).
    """
    service = GeweService(db)
    try:
        result = await service.get_contacts_info(
            app_id=data.app_id,
            wxids=data.wxids
        )
        return GeweContactInfoResponse(**result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error("Error getting contacts info: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get contacts info"
        ) from e
    finally:
        await service.cleanup()


@router.get("/login/info")
async def get_gewe_login_info(
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get saved login info (app_id and wxid) (admin only).
    """
    service = GeweService(db)
    try:
        login_info = service.get_saved_login_info()
        if login_info:
            return login_info
        return {"app_id": None, "wxid": None}
    except Exception as e:
        logger.error("Error getting login info: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get login info"
        ) from e
    finally:
        await service.cleanup()


@router.get("/config/status")
async def get_gewe_config_status(
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get Gewe configuration status (admin only).
    Returns token status and masked token value.
    """
    token = os.getenv('GEWE_TOKEN', '').strip()
    base_url = os.getenv('GEWE_BASE_URL', 'http://api.geweapi.com').strip()

    # Mask token for display
    masked_token = ''
    if token:
        masked_token = '*' * len(token) if len(token) <= 8 else f"{token[:4]}...{token[-4:]}"

    # Get app_id from saved login info if available
    app_id = None
    app_id_masked = ''
    service = GeweService(db)
    try:
        login_info = service.get_saved_login_info()
        if login_info:
            app_id_value = login_info.get('app_id')
            if app_id_value:
                app_id = app_id_value
                app_id_masked = (
                    '*' * len(app_id_value) if len(app_id_value) <= 8
                    else f"{app_id_value[:4]}...{app_id_value[-4:]}"
                )
    except Exception:
        pass  # Ignore errors when getting login info
    finally:
        await service.cleanup()

    return {
        "token_configured": bool(token),
        "token_masked": masked_token,
        "base_url": base_url,
        "app_id": app_id,
        "app_id_masked": app_id_masked
    }


@router.post("/preferences/save")
async def save_gewe_preferences(
    data: GeweSavePreferencesRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Save user preferences (region_id and device_type) (admin only).
    """
    service = GeweService(db)
    try:
        service.save_preferences(
            region_id=data.region_id,
            device_type=data.device_type
        )
        return {"status": "success", "message": "Preferences saved successfully"}
    except Exception as e:
        logger.error("Error saving preferences: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save preferences"
        ) from e
    finally:
        await service.cleanup()


@router.get("/preferences")
async def get_gewe_preferences(
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get user preferences (region_id and device_type) (admin only).
    """
    service = GeweService(db)
    try:
        preferences = service.get_preferences()
        return preferences
    except Exception as e:
        logger.error("Error getting preferences: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get preferences"
        ) from e
    finally:
        await service.cleanup()


@router.post("/device/reset")
async def reset_gewe_device_id(
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Reset device ID by clearing saved login info (admin only).
    This will allow creating a new device on next login.
    """
    service = GeweService(db)
    try:
        service.reset_device_id()
        return {"status": "success", "message": "Device ID reset successfully"}
    except Exception as e:
        logger.error("Error resetting device ID: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset device ID"
        ) from e
    finally:
        await service.cleanup()


@router.post("/webhook", response_model=dict)
async def gewe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint to receive messages from Gewe.

    This endpoint receives POST requests from Gewe with message data.
    It processes incoming messages and generates Dify responses.

    For group chats, only responds when bot is @mentioned.
    For private chats, responds to all messages.

    Security: Token verification is mandatory - verifies token from header or body matches GEWE_TOKEN.
    
    Request body follows GeweWebhookMessage structure.
    """
    # Extract client IP for logging
    client_ip = _extract_client_ip(request)

    # Parse request body
    try:
        message_data = await request.json()
    except (ValueError, json.JSONDecodeError) as e:
        logger.error("Failed to parse webhook JSON from IP %s: %s", client_ip, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        ) from e

    # Log full payload for debugging Gewe's feedback
    payload_str = json.dumps(message_data, ensure_ascii=False, indent=2)
    if len(payload_str) > 2000:
        logger.info(
            "📄 Full payload (truncated):\n%s\n... (truncated, total length: %d chars)",
            payload_str[:2000], len(payload_str)
        )
    else:
        logger.info("📄 Full payload:\n%s", payload_str)

    # Token verification (mandatory)
    token_source = _verify_webhook_token(request, message_data, client_ip)
    logger.info("✅ [Security] Token verified successfully from %s", token_source)

    # Handle test messages
    if 'testMsg' in message_data:
        logger.info("🧪 [Webhook] Received test message from Gewe: %s", message_data.get('testMsg'))
        return {"status": "ok", "message": "Test message received"}

    # Validate required fields for real messages
    if not message_data.get('Appid') and not message_data.get('Wxid'):
        logger.warning("Invalid webhook payload - missing Appid/Wxid: %s", message_data)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload: missing Appid or Wxid"
        )

    # Process webhook message
    service = GeweService(db)
    try:
        logger.info("🔄 [Webhook] Processing Gewe webhook message")

        # Process message and get Dify response
        (
            response_text,
            image_urls,
            to_wxid,
            sender_wxid,
            quoted_message
        ) = await service.process_incoming_message(message_data)
        logger.info(
            "💬 [Webhook] Message processing result - Response length: %d, Images: %d, To: %s, Quoted: %s",
            len(response_text) if response_text else 0,
            len(image_urls),
            to_wxid,
            "Yes" if quoted_message else "No"
        )

        # Send response back via WeChat if available
        if to_wxid:
            app_id = message_data.get('Appid', '')
            if app_id:
                try:
                    # Check if this is a group chat reply
                    is_group = '@chatroom' in to_wxid

                    # Prepare @ mention if replying to group chat
                    ats_param = None
                    if is_group and sender_wxid:
                        ats_param = sender_wxid

                    # Send text if available
                    if response_text:
                        logger.info(
                            "📤 [Webhook] Sending text response - App ID: %s, To: %s, Length: %d, @: %s",
                            app_id, to_wxid, len(response_text), ats_param
                        )
                        await service.send_text_message(
                            app_id=app_id,
                            to_wxid=to_wxid,
                            content=response_text,
                            ats=ats_param
                        )
                        logger.info("✅ [Webhook] Successfully sent text response to %s", to_wxid)

                    # Send images if available
                    if image_urls:
                        logger.info(
                            "🖼️ [Webhook] Sending %d images - App ID: %s, To: %s",
                            len(image_urls), app_id, to_wxid
                        )
                        await service.download_and_send_images(
                            app_id=app_id,
                            to_wxid=to_wxid,
                            image_urls=image_urls
                        )
                        logger.info("✅ [Webhook] Successfully sent images to %s", to_wxid)
                except Exception as e:
                    logger.error("❌ [Webhook] Error sending response: %s", e, exc_info=True)
                    return {"status": "error", "message": f"Failed to send response: {str(e)}"}
            else:
                logger.warning("⚠️ [Webhook] Cannot send response - App ID missing")

        return {"status": "ok"}

    except Exception as e:
        logger.error("❌ [Webhook] Error processing webhook: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        await service.cleanup()
