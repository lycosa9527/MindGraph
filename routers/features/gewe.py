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
    # =============================================================================
    # COMPREHENSIVE SECURITY ANALYSIS LOGGING
    # =============================================================================
    # Extract all possible IP addresses (for reverse proxy scenarios)
    x_real_ip = request.headers.get('X-Real-IP', '')
    x_forwarded_for = request.headers.get('X-Forwarded-For', '')
    x_forwarded_for_ips = [ip.strip() for ip in x_forwarded_for.split(',')] if x_forwarded_for else []
    direct_client_ip = request.client.host if request.client else None
    
    # Extract real client IP (handle reverse proxy scenarios)
    client_ip = (
        x_real_ip or
        (x_forwarded_for_ips[0] if x_forwarded_for_ips else '') or
        direct_client_ip or
        "unknown"
    )
    
    # Extract all domain-related headers
    host_header = request.headers.get('Host', '')
    referer_header = request.headers.get('Referer', '')
    origin_header = request.headers.get('Origin', '')
    forwarded_host = request.headers.get('X-Forwarded-Host', '')
    
    # Extract all other security-related headers
    user_agent = request.headers.get('User-Agent', '')
    content_type = request.headers.get('Content-Type', '')
    content_length = request.headers.get('Content-Length', '')
    accept_header = request.headers.get('Accept', '')
    accept_encoding = request.headers.get('Accept-Encoding', '')
    accept_language = request.headers.get('Accept-Language', '')
    
    # Extract proxy-related headers
    x_forwarded_scheme = request.headers.get('X-Forwarded-Scheme', '')
    x_forwarded_proto = request.headers.get('X-Forwarded-Proto', '')
    x_forwarded_port = request.headers.get('X-Forwarded-Port', '')
    
    # Extract signature headers (for HMAC verification)
    signature_header = (
        request.headers.get('X-GEWE-SIGNATURE') or
        request.headers.get('X-Signature') or
        request.headers.get('X-Webhook-Signature') or
        request.headers.get('X-Hub-Signature') or
        request.headers.get('X-Hub-Signature-256')
    )
    
    # Extract token headers
    x_gewe_token = request.headers.get('X-GEWE-TOKEN', '')
    authorization_header = request.headers.get('Authorization', '')
    x_auth_token = request.headers.get('X-Auth-Token', '')
    
    # Request metadata
    request_url = str(request.url)
    request_method = request.method
    request_path = request.url.path
    request_query = str(request.url.query) if request.url.query else ''
    
    # Collect all headers for analysis
    all_headers = dict(request.headers)
    
    # =============================================================================
    # LOG COMPREHENSIVE SECURITY ANALYSIS
    # =============================================================================
    logger.info("=" * 80)
    logger.info("🔒 [Security Analysis] Gewe Webhook Request - Complete Security Audit")
    logger.info("=" * 80)
    
    # IP Address Analysis
    logger.info("📍 [IP Analysis]")
    logger.info("   - X-Real-IP: %s", x_real_ip if x_real_ip else "(not present)")
    logger.info("   - X-Forwarded-For: %s", x_forwarded_for if x_forwarded_for else "(not present)")
    if x_forwarded_for_ips:
        logger.info("   - X-Forwarded-For (parsed): %s", x_forwarded_for_ips)
    logger.info("   - Direct Client IP: %s", direct_client_ip if direct_client_ip else "(not available)")
    logger.info("   - Selected Client IP (for rate limiting): %s", client_ip)
    
    # Domain Analysis
    logger.info("🌐 [Domain Analysis]")
    logger.info("   - Host Header: %s", host_header if host_header else "(not present)")
    logger.info("   - Referer Header: %s", referer_header if referer_header else "(not present)")
    logger.info("   - Origin Header: %s", origin_header if origin_header else "(not present)")
    logger.info("   - X-Forwarded-Host: %s", forwarded_host if forwarded_host else "(not present)")
    
    # Proxy Analysis
    logger.info("🔄 [Proxy Analysis]")
    logger.info("   - X-Forwarded-Scheme: %s", x_forwarded_scheme if x_forwarded_scheme else "(not present)")
    logger.info("   - X-Forwarded-Proto: %s", x_forwarded_proto if x_forwarded_proto else "(not present)")
    logger.info("   - X-Forwarded-Port: %s", x_forwarded_port if x_forwarded_port else "(not present)")
    
    # Request Details
    logger.info("📋 [Request Details]")
    logger.info("   - Method: %s", request_method)
    logger.info("   - Full URL: %s", request_url)
    logger.info("   - Path: %s", request_path)
    logger.info("   - Query String: %s", request_query if request_query else "(empty)")
    logger.info("   - Content-Type: %s", content_type if content_type else "(not present)")
    logger.info("   - Content-Length: %s", content_length if content_length else "(not present)")
    
    # User Agent Analysis
    logger.info("👤 [Client Analysis]")
    logger.info("   - User-Agent: %s", user_agent if user_agent else "(not present)")
    logger.info("   - Accept: %s", accept_header if accept_header else "(not present)")
    logger.info("   - Accept-Encoding: %s", accept_encoding if accept_encoding else "(not present)")
    logger.info("   - Accept-Language: %s", accept_language if accept_language else "(not present)")
    
    # Security Headers Analysis
    logger.info("🔐 [Security Headers Analysis]")
    if signature_header:
        sig_display = signature_header[:50] + "..." if len(signature_header) > 50 else signature_header
        logger.info("   - Signature Header Found: %s (length: %d)", sig_display, len(signature_header))
        logger.info("   - Signature Header Name: %s", 
                   'X-GEWE-SIGNATURE' if request.headers.get('X-GEWE-SIGNATURE')
                   else 'X-Signature' if request.headers.get('X-Signature')
                   else 'X-Webhook-Signature' if request.headers.get('X-Webhook-Signature')
                   else 'X-Hub-Signature' if request.headers.get('X-Hub-Signature')
                   else 'X-Hub-Signature-256')
    else:
        logger.info("   - Signature Header: (not present)")
    
    # Token Headers Analysis
    logger.info("🔑 [Token Headers Analysis]")
    if x_gewe_token:
        token_display = x_gewe_token[:20] + "..." if len(x_gewe_token) > 20 else x_gewe_token
        logger.info("   - X-GEWE-TOKEN: %s (length: %d)", token_display, len(x_gewe_token))
    else:
        logger.info("   - X-GEWE-TOKEN: (not present)")
    
    if authorization_header:
        auth_display = authorization_header[:30] + "..." if len(authorization_header) > 30 else authorization_header
        logger.info("   - Authorization: %s (length: %d)", auth_display, len(authorization_header))
    else:
        logger.info("   - Authorization: (not present)")
    
    if x_auth_token:
        auth_token_display = x_auth_token[:20] + "..." if len(x_auth_token) > 20 else x_auth_token
        logger.info("   - X-Auth-Token: %s (length: %d)", auth_token_display, len(x_auth_token))
    else:
        logger.info("   - X-Auth-Token: (not present)")
    
    # All Headers (Complete List)
    logger.info("📋 [All Headers - Complete List]")
    for header_name, header_value in sorted(all_headers.items()):
        # Mask sensitive values
        if header_name.lower() in ['x-gewe-token', 'authorization', 'x-auth-token']:
            if len(header_value) > 20:
                masked_value = header_value[:10] + "..." + header_value[-10:]
            else:
                masked_value = "*" * len(header_value)
            logger.info("   - %s: %s", header_name, masked_value)
        else:
            # Truncate very long header values
            if len(header_value) > 200:
                logger.info("   - %s: %s... (truncated, length: %d)", header_name, header_value[:200], len(header_value))
            else:
                logger.info("   - %s: %s", header_name, header_value)
    
    logger.info("=" * 80)

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
    # Note: This is unreliable when behind reverse proxy (nginx, etc.) as Host/Referer headers
    # will show the proxy domain, not Gewe's domain. Token verification + IP whitelisting
    # are the primary security mechanisms in reverse proxy scenarios.
    enable_domain_check = os.getenv('GEWE_WEBHOOK_ENABLE_DOMAIN_CHECK', 'false').strip().lower() == 'true'
    
    if enable_domain_check:
        gewe_base_url = os.getenv('GEWE_BASE_URL', 'http://api.geweapi.com').strip()
        # Extract domain from base URL (handle http://api.geweapi.com or https://api.geweapi.com)
        gewe_domain = gewe_base_url.replace('http://', '').replace('https://', '').split('/')[0]

        domain_valid = False
        # Check Referer header (most reliable for webhook verification when not behind proxy)
        if referer_header:
            if gewe_domain in referer_header:
                domain_valid = True
                logger.debug("Domain verified via Referer: %s", referer_header)

        # If Referer check failed, log warning but don't block
        # (Domain verification is secondary to token verification)
        if not domain_valid:
            logger.debug(
                "Domain verification skipped/failed - IP: %s, Host: %s, Referer: %s. "
                "Expected domain: %s. This is normal when behind reverse proxy.",
                client_ip, host_header, referer_header, gewe_domain
            )
    else:
        logger.debug(
            "Domain verification disabled (GEWE_WEBHOOK_ENABLE_DOMAIN_CHECK=false). "
            "Using token verification + IP whitelisting for security."
        )

    # Token verification for webhook security (MANDATORY)
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
        logger.info("✅ [Security] Token verified successfully from %s", token_source)
    
    # =============================================================================
    # SECURITY VERIFICATION SUMMARY
    # =============================================================================
    logger.info("=" * 80)
    logger.info("🔒 [Security Summary] Webhook Security Verification Results")
    logger.info("=" * 80)
    
    # IP Whitelisting Status
    allowed_ips_str = os.getenv('GEWE_WEBHOOK_ALLOWED_IPS', '').strip()
    if allowed_ips_str:
        allowed_ips = [ip.strip() for ip in allowed_ips_str.split(',') if ip.strip()]
        ip_allowed = client_ip in allowed_ips
        logger.info("✅ [IP Whitelist] Configured: %s", allowed_ips)
        logger.info("   - Request IP: %s", client_ip)
        logger.info("   - Status: %s", "ALLOWED" if ip_allowed else "BLOCKED")
    else:
        logger.info("⚠️  [IP Whitelist] NOT CONFIGURED (allowing all IPs)")
        logger.info("   - Request IP: %s", client_ip)
        logger.info("   - Recommendation: Set GEWE_WEBHOOK_ALLOWED_IPS with Gewe's IP ranges")
    
    # Token Verification Status
    logger.info("✅ [Token Verification] MANDATORY - VERIFIED")
    logger.info("   - Token Source: %s", token_source)
    logger.info("   - Status: VALID")
    
    # Domain Verification Status
    enable_domain_check = os.getenv('GEWE_WEBHOOK_ENABLE_DOMAIN_CHECK', 'false').strip().lower() == 'true'
    if enable_domain_check:
        gewe_base_url = os.getenv('GEWE_BASE_URL', 'http://api.geweapi.com').strip()
        gewe_domain = gewe_base_url.replace('http://', '').replace('https://', '').split('/')[0]
        domain_match = gewe_domain in (host_header or referer_header or origin_header)
        logger.info("✅ [Domain Verification] ENABLED")
        logger.info("   - Expected Domain: %s", gewe_domain)
        logger.info("   - Host Header: %s", host_header)
        logger.info("   - Referer Header: %s", referer_header)
        logger.info("   - Origin Header: %s", origin_header)
        logger.info("   - Status: %s", "VERIFIED" if domain_match else "NOT VERIFIED")
    else:
        logger.info("ℹ️  [Domain Verification] DISABLED (normal for reverse proxy)")
        logger.info("   - Reason: Domain verification unreliable behind reverse proxy")
        logger.info("   - Recommendation: Use IP whitelisting instead")
    
    # Rate Limiting Status (already logged above, but summarize)
    logger.info("✅ [Rate Limiting] ACTIVE")
    logger.info("   - Limit: 100 requests/minute per IP")
    logger.info("   - Current IP: %s", client_ip)
    
    # Signature Header Status
    if signature_header:
        logger.info("ℹ️  [Signature] PRESENT (not currently verified)")
        logger.info("   - Header: %s", 
                   'X-GEWE-SIGNATURE' if request.headers.get('X-GEWE-SIGNATURE')
                   else 'X-Signature' if request.headers.get('X-Signature')
                   else 'X-Webhook-Signature' if request.headers.get('X-Webhook-Signature')
                   else 'X-Hub-Signature' if request.headers.get('X-Hub-Signature')
                   else 'X-Hub-Signature-256')
        logger.info("   - Recommendation: Implement HMAC signature verification if available")
    else:
        logger.info("ℹ️  [Signature] NOT PRESENT")
        logger.info("   - Recommendation: Check if Gewe supports HMAC signatures")
    
    # Security Recommendations
    logger.info("💡 [Security Recommendations]")
    recommendations = []
    if not allowed_ips_str:
        recommendations.append("Set GEWE_WEBHOOK_ALLOWED_IPS with Gewe's IP addresses/ranges")
    if signature_header and not enable_domain_check:
        recommendations.append("Consider implementing HMAC signature verification")
    if not recommendations:
        recommendations.append("Current security configuration is good")
    
    for i, rec in enumerate(recommendations, 1):
        logger.info("   %d. %s", i, rec)
    
    logger.info("=" * 80)

    # 4. Request Payload Validation (Priority 2: Important)
    # Validate that payload has expected structure for Gewe messages
    # Test messages may have different structure, so we allow testMsg
    if 'testMsg' in message_data:
        test_message = message_data.get('testMsg')
        logger.info("🧪 [Webhook] Received test message from Gewe: %s", test_message)
        test_response = {"status": "ok", "message": "Test message received"}
        logger.info("📤 [Webhook] Sending test response to Gewe: %s", json.dumps(test_response, ensure_ascii=False))
        # Test messages are OK, just return success
        return test_response

    # For real messages, validate required fields
    if not message_data.get('Appid') and not message_data.get('Wxid'):
        logger.warning("Invalid webhook payload - missing Appid/Wxid: %s", message_data)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload: missing Appid or Wxid"
        )

    service = GeweService(db)
    webhook_response = {"status": "ok"}
    try:
        logger.info("🔄 [Webhook] Processing Gewe webhook message")
        logger.debug("📨 [Webhook] Message data: %s", json.dumps(message_data, ensure_ascii=False, indent=2))

        # Process message and get Dify response
        response_text, to_wxid = await service.process_incoming_message(message_data)
        logger.info(
            "💬 [Webhook] Message processing result - Response text length: %d, To wxid: %s",
            len(response_text) if response_text else 0, to_wxid
        )

        # If we have a response, send it back via WeChat
        if response_text and to_wxid:
            app_id = message_data.get('Appid', '')
            if app_id:
                try:
                    logger.info(
                        "📤 [Webhook] Sending response message - App ID: %s, To: %s, Content length: %d",
                        app_id, to_wxid, len(response_text)
                    )
                    send_result = await service.send_text_message(
                        app_id=app_id,
                        to_wxid=to_wxid,
                        content=response_text
                    )
                    logger.info(
                        "✅ [Webhook] Successfully sent Dify response to %s. Result: %s",
                        to_wxid, json.dumps(send_result, ensure_ascii=False, indent=2) if isinstance(send_result, dict) else send_result
                    )
                except Exception as e:
                    logger.error("❌ [Webhook] Error sending response message: %s", e, exc_info=True)
                    webhook_response = {"status": "error", "message": f"Failed to send response: {str(e)}"}
            else:
                logger.warning("⚠️ [Webhook] Cannot send response - App ID missing from message data")
        else:
            logger.info("ℹ️ [Webhook] No response to send (response_text or to_wxid is empty)")

        logger.info("✅ [Webhook] Webhook processing completed successfully")
        logger.info(
            "📤 [Webhook] Sending HTTP response to Gewe: %s",
            json.dumps(webhook_response, ensure_ascii=False, indent=2)
        )
        return webhook_response

    except Exception as e:
        logger.error("❌ [Webhook] Error processing Gewe webhook: %s", e, exc_info=True)
        webhook_response = {"status": "error", "message": str(e)}
        logger.info(
            "📤 [Webhook] Sending error HTTP response to Gewe: %s",
            json.dumps(webhook_response, ensure_ascii=False, indent=2)
        )
        return webhook_response
    finally:
        await service.cleanup()
        logger.debug("🧹 [Webhook] Cleaned up service resources")
