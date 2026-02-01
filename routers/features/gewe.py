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
from services.gewe import GeweService
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter
from utils.auth import get_current_user
from utils.auth.roles import is_admin


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gewe", tags=["Gewe WeChat"])

# Rate limiter for webhook endpoint
_webhook_rate_limiter = RedisRateLimiter()


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
        if login_info:
            app_id_value = login_info.get('app_id')
            if app_id_value:
                app_id = app_id_value
                # Mask app_id for display (show first 4 and last 4 characters)
                if len(app_id_value) <= 8:
                    app_id_masked = '*' * len(app_id_value)
                else:
                    app_id_masked = f"{app_id_value[:4]}...{app_id_value[-4:]}"
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

    Security: Verifies token from header or body matches GEWE_TOKEN.
    Also verifies request comes from api.geweapi.com domain.
    """
    # Get request metadata for security verification and logging
    client_ip = request.client.host if request.client else "unknown"
    host_header = request.headers.get('Host', '')
    referer_header = request.headers.get('Referer', '')
    user_agent = request.headers.get('User-Agent', '')

    # Collect all headers for analysis
    all_headers = dict(request.headers)

    # Check for signature header (if Gewe supports HMAC signatures)
    signature_header = (
        request.headers.get('X-GEWE-SIGNATURE') or
        request.headers.get('X-Signature') or
        request.headers.get('X-Webhook-Signature')
    )
    if signature_header:
        logger.info(
            "🔐 Signature header detected: %s (first 30 chars)",
            signature_header[:30]
        )

    # Check for token in headers
    token_in_header = (
        request.headers.get('X-GEWE-TOKEN') or
        request.headers.get('Authorization') or
        request.headers.get('X-Auth-Token')
    )
    if token_in_header:
        header_name = (
            'X-GEWE-TOKEN' if request.headers.get('X-GEWE-TOKEN')
            else 'Authorization' if request.headers.get('Authorization')
            else 'X-Auth-Token'
        )
        logger.info("🔑 Token found in header: %s", header_name)

    # Log request info for debugging (in dev mode)
    logger.info(
        "📥 Gewe webhook request - IP: %s, Host: %s, Referer: %s, User-Agent: %s",
        client_ip, host_header, referer_header, user_agent
    )

    # Log ALL headers for analysis (to understand what Gewe sends)
    logger.info("📋 All request headers: %s", all_headers)

    # 1. IP Whitelisting (Priority 1: Critical)
    allowed_ips_str = os.getenv('GEWE_WEBHOOK_ALLOWED_IPS', '').strip()
    if allowed_ips_str:
        allowed_ips = [ip.strip() for ip in allowed_ips_str.split(',') if ip.strip()]
        if allowed_ips and client_ip not in allowed_ips:
            logger.warning("Webhook access denied from IP: %s (not in whitelist: %s)", client_ip, allowed_ips)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden"
            )
        logger.debug("IP %s verified against whitelist", client_ip)
    else:
        logger.debug("IP whitelist not configured - allowing all IPs (dev mode)")

    # 2. Rate Limiting (Priority 1: Critical)
    # Limit: 100 requests per minute per IP (as recommended in security doc)
    is_allowed, count, error_msg = _webhook_rate_limiter.check_and_record(
        category="gewe_webhook",
        identifier=client_ip,
        max_attempts=100,
        window_seconds=60
    )
    if not is_allowed:
        logger.warning(
            "Webhook rate limit exceeded from IP: %s, count: %s, error: %s",
            client_ip, count, error_msg
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {error_msg}"
        )
    logger.debug("Rate limit check passed for IP %s (count: %s/100 per minute)", client_ip, count)

    # Parse request body once
    try:
        message_data = await request.json()
    except (ValueError, json.JSONDecodeError) as e:
        logger.error("Failed to parse webhook JSON from IP %s: %s", client_ip, e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        ) from e

    # Log complete payload structure for analysis (to understand Gewe webhook format)
    logger.info("📦 Webhook payload structure:")
    logger.info("   - Top-level keys: %s", list(message_data.keys()))

    # Log payload details based on expected structure
    if 'TypeName' in message_data:
        logger.info("   - TypeName: %s", message_data.get('TypeName'))
    if 'Appid' in message_data:
        logger.info("   - Appid: %s", message_data.get('Appid'))
    if 'Wxid' in message_data:
        logger.info("   - Wxid: %s", message_data.get('Wxid'))
    if 'token' in message_data:
        token_value = message_data.get('token')
        token_str = str(token_value)
        token_display = (
            token_str[:20] + "..."
            if len(token_str) > 20
            else token_str
        )
        logger.info("   - token: %s (present)", token_display)
    if 'testMsg' in message_data:
        logger.info("   - testMsg: %s", message_data.get('testMsg'))
    if 'Data' in message_data:
        data = message_data.get('Data', {})
        logger.info("   - Data keys: %s", list(data.keys()) if isinstance(data, dict) else "Not a dict")
        if isinstance(data, dict):
            if 'MsgType' in data:
                logger.info("   - Data.MsgType: %s", data.get('MsgType'))
            if 'FromUserName' in data:
                logger.info("   - Data.FromUserName: %s", data.get('FromUserName'))
            if 'ToUserName' in data:
                logger.info("   - Data.ToUserName: %s", data.get('ToUserName'))

    # Log full payload (truncated if too large)
    payload_str = json.dumps(message_data, ensure_ascii=False, indent=2)
    if len(payload_str) > 2000:
        logger.info(
            "📄 Full payload (truncated):\n%s\n... (truncated, total length: %d chars)",
            payload_str[:2000], len(payload_str)
        )
    else:
        logger.info("📄 Full payload:\n%s", payload_str)

    # Domain verification: Check if request appears to come from Gewe API
    gewe_base_url = os.getenv('GEWE_BASE_URL', 'http://api.geweapi.com').strip()
    # Extract domain from base URL (handle http://api.geweapi.com or https://api.geweapi.com)
    gewe_domain = gewe_base_url.replace('http://', '').replace('https://', '').split('/')[0]

    domain_valid = False
    # Check Referer header (most reliable for webhook verification)
    if referer_header:
        if gewe_domain in referer_header:
            domain_valid = True
            logger.debug("Domain verified via Referer: %s", referer_header)

    # If Referer check failed, log warning but don't block (for dev/testing)
    if not domain_valid:
        logger.warning(
            "Webhook request domain verification failed - IP: %s, Host: %s, Referer: %s. "
            "Expected domain: %s. Allowing for dev/testing.",
            client_ip, host_header, referer_header, gewe_domain
        )

    # Token verification for webhook security
    expected_token = os.getenv('GEWE_TOKEN', '').strip()
    if expected_token:
        token_valid = False
        token_source = None

        # Check token in header first (common pattern)
        header_token = request.headers.get('X-GEWE-TOKEN') or request.headers.get('Authorization')
        if header_token:
            # Remove 'Bearer ' prefix if present
            if header_token.startswith('Bearer '):
                header_token = header_token[7:]
            if header_token == expected_token:
                token_valid = True
                token_source = "header"
                logger.debug("Token verified from header")

        # If header token not found or invalid, check body token (Gewe sends token in JSON)
        if not token_valid:
            body_token = message_data.get('token', '')
            if body_token == expected_token:
                token_valid = True
                token_source = "body"
                logger.debug("Token verified from body")

        if not token_valid:
            logger.warning(
                "Invalid webhook token from IP: %s, Host: %s. "
                "Header token present: %s, Body token present: %s",
                client_ip, host_header,
                bool(header_token), bool(message_data.get('token'))
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        else:
            logger.debug("Token verified successfully from %s", token_source)
    else:
        logger.warning("GEWE_TOKEN not configured - webhook is unprotected!")

    # 4. Request Payload Validation (Priority 2: Important)
    # Validate that payload has expected structure for Gewe messages
    # Test messages may have different structure, so we allow testMsg
    if 'testMsg' in message_data:
        logger.info("Received test message from Gewe: %s", message_data.get('testMsg'))
        # Test messages are OK, just return success
        return {"status": "ok", "message": "Test message received"}

    # For real messages, validate required fields
    if not message_data.get('Appid') and not message_data.get('Wxid'):
        logger.warning("Invalid webhook payload - missing Appid/Wxid: %s", message_data)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload: missing Appid or Wxid"
        )

    service = GeweService(db)
    try:
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
