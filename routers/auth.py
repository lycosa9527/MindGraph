"""
Authentication Router for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Complete authentication API endpoints with security features.
"""

import os
import time
import uuid
import base64
import random
import string
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from io import BytesIO
import math

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Body, Request, Header
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from config.database import get_db
from models.messages import Messages, get_request_language, Language
from utils.invitations import normalize_or_generate, INVITE_PATTERN
from models.auth import User, Organization, SMSVerification
from models.requests import (
    RegisterRequest, 
    LoginRequest, 
    DemoPasskeyRequest,
    SendSMSCodeRequest,
    VerifySMSCodeRequest,
    RegisterWithSMSRequest,
    LoginWithSMSRequest,
    ResetPasswordWithSMSRequest
)
from utils.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    verify_demo_passkey,
    is_admin_demo_passkey,
    validate_invitation_code,
    check_rate_limit,
    record_failed_attempt,
    clear_attempts,
    check_account_lockout,
    increment_failed_attempts,
    reset_failed_attempts,
    is_admin,
    get_client_ip,
    is_https,
    login_attempts,
    ip_attempts,
    captcha_attempts,
    captcha_session_attempts,
    MAX_LOGIN_ATTEMPTS,
    MAX_CAPTCHA_ATTEMPTS,
    CAPTCHA_SESSION_COOKIE_NAME,
    RATE_LIMIT_WINDOW_MINUTES,
    LOCKOUT_DURATION_MINUTES,
    AUTH_MODE,
    DEMO_PASSKEY,
    ADMIN_DEMO_PASSKEY,
    BAYI_DECRYPTION_KEY,
    BAYI_DEFAULT_ORG_CODE,
    decrypt_bayi_token,
    validate_bayi_token_body
)
from services.captcha_storage import get_captcha_storage
from services.sms_middleware import (
    get_sms_middleware,
    SMSServiceError,
    SMS_CODE_EXPIRY_MINUTES,
    SMS_RESEND_INTERVAL_SECONDS,
    SMS_MAX_ATTEMPTS_PER_PHONE,
    SMS_MAX_ATTEMPTS_WINDOW_HOURS
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])

# File-based captcha storage (works across multiple server instances)
captcha_storage = get_captcha_storage()

# Path to Inter fonts (already in project)
CAPTCHA_FONTS = [
    os.path.join('static', 'fonts', 'inter-600.ttf'),  # Semi-bold
    os.path.join('static', 'fonts', 'inter-700.ttf'),  # Bold
]

# Color palette for captcha characters (vibrant colors for better visibility)
CAPTCHA_COLORS = [
    '#E74C3C',  # Red
    '#F39C12',  # Orange
    '#F1C40F',  # Yellow
    '#27AE60',  # Green
    '#3498DB',  # Blue
    '#9B59B6',  # Purple
    '#E91E63',  # Pink
    '#16A085',  # Teal
]

# ============================================================================
# AUTHENTICATION MODE DETECTION
# ============================================================================

@router.get("/mode")
async def get_auth_mode():
    """
    Get current authentication mode
    
    Allows frontend to detect and adapt to different auth modes.
    """
    return {"mode": AUTH_MODE}


@router.get("/organizations")
async def list_organizations(db: Session = Depends(get_db)):
    """
    Get list of all organizations (public endpoint for registration)
    
    Returns basic organization info for registration form dropdown.
    """
    orgs = db.query(Organization).all()
    return [
        {
            "code": org.code,
            "name": org.name
        }
        for org in orgs
    ]


# ============================================================================
# REGISTRATION
# ============================================================================

@router.post("/register")
async def register(
    request: RegisterRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Register new user (K12 teacher)
    
    Validates:
    - Captcha verification (bot protection)
    - 11-digit Chinese mobile number
    - 8+ character password
    - Mandatory name (no numbers)
    - Valid invitation code (automatically binds user to school)
    
    Note: Organization is automatically determined from invitation code.
    Each invitation code is unique and belongs to one school.
    
    Registration is only available in standard and enterprise modes.
    Demo and bayi modes use passkey authentication instead.
    """
    # Detect user language from headers (needed for all error messages)
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    # Check authentication mode - registration not allowed in demo/bayi modes
    if AUTH_MODE in ["demo", "bayi"]:
        error_msg = Messages.error("registration_not_available", lang, AUTH_MODE)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )
    
    # Validate captcha first (anti-bot protection)
    # Use verify_captcha_with_retry() for better database lock handling
    captcha_valid, captcha_error = await verify_captcha_with_retry(request.captcha_id, request.captcha)
    if not captcha_valid:
        if captcha_error == "expired":
            error_msg = Messages.error("captcha_expired", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif captcha_error == "not_found":
            error_msg = Messages.error("captcha_not_found", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif captcha_error == "incorrect":
            error_msg = Messages.error("captcha_incorrect", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif captcha_error == "database_locked":
            error_msg = Messages.error("captcha_database_unavailable", lang)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_msg
            )
        else:
            error_msg = Messages.error("captcha_verify_failed", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
    
    logger.debug(f"Captcha verified for registration: {request.phone}")
    
    # Check if phone already exists
    existing_user = db.query(User).filter(User.phone == request.phone).first()
    if existing_user:
        error_msg = Messages.error("phone_already_registered", lang)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_msg
        )
    
    # Find organization by invitation code (each invitation code is unique)
    provided_invite = (request.invitation_code or "").strip().upper()
    if not provided_invite:
        error_msg = Messages.error("invitation_code_required", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Validate invitation code format (AAAA-XXXXX pattern)
    if not INVITE_PATTERN.match(provided_invite):
        error_msg = Messages.error("invitation_code_invalid_format", lang, request.invitation_code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    org = db.query(Organization).filter(
        Organization.invitation_code == provided_invite
    ).first()
    
    if not org:
        error_msg = Messages.error("invitation_code_not_found", lang, request.invitation_code)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )
    
    logger.debug(f"User registering with invitation code for organization: {org.code} ({org.name})")
    
    # Create new user
    new_user = User(
        phone=request.phone,
        password_hash=hash_password(request.password),
        name=request.name,
        organization_id=org.id,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Generate JWT token
    token = create_access_token(new_user)
    
    # Set token as HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_https(http_request),  # SECURITY: Auto-detect HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    # Set flag cookie to indicate new login session (for AI disclaimer notification)
    response.set_cookie(
        key="show_ai_disclaimer",
        value="true",
        httponly=False,  # Allow JavaScript to read it
        secure=is_https(http_request),
        samesite="lax",
        max_age=60 * 60  # 1 hour (should be cleared after showing notification)
    )
    
    logger.info(f"User registered: {new_user.phone} (Org: {org.code})")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "phone": new_user.phone,
            "name": new_user.name,
            "organization": org.name
        }
    }


# ============================================================================
# LOGIN WITH CAPTCHA & RATE LIMITING
# ============================================================================

@router.post("/login")
async def login(
    request: LoginRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    User login with captcha verification
    
    Security features:
    - Captcha verification (bot protection)
    - Rate limiting: 10 attempts per 15 minutes (per phone)
    - Account lockout: 5 minutes after 10 failed attempts
    - Failed attempt tracking in database
    """
    # Detect user language from headers (needed for all error messages)
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    # Check rate limit by phone
    is_allowed, _ = check_rate_limit(
        request.phone, login_attempts, MAX_LOGIN_ATTEMPTS
    )
    if not is_allowed:
        logger.warning(f"Rate limit exceeded for {request.phone}")
        # Use localized message instead of hardcoded English from check_rate_limit
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg
        )
    
    # Find user
    user = db.query(User).filter(User.phone == request.phone).first()
    
    if not user:
        # Record failed attempt even if user doesn't exist (security)
        record_failed_attempt(request.phone, login_attempts)
        recent_attempts = [t for t in login_attempts.get(request.phone, []) if t > time.time() - (RATE_LIMIT_WINDOW_MINUTES * 60)]
        attempts_left = MAX_LOGIN_ATTEMPTS - len(recent_attempts)
        if attempts_left > 0:
            error_msg = Messages.error("login_failed_phone_not_found", lang, attempts_left)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg
            )
        else:
            error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
    
    # Check account lockout
    is_locked, _ = check_account_lockout(user)
    if is_locked:
        # Use localized message instead of hardcoded English from check_account_lockout
        minutes_left = LOCKOUT_DURATION_MINUTES
        error_msg = Messages.error("account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=error_msg
        )
    
    # Verify captcha
    captcha_valid, captcha_error = await verify_captcha_with_retry(request.captcha_id, request.captcha)
    if not captcha_valid:
        # Check for database lock first - don't count as failed attempt
        if captcha_error == "database_locked":
            # Database lock - don't count as failed attempt, return 503
            error_msg = Messages.error("captcha_database_unavailable", lang)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_msg
            )
        
        # For all other captcha errors, record failed attempt
        record_failed_attempt(request.phone, login_attempts)
        increment_failed_attempts(user, db)
        attempts_left = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
        
        # Provide specific captcha error message with retry suggestions (bilingual)
        if captcha_error == "expired":
            captcha_msg = Messages.error("captcha_expired", lang)
        elif captcha_error == "not_found":
            captcha_msg = Messages.error("captcha_not_found", lang)
        elif captcha_error == "incorrect":
            captcha_msg = Messages.error("captcha_incorrect", lang)
        else:
            captcha_msg = Messages.error("captcha_verify_failed", lang)
        
        if attempts_left > 0:
            # Bilingual attempt counter message
            attempts_msg = Messages.error("captcha_retry_attempts", lang, attempts_left)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{captcha_msg}{attempts_msg}"
            )
        else:
            # Account is now locked - bilingual message
            minutes_left = LOCKOUT_DURATION_MINUTES
            lockout_msg = Messages.error("captcha_account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=lockout_msg
            )
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        record_failed_attempt(request.phone, login_attempts)
        increment_failed_attempts(user, db)
        
        attempts_left = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
        if attempts_left > 0:
            error_msg = Messages.error("invalid_password", lang, attempts_left)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=error_msg
            )
        else:
            # Account is now locked
            minutes_left = LOCKOUT_DURATION_MINUTES
            error_msg = Messages.error("account_locked", lang, MAX_LOGIN_ATTEMPTS, minutes_left)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=error_msg
            )
    
    # Successful login
    clear_attempts(request.phone, login_attempts)
    reset_failed_attempts(user, db)
    
    # Get organization
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    
    # Check organization status (locked or expired)
    if org:
        # Check if organization is locked
        is_active = org.is_active if hasattr(org, 'is_active') else True
        if not is_active:
            logger.warning(f"Login blocked: Organization {org.code} is locked")
            error_msg = Messages.error("organization_locked", lang, org.name)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
        
        # Check if organization subscription has expired
        if hasattr(org, 'expires_at') and org.expires_at:
            from datetime import datetime, timezone
            if org.expires_at < datetime.now(timezone.utc):
                logger.warning(f"Login blocked: Organization {org.code} expired on {org.expires_at}")
                expired_date = org.expires_at.strftime("%Y-%m-%d")
                error_msg = Messages.error("organization_expired", lang, org.name, expired_date)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=error_msg
                )
    
    # Generate JWT token
    token = create_access_token(user)
    
    # Set token as HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_https(http_request),  # SECURITY: Auto-detect HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    # Set flag cookie to indicate new login session (for AI disclaimer notification)
    response.set_cookie(
        key="show_ai_disclaimer",
        value="true",
        httponly=False,  # Allow JavaScript to read it
        secure=is_https(http_request),
        samesite="lax",
        max_age=60 * 60  # 1 hour (should be cleared after showing notification)
    )
    
    logger.info(f"User logged in: {user.phone}")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "organization": org.name if org else None
        }
    }


# ============================================================================
# CAPTCHA GENERATION
# ============================================================================

def _generate_custom_captcha(code: str) -> BytesIO:
    """
    Generate custom captcha image with larger letters and different colors per character.
    
    Args:
        code: The captcha code string to render (4 characters)
        
    Returns:
        BytesIO object containing PNG image data
    """
    # Image dimensions - match CSS display size (140x50)
    width, height = 140, 50
    
    # Create image with white background
    image = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(image)
    
    # Load font (use bold font for better visibility)
    font_path = CAPTCHA_FONTS[1] if os.path.exists(CAPTCHA_FONTS[1]) else CAPTCHA_FONTS[0]
    try:
        # Font size proportional to image height (70% of height for good visibility)
        font_size = int(height * 0.7)  # 35px for 50px height
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        # Fallback to default font if custom font fails
        font = ImageFont.load_default()
        font_size = 24
    
    # Measure all characters first to calculate proper spacing
    char_widths = []
    char_bboxes = []
    
    for char in code:
        try:
            # Pillow 8.0+ method
            bbox = draw.textbbox((0, 0), char, font=font)
            char_width = bbox[2] - bbox[0]
            char_height = bbox[3] - bbox[1]
            char_bboxes.append(bbox)
        except AttributeError:
            # Fallback for older Pillow versions
            char_width, char_height = draw.textsize(char, font=font)
            char_bboxes.append((0, 0, char_width, char_height))
            char_width = char_width
            char_height = char_height
        
        char_widths.append(char_width)
    
    # Calculate total width needed and spacing
    total_char_width = sum(char_widths)
    padding = width * 0.08  # 8% padding on each side
    available_width = width - (padding * 2)
    spacing = (available_width - total_char_width) / (len(code) - 1) if len(code) > 1 else 0
    
    # Starting X position (left padding)
    current_x = padding
    
    # Vertical center of the image (where we want characters centered)
    image_center_y = height / 2
    
    # Draw each character with different color and slight rotation
    for i, char in enumerate(code):
        # Select color for this character
        color = CAPTCHA_COLORS[i % len(CAPTCHA_COLORS)]
        
        # Get character dimensions
        bbox = char_bboxes[i]
        char_width = char_widths[i]
        char_height = bbox[3] - bbox[1]
        
        # Calculate character center X position
        char_center_x = current_x + char_width / 2
        
        # Add slight random rotation for each character (-10 to +10 degrees)
        rotation = random.uniform(-10, 10)
        
        # Create a temporary image for this character (with padding for rotation)
        # Use sufficient padding to ensure rotation doesn't clip
        padding_size = max(char_width, char_height) * 0.6
        char_img_width = int(char_width + padding_size * 2)
        char_img_height = int(char_height + padding_size * 2)
        char_img = Image.new('RGBA', (char_img_width, char_img_height), (255, 255, 255, 0))
        char_draw = ImageDraw.Draw(char_img)
        
        # Draw character so its visual center is at the center of char_img
        # When drawing text at (x, y), the bbox top-left is at (x + bbox[0], y + bbox[1])
        # The visual center of the character is at (x + bbox[0] + char_width/2, y + bbox[1] + char_height/2)
        # To center: x + bbox[0] + char_width/2 = char_img_width/2
        #            y + bbox[1] + char_height/2 = char_img_height/2
        text_x = char_img_width / 2 - bbox[0] - char_width / 2
        text_y = char_img_height / 2 - bbox[1] - char_height / 2
        char_draw.text((text_x, text_y), char, fill=color, font=font)
        
        # Rotate character around its center (which is also the character's visual center)
        rotated_char = char_img.rotate(rotation, center=(char_img_width/2, char_img_height/2), expand=False)
        
        # Calculate paste position so the character's visual center aligns with image center
        # The character's visual center is still at the center of rotated_char
        paste_x = int(char_center_x - rotated_char.width / 2)
        paste_y = int(image_center_y - rotated_char.height / 2)
        
        # Ensure paste position is within image bounds (prevent cutoff)
        # Clamp to bounds, but try to keep centered if possible
        if paste_x < 0:
            paste_x = 0
        elif paste_x + rotated_char.width > width:
            paste_x = width - rotated_char.width
            
        if paste_y < 0:
            paste_y = 0
        elif paste_y + rotated_char.height > height:
            paste_y = height - rotated_char.height
        
        # Paste rotated character onto main image
        image.paste(rotated_char, (paste_x, paste_y), rotated_char)
        
        # Move to next character position
        current_x += char_width + spacing
    
    # Add subtle noise lines for security (prevent OCR)
    for _ in range(5):
        x1 = random.randint(0, width)
        y1 = random.randint(0, height)
        x2 = random.randint(0, width)
        y2 = random.randint(0, height)
        noise_color = random.choice(['#E0E0E0', '#E8E8E8', '#F0F0F0'])
        draw.line([(x1, y1), (x2, y2)], fill=noise_color, width=1)
    
    # Add subtle random noise dots
    for _ in range(15):
        x = random.randint(0, width)
        y = random.randint(0, height)
        noise_color = random.choice(['#E0E0E0', '#E8E8E8'])
        draw.ellipse([x-1, y-1, x+1, y+1], fill=noise_color)
    
    # Apply very slight blur filter for anti-OCR
    image = image.filter(ImageFilter.SMOOTH)
    
    # Save to BytesIO
    img_bytes = BytesIO()
    image.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes


@router.get("/captcha/generate")
async def generate_captcha(
    request: Request, 
    response: Response,
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Generate custom captcha image with larger letters and different colors per character
    
    Features:
    - Uses existing Inter fonts from project
    - Large font size (90px) for better readability
    - Each character has a different vibrant color
    - Generates distorted image with noise to prevent OCR bots
    - 100% self-hosted (China-compatible)
    - Rate limited: Max 30 requests per 15 minutes per session (browser cookie)
    
    Returns:
        {
            "captcha_id": "unique-session-id",
            "captcha_image": "data:image/png;base64,..." 
        }
    """
    # Get or create session token for rate limiting
    # Session-based rate limiting allows each browser/device its own limit
    # This solves the issue of many users sharing the same IP (e.g., school network)
    session_token = request.cookies.get(CAPTCHA_SESSION_COOKIE_NAME)
    
    if not session_token:
        # New session - generate token
        session_token = str(uuid.uuid4())
        logger.debug(f"New captcha session created: {session_token[:8]}...")
    
    # Rate limit by session token (not IP)
    is_allowed, _ = check_rate_limit(
        session_token, captcha_session_attempts, MAX_CAPTCHA_ATTEMPTS
    )
    if not is_allowed:
        logger.warning(f"Captcha rate limit exceeded for session: {session_token[:8]}...")
        # Use localized message instead of hardcoded English from check_rate_limit
        accept_language = request.headers.get("Accept-Language", "")
        lang: Language = get_request_language(x_language, accept_language)
        error_msg = Messages.error("too_many_login_attempts", lang, RATE_LIMIT_WINDOW_MINUTES)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg
        )
    
    # Record attempt
    record_failed_attempt(session_token, captcha_session_attempts)
    
    # Set session cookie (matches rate limit window duration)
    response.set_cookie(
        key=CAPTCHA_SESSION_COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=is_https(request),  # SECURITY: Auto-detect HTTPS
        samesite="lax",
        max_age=RATE_LIMIT_WINDOW_MINUTES * 60  # 15 minutes
    )
    
    # Generate 4-character code
    # Excludes: I, O, 0, 1 (to avoid confusion)
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    code = ''.join(random.choices(chars, k=4))
    
    # Generate custom captcha image with larger letters and different colors
    data = _generate_custom_captcha(code)
    
    # Convert to base64 for browser display
    img_base64 = base64.b64encode(data.getvalue()).decode()
    
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    
    # Detect user language from headers
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    # Store code with expiration (5 minutes)
    # Retry logic handles transient database locks automatically
    try:
        captcha_storage.store(session_id, code, expires_in_seconds=300)
    except Exception as e:
        logger.error(f"Failed to store captcha {session_id} after retries: {e}")
        error_msg = Messages.error("captcha_generate_failed", lang)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )
    
    logger.debug(f"Generated captcha: {session_id} for session: {session_token[:8]}...")
    
    return {
        "captcha_id": session_id,
        "captcha_image": f"data:image/png;base64,{img_base64}"
    }


def verify_captcha(captcha_id: str, user_code: str) -> Tuple[bool, Optional[str]]:
    """
    Verify captcha code (synchronous wrapper for storage layer).
    
    Note: Verification is CASE-INSENSITIVE for better user experience.
    Users can enter captcha in any case (upper/lower/mixed).
    
    Returns:
        Tuple of (is_valid: bool, error_reason: Optional[str])
        error_reason can be: "not_found", "expired", "incorrect", "database_locked", "error", or None if valid
    Removes captcha after verification (one-time use)
    """
    return captcha_storage.verify_and_remove(captcha_id, user_code)


async def verify_captcha_with_retry(
    captcha_id: str, 
    user_code: str, 
    max_endpoint_retries: int = 2
) -> Tuple[bool, Optional[str]]:
    """
    Verify captcha with endpoint-level retry for database lock errors.
    
    This provides an additional retry layer beyond storage-level retries (8 retries).
    Uses async sleep to avoid blocking the event loop, allowing other requests to be processed.
    
    Flow:
    1. Call storage layer (which has 8 retries, ~1.5s worst-case)
    2. If database lock error, retry with async sleep (non-blocking)
    3. Total: 8 storage retries + 2 endpoint retries = 10 effective retries (~1.8s worst-case)
    
    Args:
        captcha_id: Unique captcha identifier
        user_code: User-provided captcha code
        max_endpoint_retries: Maximum endpoint-level retries (default: 2)
    
    Returns:
        Tuple of (is_valid: bool, error_reason: Optional[str])
        error_reason can be: "not_found", "expired", "incorrect", "database_locked", "error", or None if valid
    """
    for attempt in range(max_endpoint_retries):
        # Call storage layer (which has its own 8 retries)
        captcha_valid, captcha_error = verify_captcha(captcha_id, user_code)
        
        # If successful, return immediately
        if captcha_valid:
            return captcha_valid, captcha_error
        
        # If error is NOT database-related, don't retry
        # Only retry on database_locked errors (not generic "error" which could be non-database)
        if captcha_error != "database_locked":
            return captcha_valid, captcha_error
        
        # Database lock error - retry with exponential backoff (async, non-blocking)
        if attempt < max_endpoint_retries - 1:
            delay = 0.1 * (2 ** attempt)  # 0.1s, 0.2s
            logger.warning(
                f"[Auth] Database lock in verify_captcha, "
                f"endpoint retry {attempt + 1}/{max_endpoint_retries} after {delay}s delay. "
                f"Captcha ID: {captcha_id[:8]}..."
            )
            await asyncio.sleep(delay)  # Non-blocking async sleep
        else:
            # All endpoint retries exhausted
            logger.error(
                f"[Auth] Database lock persists after {max_endpoint_retries} endpoint retries. "
                f"Captcha ID: {captcha_id[:8]}..."
            )
            return False, "database_locked"
    
    return False, "database_locked"


# ============================================================================
# SMS VERIFICATION
# ============================================================================

@router.post("/sms/send")
async def send_sms_code(
    request: SendSMSCodeRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Send SMS verification code
    
    Sends a 6-digit verification code via Tencent SMS.
    
    Security:
    - Captcha verification required (bot protection)
    
    Purposes:
    - register: For new user registration
    - login: For SMS-based login
    - reset_password: For password recovery
    
    Rate limiting:
    - 60 seconds cooldown between requests for same phone/purpose
    - Maximum 5 codes per hour per phone number
    """
    # Detect user language from headers (needed for all error messages)
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    # Check authentication mode - registration SMS not allowed in demo/bayi modes
    if request.purpose == "register" and AUTH_MODE in ["demo", "bayi"]:
        error_msg = Messages.error("registration_not_available", lang, AUTH_MODE)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )
    
    # Verify captcha first (anti-bot protection)
    captcha_valid, captcha_error = await verify_captcha_with_retry(request.captcha_id, request.captcha)
    if not captcha_valid:
        if captcha_error == "expired":
            error_msg = Messages.error("captcha_expired", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif captcha_error == "not_found":
            error_msg = Messages.error("captcha_not_found", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif captcha_error == "incorrect":
            error_msg = Messages.error("captcha_incorrect", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        elif captcha_error == "database_locked":
            error_msg = Messages.error("captcha_database_unavailable", lang)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=error_msg
            )
        else:
            error_msg = Messages.error("captcha_verify_failed", lang)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
    
    sms_middleware = get_sms_middleware()
    
    # Check if SMS service is available
    if not sms_middleware.is_available:
        error_msg = Messages.error("sms_service_not_configured", lang)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=error_msg
        )
    
    phone = request.phone
    purpose = request.purpose
    
    # For registration, check if phone already exists
    if purpose == "register":
        existing_user = db.query(User).filter(User.phone == phone).first()
        if existing_user:
            error_msg = Messages.error("phone_already_registered", lang)
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )
    
    # For login and reset_password, check if user exists
    if purpose in ["login", "reset_password"]:
        existing_user = db.query(User).filter(User.phone == phone).first()
        if not existing_user:
            if purpose == "login":
                error_msg = Messages.error("phone_not_registered_login", lang)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=error_msg
                )
            else:  # reset_password
                error_msg = Messages.error("phone_not_registered_reset", lang)
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=error_msg
                )
    
    # Check rate limiting: cooldown between requests
    now = datetime.now(timezone.utc)
    cooldown_threshold = now - timedelta(seconds=SMS_RESEND_INTERVAL_SECONDS)
    
    recent_code = db.query(SMSVerification).filter(
        SMSVerification.phone == phone,
        SMSVerification.purpose == purpose,
        SMSVerification.created_at > cooldown_threshold,
        SMSVerification.is_used == False
    ).first()
    
    if recent_code:
        wait_seconds = SMS_RESEND_INTERVAL_SECONDS - int((now - recent_code.created_at).total_seconds())
        wait_minutes = (wait_seconds // 60) + 1 if wait_seconds >= 60 else 0
        if wait_minutes > 0:
            error_msg = Messages.error("sms_cooldown_minutes", lang, wait_minutes)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
        else:
            error_msg = Messages.error("sms_cooldown_seconds", lang, wait_seconds)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_msg
            )
    
    # Check rate limit within time window
    # Count ALL codes created within the window to prevent rate limit bypass
    # (users could otherwise request codes, let them expire, and request more)
    window_start = now - timedelta(hours=SMS_MAX_ATTEMPTS_WINDOW_HOURS)
    window_count = db.query(SMSVerification).filter(
        SMSVerification.phone == phone,
        SMSVerification.created_at > window_start
    ).count()
    
    if window_count >= SMS_MAX_ATTEMPTS_PER_PHONE:
        error_msg = Messages.error("too_many_sms_requests", lang, window_count, SMS_MAX_ATTEMPTS_WINDOW_HOURS)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=error_msg
        )
    
    # Generate verification code first
    code = sms_middleware.generate_code()
    
    # Store verification code in database BEFORE sending SMS
    # This ensures the code is always verifiable if the user receives it.
    # If we sent first and DB failed, user would have unusable code.
    expires_at = now + timedelta(minutes=SMS_CODE_EXPIRY_MINUTES)
    
    # Delete any existing record with same (phone, code, purpose) to prevent
    # IntegrityError from UniqueConstraint collision. This handles the case where
    # the same 6-digit code is randomly generated again for the same phone/purpose.
    db.query(SMSVerification).filter(
        SMSVerification.phone == phone,
        SMSVerification.code == code,
        SMSVerification.purpose == purpose
    ).delete()
    
    sms_verification = SMSVerification(
        phone=phone,
        code=code,
        purpose=purpose,
        expires_at=expires_at,
        created_at=now
    )
    db.add(sms_verification)
    db.commit()
    
    # Now send the SMS with pre-generated code (using middleware's convenience method)
    try:
        success, message, _ = await sms_middleware.send_verification_code(phone, purpose, code=code, lang=lang)
    except SMSServiceError as e:
        # SMS middleware error (rate limiting, etc.)
        # Remove the database record since SMS won't be sent
        db.query(SMSVerification).filter(
            SMSVerification.id == sms_verification.id
        ).delete()
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    
    if not success:
        # SMS sending failed - remove the database record since user won't receive the code
        db.query(SMSVerification).filter(
            SMSVerification.id == sms_verification.id
        ).delete()
        db.commit()
        # Provide more specific error message
        if message and message != "SMS service not available":
            error_detail = message
        else:
            error_detail = Messages.error("sms_service_temporarily_unavailable", lang)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail
        )
    
    logger.info(f"SMS code sent to {phone[:3]}****{phone[-4:]} for {purpose}")
    
    return {
        "message": Messages.success("verification_code_sent", lang),
        "expires_in": SMS_CODE_EXPIRY_MINUTES * 60,  # in seconds
        "resend_after": SMS_RESEND_INTERVAL_SECONDS  # in seconds
    }


@router.post("/sms/verify")
async def verify_sms_code(
    request: VerifySMSCodeRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Verify SMS code (standalone verification)
    
    Verifies the SMS code without performing any action.
    Useful for frontend validation before form submission.
    
    Note: This does NOT consume the code - the actual action
    endpoints (register_sms, login_sms, reset_password) will
    consume it.
    """
    # Detect user language from headers
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    phone = request.phone
    code = request.code
    purpose = request.purpose
    now = datetime.now(timezone.utc)
    
    # Find valid verification code
    verification = db.query(SMSVerification).filter(
        SMSVerification.phone == phone,
        SMSVerification.code == code,
        SMSVerification.purpose == purpose,
        SMSVerification.is_used == False,
        SMSVerification.expires_at > now
    ).order_by(SMSVerification.created_at.desc()).first()
    
    if not verification:
        # Check if code exists but expired
        expired = db.query(SMSVerification).filter(
            SMSVerification.phone == phone,
            SMSVerification.code == code,
            SMSVerification.purpose == purpose,
            SMSVerification.is_used == False
        ).first()
        
        if expired and expired.expires_at <= now:
            error_msg = Messages.error("sms_code_expired", lang, SMS_CODE_EXPIRY_MINUTES)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        error_msg = Messages.error("sms_code_invalid", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Increment attempt count (for tracking)
    verification.attempts += 1
    db.commit()
    
    return {
        "valid": True,
        "message": Messages.success("verification_code_valid", lang)
    }


def _verify_and_consume_sms_code(
    phone: str, 
    code: str, 
    purpose: str, 
    db: Session,
    lang: Language = "en"
) -> bool:
    """
    Internal helper to verify and consume SMS code
    
    Returns True if valid, raises HTTPException if invalid
    
    Uses atomic UPDATE with rowcount check to prevent race conditions.
    This approach works with both SQLite (which ignores SELECT FOR UPDATE)
    and PostgreSQL/MySQL. Only one concurrent request can succeed.
    
    Args:
        phone: Phone number
        code: SMS verification code
        purpose: Purpose of verification (register, login, reset_password)
        db: Database session
        lang: Language for error messages (default: "en")
    """
    now = datetime.now(timezone.utc)
    
    # Use atomic UPDATE with WHERE conditions to prevent race conditions
    # Only one concurrent request will get rowcount=1, others get rowcount=0
    # This works on SQLite (which ignores SELECT FOR UPDATE) and PostgreSQL/MySQL
    result = db.query(SMSVerification).filter(
        SMSVerification.phone == phone,
        SMSVerification.code == code,
        SMSVerification.purpose == purpose,
        SMSVerification.is_used == False,
        SMSVerification.expires_at > now
    ).update(
        {
            SMSVerification.is_used: True,
            SMSVerification.used_at: now
        },
        synchronize_session=False
    )
    db.commit()
    
    # If rowcount is 1, we successfully consumed the code
    # If rowcount is 0, either code doesn't exist, is expired, or was already consumed
    if result == 1:
        return True
    
    # Code was not consumed - provide appropriate error message
    # Check if code exists but expired (for better error message)
    expired = db.query(SMSVerification).filter(
        SMSVerification.phone == phone,
        SMSVerification.code == code,
        SMSVerification.purpose == purpose,
        SMSVerification.is_used == False
    ).first()
    
    if expired and expired.expires_at <= now:
        error_msg = Messages.error("sms_code_expired", lang, SMS_CODE_EXPIRY_MINUTES)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Check if code was already used (race condition - another request consumed it)
    already_used = db.query(SMSVerification).filter(
        SMSVerification.phone == phone,
        SMSVerification.code == code,
        SMSVerification.purpose == purpose,
        SMSVerification.is_used == True
    ).first()
    
    if already_used:
        error_msg = Messages.error("sms_code_already_used", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    error_msg = Messages.error("sms_code_invalid", lang)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=error_msg
    )


@router.post("/register_sms")
async def register_with_sms(
    request: RegisterWithSMSRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Register new user with SMS verification
    
    Alternative to captcha-based registration.
    Requires a valid SMS verification code.
    
    Validates:
    - 11-digit Chinese mobile number
    - 8+ character password
    - Mandatory name (no numbers)
    - Valid invitation code
    - SMS verification code (consumed last to avoid wasting codes)
    
    Registration is only available in standard and enterprise modes.
    Demo and bayi modes use passkey authentication instead.
    """
    # Detect user language from headers (needed for all error messages)
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    # Check authentication mode - registration not allowed in demo/bayi modes
    if AUTH_MODE in ["demo", "bayi"]:
        error_msg = Messages.error("registration_not_available", lang, AUTH_MODE)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )
    
    # Validate all prerequisites BEFORE consuming SMS code
    # This prevents wasting codes on validation failures
    
    # Check if phone already exists
    existing_user = db.query(User).filter(User.phone == request.phone).first()
    if existing_user:
        error_msg = Messages.error("phone_already_registered", lang)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error_msg
        )
    
    # Find organization by invitation code
    provided_invite = (request.invitation_code or "").strip().upper()
    if not provided_invite:
        error_msg = Messages.error("invitation_code_required", lang)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    # Validate invitation code format (AAAA-XXXXX pattern)
    if not INVITE_PATTERN.match(provided_invite):
        error_msg = Messages.error("invitation_code_invalid_format", lang, request.invitation_code)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    
    org = db.query(Organization).filter(
        Organization.invitation_code == provided_invite
    ).first()
    
    if not org:
        error_msg = Messages.error("invitation_code_not_found", lang, request.invitation_code)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )
    
    # All validations passed - now consume the SMS code
    _verify_and_consume_sms_code(
        request.phone, 
        request.sms_code, 
        "register", 
        db,
        lang
    )
    
    logger.debug(f"User registering with SMS for organization: {org.code} ({org.name})")
    
    # Create new user
    new_user = User(
        phone=request.phone,
        password_hash=hash_password(request.password),
        name=request.name,
        organization_id=org.id,
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Generate JWT token
    token = create_access_token(new_user)
    
    # Set token as HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_https(http_request),  # SECURITY: Auto-detect HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    # Set flag cookie to indicate new login session (for AI disclaimer notification)
    response.set_cookie(
        key="show_ai_disclaimer",
        value="true",
        httponly=False,  # Allow JavaScript to read it
        secure=is_https(http_request),
        samesite="lax",
        max_age=60 * 60  # 1 hour (should be cleared after showing notification)
    )
    
    logger.info(f"User registered via SMS: {new_user.phone} (Org: {org.code})")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "phone": new_user.phone,
            "name": new_user.name,
            "organization": org.name
        }
    }


@router.post("/login_sms")
async def login_with_sms(
    request: LoginWithSMSRequest,
    http_request: Request,
    response: Response,
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Login with SMS verification
    
    Alternative to password-based login.
    Requires a valid SMS verification code.
    
    Benefits:
    - No password required
    - Bypasses account lockout
    - Quick verification
    """
    # Detect user language from headers (needed for all error messages)
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    # Validate all prerequisites BEFORE consuming SMS code
    # This prevents wasting codes on validation failures
    
    # Find user first
    user = db.query(User).filter(User.phone == request.phone).first()
    
    if not user:
        error_msg = Messages.error("phone_not_registered_login", lang)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_msg
        )
    
    # Get organization and check status BEFORE consuming code
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    
    # Check organization status
    if org:
        is_active = org.is_active if hasattr(org, 'is_active') else True
        if not is_active:
            logger.warning(f"SMS login blocked: Organization {org.code} is locked")
            error_msg = Messages.error("organization_locked", lang, org.name)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=error_msg
            )
        
        if hasattr(org, 'expires_at') and org.expires_at:
            if org.expires_at < datetime.now(timezone.utc):
                logger.warning(f"SMS login blocked: Organization {org.code} expired")
                expired_date = org.expires_at.strftime("%Y-%m-%d")
                error_msg = Messages.error("organization_expired", lang, org.name, expired_date)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=error_msg
                )
    
    # All validations passed - now consume the SMS code
    _verify_and_consume_sms_code(
        request.phone,
        request.sms_code,
        "login",
        db,
        lang
    )
    
    # Reset any failed attempts (SMS login is verified)
    reset_failed_attempts(user, db)
    
    # Generate JWT token
    token = create_access_token(user)
    
    # Set token as HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_https(http_request),  # SECURITY: Auto-detect HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60
    )
    
    # Set flag cookie to indicate new login session (for AI disclaimer notification)
    response.set_cookie(
        key="show_ai_disclaimer",
        value="true",
        httponly=False,  # Allow JavaScript to read it
        secure=is_https(http_request),
        samesite="lax",
        max_age=60 * 60  # 1 hour (should be cleared after showing notification)
    )
    
    logger.info(f"User logged in via SMS: {user.phone}")
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "organization": org.name if org else None
        }
    }


@router.post("/reset_password")
async def reset_password_with_sms(
    request: ResetPasswordWithSMSRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Reset password with SMS verification
    
    Allows users to reset their password using SMS verification.
    Also unlocks the account if it was locked.
    """
    # Detect user language from headers (needed for all error messages)
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    # Find user
    user = db.query(User).filter(User.phone == request.phone).first()
    
    if not user:
        error_msg = Messages.error("phone_not_registered_reset", lang)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_msg
        )
    
    # Verify SMS code
    _verify_and_consume_sms_code(
        request.phone,
        request.sms_code,
        "reset_password",
        db,
        lang
    )
    
    # Update password
    user.password_hash = hash_password(request.new_password)
    user.failed_login_attempts = 0  # Unlock account
    user.locked_until = None
    db.commit()
    
    logger.info(f"Password reset via SMS for user: {user.phone}")
    
    return {
        "message": Messages.success("password_reset_success", lang),
        "phone": user.phone[:3] + "****" + user.phone[-4:]
    }


# ============================================================================
# CURRENT USER
# ============================================================================

@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user profile
    """
    org = db.query(Organization).filter(
        Organization.id == current_user.organization_id
    ).first()
    
    return {
        "id": current_user.id,
        "phone": current_user.phone,
        "name": current_user.name,
        "organization": {
            "id": org.id if org else None,
            "code": org.code if org else None,
            "name": org.name if org else None
        },
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }


# ============================================================================
# DEMO MODE
# ============================================================================

@router.post("/demo/verify")
async def verify_demo(
    passkey_request: DemoPasskeyRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Verify demo/bayi passkey and return JWT token
    
    Demo mode and Bayi mode allow access with a 6-digit passkey.
    Supports both regular demo access and admin demo access.
    In bayi mode, creates bayi-specific users.
    """
    # Detect user language from headers (needed for all error messages)
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    # Enhanced logging for debugging (without revealing actual passkeys)
    received_length = len(passkey_request.passkey) if passkey_request.passkey else 0
    expected_length = len(DEMO_PASSKEY)
    logger.info(f"Passkey verification attempt ({AUTH_MODE} mode) - Received: {received_length} chars, Expected: {expected_length} chars")
    
    if not verify_demo_passkey(passkey_request.passkey):
        logger.warning(f"Passkey verification failed - Check .env file for whitespace in DEMO_PASSKEY or ADMIN_DEMO_PASSKEY")
        error_msg = Messages.error("invalid_passkey", lang)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error_msg
        )
    
    # Check if this is admin demo access
    is_admin_access = is_admin_demo_passkey(passkey_request.passkey)
    
    # Determine user phone and name based on mode
    if AUTH_MODE == "bayi":
        # Bayi mode: use bayi-specific users
        user_phone = "bayi-admin@system.com" if is_admin_access else "bayi@system.com"
        user_name = "Bayi Admin" if is_admin_access else "Bayi User"
    else:
        # Demo mode: use demo users
        user_phone = "demo-admin@system.com" if is_admin_access else "demo@system.com"
        user_name = "Demo Admin" if is_admin_access else "Demo User"
    
    # Get or create user
    auth_user = db.query(User).filter(User.phone == user_phone).first()
    
    if not auth_user:
        # Get or create organization based on mode
        if AUTH_MODE == "bayi":
            org = db.query(Organization).filter(
                Organization.code == BAYI_DEFAULT_ORG_CODE
            ).first()
            if not org:
                # Create bayi organization if it doesn't exist
                org = Organization(
                    code=BAYI_DEFAULT_ORG_CODE,
                    name="Bayi School",
                    invitation_code="BAYI2024",
                    created_at=datetime.now(timezone.utc)
                )
                db.add(org)
                db.commit()
                db.refresh(org)
                logger.info(f"Created bayi organization: {BAYI_DEFAULT_ORG_CODE}")
        else:
            # Demo mode: use first available organization
            org = db.query(Organization).first()
            if not org:
                # Note: This is an internal error in demo mode, default to English
                error_msg = Messages.error("no_organizations_available", "en")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_msg
                )
        
        try:
            # Use a short, simple password (bcrypt max is 72 bytes)
            auth_user = User(
                phone=user_phone,
                password_hash=hash_password("passkey-no-pwd"),
                name=user_name,
                organization_id=org.id,
                created_at=datetime.now(timezone.utc)
            )
            db.add(auth_user)
            db.commit()
            db.refresh(auth_user)
            logger.info(f"Created new {AUTH_MODE} user: {user_phone}")
        except Exception as e:
            # If creation fails, try to rollback and check if user was somehow created
            db.rollback()
            logger.error(f"Failed to create {AUTH_MODE} user: {e}")
            
            # Try to get the user again in case it was created by another request
            auth_user = db.query(User).filter(User.phone == user_phone).first()
            if not auth_user:
                # Note: This is an internal error, default to English
                error_msg = Messages.error("user_creation_failed", "en", str(e))
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=error_msg
                )
    
    # Generate JWT token
    token = create_access_token(auth_user)
    
    # Set token as HTTP-only cookie (prevents redirect loop between /demo and /editor)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_https(request),  # SECURITY: Auto-detect HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    # Set flag cookie to indicate new login session (for AI disclaimer notification)
    response.set_cookie(
        key="show_ai_disclaimer",
        value="true",
        httponly=False,  # Allow JavaScript to read it
        secure=is_https(request),
        samesite="lax",
        max_age=60 * 60  # 1 hour (should be cleared after showing notification)
    )
    
    log_msg = f"{AUTH_MODE.upper()} {'ADMIN' if is_admin_access else ''} access granted"
    logger.info(log_msg)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": auth_user.id,
            "phone": auth_user.phone,
            "name": auth_user.name,
            "is_admin": is_admin_access
        }
    }


# ============================================================================
# LOGOUT
# ============================================================================

@router.post("/logout")
async def logout(
    request: Request, 
    response: Response, 
    current_user: User = Depends(get_current_user),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    Logout user (client-side token removal)
    
    JWT tokens are stateless, so logout happens on client side
    by removing the token from storage.
    """
    # Detect user language from headers
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    # Clear the cookie (must match original cookie settings)
    response.delete_cookie(
        key="access_token",
        path="/",
        samesite="lax",
        secure=is_https(request)  # SECURITY: Match original cookie settings
    )
    
    logger.info(f"User logged out: {current_user.phone}")
    return {"message": Messages.success("logged_out", lang)}


# ============================================================================
# ADMIN: ORGANIZATION MANAGEMENT
# ============================================================================

@router.get("/admin/organizations", dependencies=[Depends(get_current_user)])
async def list_organizations_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """List all organizations (ADMIN ONLY)"""
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    orgs = db.query(Organization).all()
    result = []
    
    # Get token stats for all organizations (this week)
    token_stats_by_org = {}
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    
    try:
        from models.token_usage import TokenUsage
        org_token_stats = db.query(
            Organization.id,
            Organization.name,
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label('input_tokens'),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label('output_tokens'),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label('total_tokens')
        ).outerjoin(
            TokenUsage,
            and_(
                Organization.id == TokenUsage.organization_id,
                TokenUsage.created_at >= week_ago,
                TokenUsage.success == True
            )
        ).group_by(
            Organization.id,
            Organization.name
        ).all()
        
        for org_stat in org_token_stats:
            token_stats_by_org[org_stat.id] = {
                "input_tokens": int(org_stat.input_tokens or 0),
                "output_tokens": int(org_stat.output_tokens or 0),
                "total_tokens": int(org_stat.total_tokens or 0)
            }
    except (ImportError, Exception) as e:
        logger.debug(f"TokenUsage not available yet: {e}")
    
    for org in orgs:
        user_count = db.query(User).filter(User.organization_id == org.id).count()
        org_token_stats = token_stats_by_org.get(org.id, {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        })
        
        result.append({
            "id": org.id,
            "code": org.code,
            "name": org.name,
            "invitation_code": org.invitation_code,
            "user_count": user_count,
            "expires_at": org.expires_at.isoformat() if org.expires_at else None,
            "is_active": org.is_active if hasattr(org, 'is_active') else True,
            "created_at": org.created_at.isoformat() if org.created_at else None,
            "token_stats": org_token_stats
        })
    return result


@router.post("/admin/organizations", dependencies=[Depends(get_current_user)])
async def create_organization_admin(
    request: dict,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Create new organization (ADMIN ONLY)"""
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    if not all(k in request for k in ["code", "name"]):
        error_msg = Messages.error("missing_required_fields", lang, "code, name")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    existing = db.query(Organization).filter(Organization.code == request["code"]).first()
    if existing:
        error_msg = Messages.error("organization_exists", lang, request["code"])
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
    
    # Prepare invitation code: accept provided if valid, otherwise auto-generate following pattern
    provided_invite = request.get("invitation_code")
    invitation_code = normalize_or_generate(provided_invite, request.get("name"), request.get("code"))

    # Ensure uniqueness of invitation codes across organizations if possible
    existing_invite = db.query(Organization).filter(Organization.invitation_code == invitation_code).first()
    if existing_invite:
        # Regenerate a few times to avoid collision
        attempts = 0
        while attempts < 5:
            invitation_code = normalize_or_generate(None, request.get("name"), request.get("code"))
            if not db.query(Organization).filter(Organization.invitation_code == invitation_code).first():
                break
            attempts += 1
        if attempts == 5:
            error_msg = Messages.error("failed_generate_invitation_code", lang)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)

    new_org = Organization(
        code=request["code"],
        name=request["name"],
        invitation_code=invitation_code,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_org)
    db.commit()
    db.refresh(new_org)
    
    logger.info(f"Admin {current_user.phone} created organization: {new_org.code}")
    return {
        "id": new_org.id,
        "code": new_org.code,
        "name": new_org.name,
        "invitation_code": new_org.invitation_code,
        "created_at": new_org.created_at.isoformat()
    }


@router.put("/admin/organizations/{org_id}", dependencies=[Depends(get_current_user)])
async def update_organization_admin(
    org_id: int,
    request: dict,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Update organization (ADMIN ONLY)"""
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    
    # Update code (if provided)
    if "code" in request:
        new_code = (request["code"] or "").strip()
        if not new_code:
            error_msg = Messages.error("organization_code_empty", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if len(new_code) > 50:
            error_msg = Messages.error("organization_code_too_long", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if new_code != org.code:
            conflict = db.query(Organization).filter(Organization.code == new_code).first()
            if conflict:
                error_msg = Messages.error("organization_exists", lang, new_code)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
            org.code = new_code

    if "name" in request:
        org.name = request["name"]
    if "invitation_code" in request:
        proposed = request.get("invitation_code")
        # Normalize/enforce pattern; if not matching, auto-generate from (new) name/code
        normalized = normalize_or_generate(
            proposed,
            request.get("name", org.name),
            request.get("code", org.code)
        )
        # Ensure uniqueness across organizations (exclude current org)
        conflict = db.query(Organization).filter(
            Organization.invitation_code == normalized,
            Organization.id != org.id
        ).first()
        if conflict:
            attempts = 0
            while attempts < 5:
                normalized = normalize_or_generate(None, request.get("name", org.name), request.get("code", org.code))
                if not db.query(Organization).filter(Organization.invitation_code == normalized, Organization.id != org.id).first():
                    break
                attempts += 1
            if attempts == 5:
                error_msg = Messages.error("failed_generate_invitation_code", lang)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)
        org.invitation_code = normalized
    
    # Update expiration date (if provided)
    if "expires_at" in request:
        expires_str = request.get("expires_at")
        if expires_str:
            from datetime import datetime
            try:
                # Parse ISO format date string
                org.expires_at = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
            except ValueError:
                error_msg = Messages.error("invalid_date_format", lang)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        else:
            org.expires_at = None
    
    # Update active status (if provided)
    if "is_active" in request:
        org.is_active = bool(request.get("is_active"))
    
    db.commit()
    db.refresh(org)
    
    logger.info(f"Admin {current_user.phone} updated organization: {org.code}")
    return {
        "id": org.id,
        "code": org.code,
        "name": org.name,
        "invitation_code": org.invitation_code,
        "expires_at": org.expires_at.isoformat() if org.expires_at else None,
        "is_active": org.is_active if hasattr(org, 'is_active') else True,
        "created_at": org.created_at.isoformat() if org.created_at else None
    }


@router.delete("/admin/organizations/{org_id}", dependencies=[Depends(get_current_user)])
async def delete_organization_admin(
    org_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Delete organization (ADMIN ONLY)"""
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        error_msg = Messages.error("organization_not_found", lang, org_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    
    user_count = db.query(User).filter(User.organization_id == org_id).count()
    if user_count > 0:
        error_msg = Messages.error("cannot_delete_organization_with_users", lang, user_count)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    db.delete(org)
    db.commit()
    
    logger.warning(f"Admin {current_user.phone} deleted organization: {org.code}")
    return {"message": Messages.success("organization_deleted", lang, org.code)}


# ============================================================================
# ADMIN: USER MANAGEMENT
# ============================================================================

@router.get("/admin/users", dependencies=[Depends(get_current_user)])
async def list_users_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = 50,
    search: str = "",
    organization_id: int = None,
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """
    List users with pagination and filtering (ADMIN ONLY)
    
    Query Parameters:
    - page: Page number (starting from 1)
    - page_size: Number of items per page (default: 50)
    - search: Search by name or phone number
    - organization_id: Filter by organization
    """
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    # Build base query
    query = db.query(User)
    
    # Apply organization filter
    if organization_id:
        query = query.filter(User.organization_id == organization_id)
    
    # Apply search filter (name or phone)
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (User.name.like(search_term)) | (User.phone.like(search_term))
        )
    
    # Get total count for pagination
    total = query.count()
    
    # Calculate pagination
    skip = (page - 1) * page_size
    total_pages = (total + page_size - 1) // page_size  # Ceiling division
    
    # Get paginated users
    users = query.order_by(User.created_at.desc()).offset(skip).limit(page_size).all()
    
    # Get token stats for all users (this week)
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    token_stats_by_user = {}
    
    try:
        from models.token_usage import TokenUsage
        user_token_stats = db.query(
            TokenUsage.user_id,
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label('input_tokens'),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label('output_tokens'),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= week_ago,
            TokenUsage.success == True,
            TokenUsage.user_id.isnot(None)
        ).group_by(
            TokenUsage.user_id
        ).all()
        
        for stat in user_token_stats:
            token_stats_by_user[stat.user_id] = {
                "input_tokens": int(stat.input_tokens or 0),
                "output_tokens": int(stat.output_tokens or 0),
                "total_tokens": int(stat.total_tokens or 0)
            }
    except (ImportError, Exception) as e:
        logger.debug(f"TokenUsage not available yet: {e}")
    
    result = []
    for user in users:
        org = db.query(Organization).filter(Organization.id == user.organization_id).first()
        
        # Mask phone number for privacy (show first 3 and last 4 digits)
        # Example: 13812345678 -> 138****5678
        masked_phone = user.phone
        if len(user.phone) == 11:
            masked_phone = user.phone[:3] + "****" + user.phone[-4:]
        
        # Get token stats for this user
        user_token_stats = token_stats_by_user.get(user.id, {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0
        })
        
        result.append({
            "id": user.id,
            "phone": masked_phone,  # Masked for display
            "phone_real": user.phone,  # Real phone for editing (admin only)
            "name": user.name,
            "organization_id": user.organization_id,  # For editing
            "organization_code": org.code if org else None,
            "organization_name": org.name if org else None,
            "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "token_stats": user_token_stats  # Token usage for this user
        })
    
    return {
        "users": result,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages
        }
    }


@router.put("/admin/users/{user_id}", dependencies=[Depends(get_current_user)])
async def update_user_admin(
    user_id: int,
    request: dict,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Update user information (ADMIN ONLY)"""
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    
    # Update phone (with validation)
    if "phone" in request:
        new_phone = request["phone"].strip()
        if not new_phone:
            error_msg = Messages.error("phone_cannot_be_empty", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if len(new_phone) != 11 or not new_phone.isdigit() or not new_phone.startswith('1'):
            error_msg = Messages.error("phone_format_invalid", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        
        # Check if phone already exists (for another user)
        if new_phone != user.phone:
            existing = db.query(User).filter(User.phone == new_phone).first()
            if existing:
                error_msg = Messages.error("phone_already_registered_other", lang, new_phone)
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_msg)
        user.phone = new_phone
    
    # Update name (with validation)
    if "name" in request:
        new_name = request["name"].strip()
        if not new_name or len(new_name) < 2:
            error_msg = Messages.error("name_too_short", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        if any(char.isdigit() for char in new_name):
            error_msg = Messages.error("name_cannot_contain_numbers", lang)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        user.name = new_name
    
    # Update organization
    if "organization_id" in request:
        org_id = request["organization_id"]
        if org_id:
            org = db.query(Organization).filter(Organization.id == org_id).first()
            if not org:
                error_msg = Messages.error("organization_not_found", lang, org_id)
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
            user.organization_id = org_id
    
    db.commit()
    db.refresh(user)
    
    # Get updated organization info
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    
    logger.info(f"Admin {current_user.phone} updated user: {user.phone}")
    
    return {
        "message": Messages.success("user_updated", lang),
        "user": {
            "id": user.id,
            "phone": user.phone,
            "name": user.name,
            "organization_code": org.code if org else None,
            "organization_name": org.name if org else None
        }
    }


@router.delete("/admin/users/{user_id}", dependencies=[Depends(get_current_user)])
async def delete_user_admin(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Delete user (ADMIN ONLY)"""
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    
    # Prevent deleting self
    if user.id == current_user.id:
        error_msg = Messages.error("cannot_delete_own_account", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    user_phone = user.phone
    db.delete(user)
    db.commit()
    
    logger.warning(f"Admin {current_user.phone} deleted user: {user_phone}")
    return {"message": Messages.success("user_deleted", lang, user_phone)}


@router.put("/admin/users/{user_id}/unlock", dependencies=[Depends(get_current_user)])
async def unlock_user_admin(
    user_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Unlock user account (ADMIN ONLY)"""
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    
    logger.info(f"Admin {current_user.phone} unlocked user: {user.phone}")
    return {"message": Messages.success("user_unlocked", lang, user.phone)}


@router.put("/admin/users/{user_id}/reset-password", dependencies=[Depends(get_current_user)])
async def reset_user_password_admin(
    user_id: int,
    request: Optional[dict] = Body(None),
    http_request: Request = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Reset user password (ADMIN ONLY)
    
    Request body (optional):
        {
            "password": "new_password"  # Optional, defaults to "12345678" if not provided
        }
    
    Security:
        - Admin only
        - Cannot reset own password
        - Also unlocks account if locked
    """
    # Get language from request if available
    if http_request:
        accept_language = http_request.headers.get("Accept-Language", "")
        lang: Language = get_request_language(x_language, accept_language)
    else:
        lang: Language = "en"  # Default fallback
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        error_msg = Messages.error("user_not_found", lang, user_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    
    # Prevent admin from resetting their own password this way
    if user.id == current_user.id:
        error_msg = Messages.error("cannot_reset_own_password", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    # Get password from request body, default to '12345678' if not provided
    password = request.get("password") if request and isinstance(request, dict) else None
    new_password = password if password and password.strip() else "12345678"
    
    # Validate password length (minimum 8 characters as per system requirement)
    if not new_password or len(new_password.strip()) == 0:
        error_msg = Messages.error("password_cannot_be_empty", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    if len(new_password.strip()) < 8:
        error_msg = Messages.error("password_too_short", lang)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    # Reset password
    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0  # Also unlock if locked
    user.locked_until = None
    db.commit()
    
    logger.info(f"Admin {current_user.phone} reset password for user: {user.phone}")
    return {"message": Messages.success("password_reset_for_user", lang, user.phone)}


# ============================================================================
# ADMIN: SYSTEM SETTINGS (.ENV MANAGEMENT)
# ============================================================================

@router.get("/admin/settings", dependencies=[Depends(get_current_user)])
async def get_settings_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Get system settings from .env (ADMIN ONLY)"""
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    env_path = ".env"
    settings = {}
    
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    
                    if key in ['JWT_SECRET_KEY', 'DATABASE_URL']:
                        continue
                    
                    if 'PASSWORD' in key or 'SECRET' in key or 'PASSKEY' in key:
                        settings[key] = "******"
                    else:
                        settings[key] = value
    
    return settings


@router.put("/admin/settings", dependencies=[Depends(get_current_user)])
async def update_settings_admin(
    request: dict,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Update system settings in .env (ADMIN ONLY)"""
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    forbidden_keys = ['JWT_SECRET_KEY', 'DATABASE_URL']
    for key in request:
        if key in forbidden_keys:
            error_msg = Messages.error("cannot_modify_field_via_api", lang, key)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    
    env_path = ".env"
    lines = []
    
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    
    updated_keys = set()
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and '=' in stripped:
            key = stripped.split('=', 1)[0].strip()
            if key in request:
                lines[i] = f"{key}={request[key]}\n"
                updated_keys.add(key)
    
    for key, value in request.items():
        if key not in updated_keys:
            lines.append(f"{key}={value}\n")
    
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    logger.warning(f"Admin {current_user.phone} updated .env settings: {list(request.keys())}")
    
    return {
        "message": Messages.success("settings_updated", lang),
        "warning": Messages.warning("server_restart_required", lang),
        "updated_keys": list(request.keys())
    }


@router.get("/admin/stats", dependencies=[Depends(get_current_user)])
async def get_stats_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Get system statistics (ADMIN ONLY)"""
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    total_users = db.query(User).count()
    total_orgs = db.query(Organization).count()
    
    # Get users by organization (using school name, sorted by count descending)
    users_by_org = {}
    orgs = db.query(Organization).all()
    for org in orgs:
        count = db.query(User).filter(User.organization_id == org.id).count()
        users_by_org[org.name] = count
    
    # Sort by count (highest first)
    users_by_org = dict(sorted(users_by_org.items(), key=lambda x: x[1], reverse=True))
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    recent_registrations = db.query(User).filter(User.created_at >= today_start).count()
    
    # Token usage stats (this week) - PER USER and PER ORGANIZATION tracking!
    token_stats = {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0
    }
    
    # Per-organization token usage (for school-level reporting)
    token_stats_by_org = {}
    
    try:
        from models.token_usage import TokenUsage
        
        # Global token stats for past week
        week_token_stats = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= week_ago,
            TokenUsage.success == True
        ).first()
        
        if week_token_stats:
            token_stats = {
                "input_tokens": int(week_token_stats.input_tokens or 0),
                "output_tokens": int(week_token_stats.output_tokens or 0),
                "total_tokens": int(week_token_stats.total_tokens or 0)
            }
        
        # Per-organization TOTAL token usage (all time, for active school ranking)
        # Use LEFT JOIN to include organizations with no token usage
        org_token_stats = db.query(
            Organization.id,
            Organization.name,
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label('input_tokens'),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label('output_tokens'),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label('total_tokens'),
            func.coalesce(func.count(TokenUsage.id), 0).label('request_count')
        ).outerjoin(
            TokenUsage, 
            and_(
                Organization.id == TokenUsage.organization_id,
                TokenUsage.success == True
            )
        ).group_by(
            Organization.id,
            Organization.name
        ).all()
        
        # Build per-organization stats dictionary
        # Only include organizations that actually have token usage
        for org_stat in org_token_stats:
            if org_stat.request_count and org_stat.request_count > 0:
                token_stats_by_org[org_stat.name] = {
                    "org_id": org_stat.id,
                    "input_tokens": int(org_stat.input_tokens or 0),
                    "output_tokens": int(org_stat.output_tokens or 0),
                    "total_tokens": int(org_stat.total_tokens or 0),
                    "request_count": int(org_stat.request_count or 0)
                }
            
    except (ImportError, Exception) as e:
        # TokenUsage model doesn't exist yet or table not created - return zeros
        logger.debug(f"TokenUsage not available yet: {e}")
    
    return {
        "total_users": total_users,
        "total_organizations": total_orgs,
        "users_by_org": users_by_org,
        "recent_registrations": recent_registrations,
        "token_stats": token_stats,  # Global token stats
        "token_stats_by_org": token_stats_by_org  # Per-organization TOTAL token stats (all time)
    }


@router.get("/admin/token-stats", dependencies=[Depends(get_current_user)])
async def get_token_stats_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Get detailed token usage statistics (ADMIN ONLY)"""
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # Initialize default stats
    today_stats = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    week_stats = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    month_stats = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    total_stats = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    top_users = []
    
    try:
        from models.token_usage import TokenUsage
        
        # Today stats
        today_token_stats = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= today_start,
            TokenUsage.success == True
        ).first()
        
        if today_token_stats:
            today_stats = {
                "input_tokens": int(today_token_stats.input_tokens or 0),
                "output_tokens": int(today_token_stats.output_tokens or 0),
                "total_tokens": int(today_token_stats.total_tokens or 0)
            }
        
        # Past week stats
        week_token_stats = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= week_ago,
            TokenUsage.success == True
        ).first()
        
        if week_token_stats:
            week_stats = {
                "input_tokens": int(week_token_stats.input_tokens or 0),
                "output_tokens": int(week_token_stats.output_tokens or 0),
                "total_tokens": int(week_token_stats.total_tokens or 0)
            }
        
        # Past month stats
        month_token_stats = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.created_at >= month_ago,
            TokenUsage.success == True
        ).first()
        
        if month_token_stats:
            month_stats = {
                "input_tokens": int(month_token_stats.input_tokens or 0),
                "output_tokens": int(month_token_stats.output_tokens or 0),
                "total_tokens": int(month_token_stats.total_tokens or 0)
            }
        
        # Total stats (all time)
        total_token_stats = db.query(
            func.sum(TokenUsage.input_tokens).label('input_tokens'),
            func.sum(TokenUsage.output_tokens).label('output_tokens'),
            func.sum(TokenUsage.total_tokens).label('total_tokens')
        ).filter(
            TokenUsage.success == True
        ).first()
        
        if total_token_stats:
            total_stats = {
                "input_tokens": int(total_token_stats.input_tokens or 0),
                "output_tokens": int(total_token_stats.output_tokens or 0),
                "total_tokens": int(total_token_stats.total_tokens or 0)
            }
        
        # Top 10 users by total tokens (all time), including organization name
        top_users_query = db.query(
            User.id,
            User.phone,
            User.name,
            Organization.name.label('organization_name'),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label('total_tokens'),
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label('input_tokens'),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label('output_tokens')
        ).outerjoin(
            Organization,
            User.organization_id == Organization.id
        ).outerjoin(
            TokenUsage,
            and_(
                User.id == TokenUsage.user_id,
                TokenUsage.success == True
            )
        ).group_by(
            User.id,
            User.phone,
            User.name,
            Organization.name
        ).order_by(
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).desc()
        ).limit(10).all()
        
        top_users = [
            {
                "id": user.id,
                "phone": user.phone,
                "name": user.name or user.phone,
                "organization_name": user.organization_name or "",
                "input_tokens": int(user.input_tokens or 0),
                "output_tokens": int(user.output_tokens or 0),
                "total_tokens": int(user.total_tokens or 0)
            }
            for user in top_users_query
        ]
        
    except (ImportError, Exception) as e:
        logger.debug(f"TokenUsage not available yet: {e}")
    
    return {
        "today": today_stats,
        "past_week": week_stats,
        "past_month": month_stats,
        "total": total_stats,
        "top_users": top_users
    }


@router.get("/admin/stats/trends", dependencies=[Depends(get_current_user)])
async def get_stats_trends_admin(
    request: Request,
    metric: str,  # 'users', 'organizations', 'registrations', 'tokens'
    days: int = 30,  # Number of days to look back
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Get time-series trends data for dashboard charts (ADMIN ONLY)"""
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    if days > 90:
        days = 90  # Cap at 90 days
    if days < 1:
        days = 1  # Minimum 1 day
    
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=days)
    start_date = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # Generate all dates in range (fill missing dates with 0)
    date_list = []
    current = start_date
    while current <= now:
        date_list.append(current.date())
        current += timedelta(days=1)
    
    trends_data = []
    
    if metric == 'users':
        # Daily cumulative user count
        try:
            # Get initial count before start_date
            initial_count = db.query(func.count(User.id)).filter(
                User.created_at < start_date
            ).scalar() or 0
            
            # Get user counts grouped by date
            user_counts = db.query(
                func.date(User.created_at).label('date'),
                func.count(User.id).label('count')
            ).filter(
                User.created_at >= start_date
            ).group_by(
                func.date(User.created_at)
            ).all()
            
            # Create a dictionary for quick lookup
            counts_by_date = {str(row.date): row.count for row in user_counts}
            
            # Calculate cumulative counts
            cumulative = initial_count
            for date in date_list:
                date_str = str(date)
                if date_str in counts_by_date:
                    cumulative += counts_by_date[date_str]
                trends_data.append({
                    "date": date_str,
                    "value": cumulative
                })
        except Exception as e:
            logger.error(f"Error fetching user trends: {e}")
            # Return zeros if error
            for date in date_list:
                trends_data.append({"date": str(date), "value": 0})
    
    elif metric == 'organizations':
        # Daily cumulative organization count
        try:
            # Get initial count before start_date
            initial_count = db.query(func.count(Organization.id)).filter(
                Organization.created_at < start_date
            ).scalar() or 0
            
            org_counts = db.query(
                func.date(Organization.created_at).label('date'),
                func.count(Organization.id).label('count')
            ).filter(
                Organization.created_at >= start_date
            ).group_by(
                func.date(Organization.created_at)
            ).all()
            
            counts_by_date = {str(row.date): row.count for row in org_counts}
            
            cumulative = initial_count
            for date in date_list:
                date_str = str(date)
                if date_str in counts_by_date:
                    cumulative += counts_by_date[date_str]
                trends_data.append({
                    "date": date_str,
                    "value": cumulative
                })
        except Exception as e:
            logger.error(f"Error fetching organization trends: {e}")
            for date in date_list:
                trends_data.append({"date": str(date), "value": 0})
    
    elif metric == 'registrations':
        # Daily new user registrations (non-cumulative)
        try:
            reg_counts = db.query(
                func.date(User.created_at).label('date'),
                func.count(User.id).label('count')
            ).filter(
                User.created_at >= start_date
            ).group_by(
                func.date(User.created_at)
            ).all()
            
            counts_by_date = {str(row.date): row.count for row in reg_counts}
            
            for date in date_list:
                date_str = str(date)
                trends_data.append({
                    "date": date_str,
                    "value": counts_by_date.get(date_str, 0)
                })
        except Exception as e:
            logger.error(f"Error fetching registration trends: {e}")
            for date in date_list:
                trends_data.append({"date": str(date), "value": 0})
    
    elif metric == 'tokens':
        # Daily token usage (non-cumulative)
        try:
            from models.token_usage import TokenUsage
            
            token_counts = db.query(
                func.date(TokenUsage.created_at).label('date'),
                func.sum(TokenUsage.total_tokens).label('total_tokens'),
                func.sum(TokenUsage.input_tokens).label('input_tokens'),
                func.sum(TokenUsage.output_tokens).label('output_tokens')
            ).filter(
                TokenUsage.created_at >= start_date,
                TokenUsage.success == True
            ).group_by(
                func.date(TokenUsage.created_at)
            ).all()
            
            tokens_by_date = {
                str(row.date): {
                    "total": int(row.total_tokens or 0),
                    "input": int(row.input_tokens or 0),
                    "output": int(row.output_tokens or 0)
                }
                for row in token_counts
            }
            
            for date in date_list:
                date_str = str(date)
                tokens = tokens_by_date.get(date_str, {"total": 0, "input": 0, "output": 0})
                trends_data.append({
                    "date": date_str,
                    "value": tokens["total"],
                    "input": tokens["input"],
                    "output": tokens["output"]
                })
        except Exception as e:
            logger.error(f"Error fetching token trends: {e}")
            for date in date_list:
                trends_data.append({
                    "date": str(date),
                    "value": 0,
                    "input": 0,
                    "output": 0
                })
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric: {metric}. Must be one of: users, organizations, registrations, tokens"
        )
    
    return {
        "metric": metric,
        "days": days,
        "data": trends_data
    }


# ============================================================================
# API Key Management Endpoints (ADMIN ONLY)
# ============================================================================

@router.get("/admin/api_keys", dependencies=[Depends(get_current_user)])
async def list_api_keys_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """List all API keys with usage stats (ADMIN ONLY)"""
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    from models.auth import APIKey
    
    keys = db.query(APIKey).order_by(APIKey.created_at.desc()).all()
    
    return [{
        "id": key.id,
        "key": key.key,
        "name": key.name,
        "description": key.description,
        "quota_limit": key.quota_limit,
        "usage_count": key.usage_count,
        "is_active": key.is_active,
        "created_at": key.created_at.isoformat() if key.created_at else None,
        "last_used_at": key.last_used_at.isoformat() if key.last_used_at else None,
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
        "usage_percentage": round((key.usage_count / key.quota_limit * 100), 1) if key.quota_limit else 0
    } for key in keys]


@router.post("/admin/api_keys", dependencies=[Depends(get_current_user)])
async def create_api_key_admin(
    request: dict,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Create new API key (ADMIN ONLY)"""
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    from utils.auth import generate_api_key
    from datetime import datetime as dt, timedelta
    
    name = request.get("name")
    description = request.get("description", "")
    quota_limit = request.get("quota_limit")
    expires_days = request.get("expires_days")  # Optional: days until expiration
    
    if not name:
        error_msg = Messages.error("name_required", lang)
        raise HTTPException(status_code=400, detail=error_msg)
    
    # Generate the API key
    key = generate_api_key(name, description, quota_limit, db)
    
    # Update expiration if specified
    if expires_days:
        from models.auth import APIKey
        key_record = db.query(APIKey).filter(APIKey.key == key).first()
        if key_record:
            key_record.expires_at = dt.utcnow() + timedelta(days=expires_days)
            db.commit()
    
    return {
        "message": Messages.success("api_key_created", lang),
        "key": key,
        "name": name,
        "quota_limit": quota_limit or "unlimited",
        "warning": Messages.warning("api_key_save_warning", lang)
    }


@router.put("/admin/api_keys/{key_id}", dependencies=[Depends(get_current_user)])
async def update_api_key_admin(
    key_id: int,
    request: dict,
    http_request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Update API key settings (ADMIN ONLY)"""
    accept_language = http_request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    from models.auth import APIKey
    
    key_record = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key_record:
        error_msg = Messages.error("api_key_not_found", lang)
        raise HTTPException(status_code=404, detail=error_msg)
    
    # Update fields if provided
    if "name" in request:
        key_record.name = request["name"]
    if "description" in request:
        key_record.description = request["description"]
    if "quota_limit" in request:
        key_record.quota_limit = request["quota_limit"]
    if "is_active" in request:
        key_record.is_active = request["is_active"]
    if "usage_count" in request:  # Allow resetting usage
        key_record.usage_count = request["usage_count"]
    
    db.commit()
    
    return {
        "message": Messages.success("api_key_updated", lang),
        "key": {
            "id": key_record.id,
            "name": key_record.name,
            "quota_limit": key_record.quota_limit,
            "usage_count": key_record.usage_count,
            "is_active": key_record.is_active
        }
    }


@router.delete("/admin/api_keys/{key_id}", dependencies=[Depends(get_current_user)])
async def delete_api_key_admin(
    key_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Delete/revoke API key (ADMIN ONLY)"""
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    from models.auth import APIKey
    
    key_record = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key_record:
        error_msg = Messages.error("api_key_not_found", lang)
        raise HTTPException(status_code=404, detail=error_msg)
    
    key_name = key_record.name
    db.delete(key_record)
    db.commit()
    
    return {
        "message": f"API key '{key_name}' deleted successfully"
    }


@router.put("/admin/api_keys/{key_id}/toggle", dependencies=[Depends(get_current_user)])
async def toggle_api_key_admin(
    key_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_language: Optional[str] = Header(None, alias="X-Language")
):
    """Toggle API key active status (ADMIN ONLY)"""
    accept_language = request.headers.get("Accept-Language", "")
    lang: Language = get_request_language(x_language, accept_language)
    
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    
    from models.auth import APIKey
    
    key_record = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key_record:
        error_msg = Messages.error("api_key_not_found", lang)
        raise HTTPException(status_code=404, detail=error_msg)
    
    key_record.is_active = not key_record.is_active
    db.commit()
    
    if key_record.is_active:
        message = Messages.success("api_key_activated", lang, key_record.name)
    else:
        message = Messages.success("api_key_deactivated", lang, key_record.name)
    
    return {
        "message": message,
        "is_active": key_record.is_active
    }

