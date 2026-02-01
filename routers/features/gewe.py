"""Gewe WeChat Router.

API endpoints for Gewe WeChat integration with Dify AI responses (admin only).

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Optional
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
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


async def get_gewe_service(db: Session = Depends(get_db)) -> GeweService:
    """
    Dependency to get GeweService with automatic cleanup.
    
    Note: Cleanup happens automatically when the request completes.
    """
    return GeweService(db)


# =============================================================================
# Pydantic Models
# =============================================================================

class GeweLoginQrCodeRequest(BaseModel):
    """Request model for getting login QR code"""
    app_id: str = Field("", alias="appId", description="Device ID (empty string for first login, required field)")
    region_id: str = Field("320000", alias="regionId", description="Region ID (required)")
    device_type: str = Field("ipad", alias="deviceType", description="Device type: ipad (recommended) or mac (required)")
    proxy_ip: Optional[str] = Field(None, alias="proxyIp", description="Custom proxy IP (format: socks5://username:password@123.2.2.2:8932)")
    ttuid: Optional[str] = Field(None, alias="ttuid", description="Proxy ID download URL (must be used with regionId/proxyIp)")
    aid: Optional[str] = Field(None, alias="aid", description="Aid download URL (local computer proxy)")


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
    proxy_ip: Optional[str] = Field(None, alias="proxyIp", description="Proxy IP (format: socks5://username:password@123.2.2.2)")
    captch_code: Optional[str] = Field(None, alias="captchCode", description="Captcha code if phone prompts for verification code")


class GeweSetCallbackRequest(BaseModel):
    """Request model for setting callback URL"""
    callback_url: str = Field(..., alias="callbackUrl", description="Callback URL for receiving messages")


class GeweSendMessageRequest(BaseModel):
    """Request model for sending text message"""
    app_id: str = Field(..., alias="appId", description="Device ID (required)")
    to_wxid: str = Field(..., alias="toWxid", description="Recipient wxid (friend/group ID, required)")
    content: str = Field(..., min_length=1, description="Message content (required, must include @xxx when @mentioning in group)")
    ats: Optional[str] = Field(None, alias="ats", description="@ mentions (comma-separated wxids, or 'notify@all' for all members)")


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

@router.post("/login/qrcode")
async def get_gewe_login_qrcode(
    data: GeweLoginQrCodeRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get login QR code for WeChat (admin only).
    """
    service = GeweService(db)
    try:
        result = await service.get_login_qr_code(
            app_id=data.app_id or "",
            region_id=data.region_id,
            device_type=data.device_type,
            proxy_ip=data.proxy_ip,
            ttuid=data.ttuid,
            aid=data.aid
        )
        return result
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
        # Cleanup HTTP sessions
        await service.cleanup()


@router.post("/login/check")
async def check_gewe_login(
    data: GeweCheckLoginRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Check login status (admin only).
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
        return result
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
        # Cleanup HTTP sessions
        await service.cleanup()


@router.post("/callback/set")
async def set_gewe_callback(
    data: GeweSetCallbackRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Set callback URL for receiving messages (admin only).
    """
    service = GeweService(db)
    try:
        result = await service.set_callback(callback_url=data.callback_url)
        return result
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


@router.post("/message/send")
async def send_gewe_message(
    data: GeweSendMessageRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Send text message via WeChat (admin only).
    """
    service = GeweService(db)
    try:
        result = await service.send_text_message(
            app_id=data.app_id,
            to_wxid=data.to_wxid,
            content=data.content,
            ats=data.ats
        )
        return result
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


@router.post("/contacts/list")
async def get_gewe_contacts(
    data: GeweGetContactsRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get contacts list (admin only).
    """
    service = GeweService(db)
    try:
        result = await service.get_contacts_list(app_id=data.app_id)
        return result
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


@router.post("/contacts/info")
async def get_gewe_contacts_info(
    data: GeweGetContactsInfoRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get contacts info (admin only).
    """
    service = GeweService(db)
    try:
        result = await service.get_contacts_info(
            app_id=data.app_id,
            wxids=data.wxids
        )
        return result
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
    try:
        service = GeweService(db)
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
    
    # Mask token for display (show first 4 and last 4 characters)
    masked_token = ''
    if token:
        if len(token) <= 8:
            masked_token = '*' * len(token)
        else:
            masked_token = f"{token[:4]}...{token[-4:]}"
    
    # Get app_id from saved login info if available
    app_id = None
    app_id_masked = ''
    try:
        service = GeweService(db)
        login_info = service.get_saved_login_info()
        if login_info and login_info.get('app_id'):
            app_id = login_info.get('app_id')
            # Mask app_id for display (show first 4 and last 4 characters)
            if len(app_id) <= 8:
                app_id_masked = '*' * len(app_id)
            else:
                app_id_masked = f"{app_id[:4]}...{app_id[-4:]}"
    except Exception:
        pass  # Ignore errors when getting login info
    
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
    try:
        service = GeweService(db)
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


@router.get("/preferences")
async def get_gewe_preferences(
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get user preferences (region_id and device_type) (admin only).
    """
    try:
        service = GeweService(db)
        preferences = service.get_preferences()
        return preferences
    except Exception as e:
        logger.error("Error getting preferences: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get preferences"
        ) from e


@router.post("/webhook")
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
    """
    service = GeweService(db)
    try:
        message_data = await request.json()
        logger.debug("Received Gewe webhook: %s", message_data)

        # Process message and get Dify response
        response_text, to_wxid = await service.process_incoming_message(message_data)

        # If we have a response, send it back via WeChat
        if response_text and to_wxid:
            app_id = message_data.get('Appid', '')
            if app_id:
                try:
                    await service.send_text_message(
                        app_id=app_id,
                        to_wxid=to_wxid,
                        content=response_text
                    )
                    logger.info("Sent Dify response to %s", to_wxid)
                except Exception as e:
                    logger.error("Error sending response message: %s", e, exc_info=True)

        return {"status": "ok"}

    except Exception as e:
        logger.error("Error processing Gewe webhook: %s", e, exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        await service.cleanup()
