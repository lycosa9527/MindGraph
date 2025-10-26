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
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from captcha.image import ImageCaptcha

from config.database import get_db
from utils.invitations import normalize_or_generate, INVITE_PATTERN
from models.auth import User, Organization
from models.requests import RegisterRequest, LoginRequest, DemoPasskeyRequest
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
    login_attempts,
    ip_attempts,
    captcha_attempts,
    MAX_LOGIN_ATTEMPTS,
    MAX_CAPTCHA_ATTEMPTS,
    AUTH_MODE,
    DEMO_PASSKEY,
    ADMIN_DEMO_PASSKEY
)

import logging

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])

# In-memory captcha storage (use Redis in production for multi-server)
captcha_store = {}

# Path to Inter fonts (already in project)
CAPTCHA_FONTS = [
    os.path.join('static', 'fonts', 'inter-600.ttf'),  # Semi-bold
    os.path.join('static', 'fonts', 'inter-700.ttf'),  # Bold
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
    response: Response,
    db: Session = Depends(get_db)
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
    """
    # Validate captcha first (anti-bot protection)
    if request.captcha_id not in captcha_store:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Captcha expired or invalid. Please refresh."
        )
    
    stored_captcha = captcha_store[request.captcha_id]
    
    # Check expiration
    if time.time() > stored_captcha["expires"]:
        del captcha_store[request.captcha_id]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Captcha expired. Please refresh."
        )
    
    if stored_captcha['code'].upper() != request.captcha.upper():
        # Don't delete captcha_id yet, allow retry
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect captcha code"
        )
    
    # Captcha verified (case-insensitive), remove from store (one-time use)
    del captcha_store[request.captcha_id]
    logger.debug(f"Captcha verified for registration: {request.phone}")
    
    # Check if phone already exists
    existing_user = db.query(User).filter(User.phone == request.phone).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number already registered"
        )
    
    # Find organization by invitation code (each invitation code is unique)
    provided_invite = (request.invitation_code or "").strip().upper()
    if not provided_invite:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invitation code is required"
        )
    
    org = db.query(Organization).filter(
        Organization.invitation_code == provided_invite
    ).first()
    
    if not org:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or expired invitation code"
        )
    
    logger.debug(f"User registering with invitation code for organization: {org.code} ({org.name})")
    
    # Create new user
    new_user = User(
        phone=request.phone,
        password_hash=hash_password(request.password),
        name=request.name,
        organization_id=org.id,
        created_at=datetime.utcnow()
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
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
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
    response: Response,
    db: Session = Depends(get_db)
):
    """
    User login with captcha verification
    
    Security features:
    - Captcha verification (bot protection)
    - Rate limiting: 5 attempts per 15 minutes (per phone)
    - Account lockout: 15 minutes after 5 failed attempts
    - Failed attempt tracking in database
    """
    # Check rate limit by phone
    is_allowed, rate_limit_msg = check_rate_limit(
        request.phone, login_attempts, MAX_LOGIN_ATTEMPTS
    )
    if not is_allowed:
        logger.warning(f"Rate limit exceeded for {request.phone}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_limit_msg
        )
    
    # Find user
    user = db.query(User).filter(User.phone == request.phone).first()
    
    if not user:
        # Record failed attempt even if user doesn't exist (security)
        record_failed_attempt(request.phone, login_attempts)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid phone or password"
        )
    
    # Check account lockout
    is_locked, lockout_msg = check_account_lockout(user)
    if is_locked:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=lockout_msg
        )
    
    # Verify captcha
    captcha_valid = verify_captcha(request.captcha_id, request.captcha)
    if not captcha_valid:
        record_failed_attempt(request.phone, login_attempts)
        increment_failed_attempts(user, db)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid captcha code"
        )
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        record_failed_attempt(request.phone, login_attempts)
        increment_failed_attempts(user, db)
        
        attempts_left = MAX_LOGIN_ATTEMPTS - user.failed_login_attempts
        if attempts_left > 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid password. {attempts_left} attempts remaining."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account locked due to too many failed attempts. Try again in 15 minutes."
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
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization account is locked. Please contact support."
            )
        
        # Check if organization subscription has expired
        if hasattr(org, 'expires_at') and org.expires_at:
            from datetime import datetime
            if org.expires_at < datetime.utcnow():
                logger.warning(f"Login blocked: Organization {org.code} expired on {org.expires_at}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Organization subscription has expired. Please contact support."
                )
    
    # Generate JWT token
    token = create_access_token(user)
    
    # Set token as HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
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

@router.get("/captcha/generate")
async def generate_captcha(request: Request):
    """
    Generate PIL image captcha using Inter fonts
    
    Features:
    - Uses existing Inter fonts from project
    - Generates distorted image to prevent OCR bots
    - 100% self-hosted (China-compatible)
    - Rate limited: Max 10 requests per 15 minutes per IP
    
    Returns:
        {
            "captcha_id": "unique-session-id",
            "captcha_image": "data:image/png;base64,..." 
        }
    """
    # Rate limit captcha generation by IP (prevent abuse)
    # Use get_client_ip to handle reverse proxy (nginx) correctly
    client_ip = get_client_ip(request)
    is_allowed, rate_limit_msg = check_rate_limit(
        client_ip, captcha_attempts, MAX_CAPTCHA_ATTEMPTS
    )
    if not is_allowed:
        logger.warning(f"Captcha rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=rate_limit_msg
        )
    
    # Record attempt
    record_failed_attempt(client_ip, captcha_attempts)
    
    # Create captcha generator with Inter fonts
    image_captcha = ImageCaptcha(
        width=200, 
        height=80,
        fonts=CAPTCHA_FONTS
    )
    
    # Generate 4-character code
    # Excludes: I, O, 0, 1 (to avoid confusion)
    chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    code = ''.join(random.choices(chars, k=4))
    
    # Generate distorted image
    data = image_captcha.generate(code)
    
    # Convert to base64 for browser display
    img_base64 = base64.b64encode(data.getvalue()).decode()
    
    # Generate unique session ID
    session_id = str(uuid.uuid4())
    
    # Store code with expiration (5 minutes)
    captcha_store[session_id] = {
        "code": code.upper(),
        "expires": time.time() + 300
    }
    
    # Clean expired captchas (maintenance)
    current_time = time.time()
    expired_keys = [k for k, v in captcha_store.items() if v["expires"] < current_time]
    for key in expired_keys:
        del captcha_store[key]
    
    logger.info(f"Generated captcha: {session_id} for IP: {client_ip}")
    
    return {
        "captcha_id": session_id,
        "captcha_image": f"data:image/png;base64,{img_base64}"
    }


def verify_captcha(captcha_id: str, user_code: str) -> bool:
    """
    Verify captcha code
    
    Note: Verification is CASE-INSENSITIVE for better user experience.
    Users can enter captcha in any case (upper/lower/mixed).
    
    Returns True if valid, False otherwise
    Removes captcha after verification (one-time use)
    """
    if captcha_id not in captcha_store:
        logger.warning(f"Captcha not found: {captcha_id}")
        return False
    
    stored = captcha_store[captcha_id]
    
    # Check expiration
    if time.time() > stored["expires"]:
        del captcha_store[captcha_id]
        logger.warning(f"Captcha expired: {captcha_id}")
        return False
    
    # Verify code (CASE-INSENSITIVE comparison)
    is_valid = stored["code"].upper() == user_code.upper()
    
    # Remove captcha (one-time use)
    del captcha_store[captcha_id]
    
    if not is_valid:
        logger.warning(f"Captcha verification failed: {captcha_id}")
    
    return is_valid


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
    request: DemoPasskeyRequest,
    response: Response,
    db: Session = Depends(get_db)
):
    """
    Verify demo passkey and return JWT token
    
    Demo mode allows access with a 6-digit passkey.
    Supports both regular demo access and admin demo access.
    """
    # Enhanced logging for debugging (without revealing actual passkeys)
    received_length = len(request.passkey) if request.passkey else 0
    expected_length = len(DEMO_PASSKEY)
    logger.info(f"Demo passkey verification attempt - Received: {received_length} chars, Expected: {expected_length} chars")
    
    if not verify_demo_passkey(request.passkey):
        logger.warning(f"Demo passkey verification failed - Check .env file for whitespace in DEMO_PASSKEY or ADMIN_DEMO_PASSKEY")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid passkey"
        )
    
    # Check if this is admin demo access
    is_admin_access = is_admin_demo_passkey(request.passkey)
    
    # Use different user for admin vs regular demo
    demo_phone = "demo-admin@system.com" if is_admin_access else "demo@system.com"
    demo_name = "Demo Admin" if is_admin_access else "Demo User"
    
    # Get or create demo user
    demo_user = db.query(User).filter(User.phone == demo_phone).first()
    
    if not demo_user:
        # Create demo user (regular or admin)
        org = db.query(Organization).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No organizations available for demo"
            )
        
        try:
            # Use a short, simple password for demo users (bcrypt max is 72 bytes)
            demo_user = User(
                phone=demo_phone,
                password_hash=hash_password("demo-no-pwd"),
                name=demo_name,
                organization_id=org.id,
                created_at=datetime.utcnow()
            )
            db.add(demo_user)
            db.commit()
            db.refresh(demo_user)
            logger.info(f"Created new demo user: {demo_phone}")
        except Exception as e:
            # If creation fails, try to rollback and check if user was somehow created
            db.rollback()
            logger.error(f"Failed to create demo user: {e}")
            
            # Try to get the user again in case it was created by another request
            demo_user = db.query(User).filter(User.phone == demo_phone).first()
            if not demo_user:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Demo user creation failed: {str(e)}. Please contact admin or delete existing demo users: DELETE FROM users WHERE phone LIKE 'demo%@system.com';"
                )
    
    # Generate JWT token
    token = create_access_token(demo_user)
    
    # Set token as HTTP-only cookie (prevents redirect loop between /demo and /editor)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    log_msg = "Demo ADMIN access granted" if is_admin_access else "Demo mode access granted"
    logger.info(log_msg)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": demo_user.id,
            "phone": demo_user.phone,
            "name": demo_user.name,
            "is_admin": is_admin_access
        }
    }


# ============================================================================
# LOGOUT
# ============================================================================

@router.post("/logout")
async def logout(response: Response, current_user: User = Depends(get_current_user)):
    """
    Logout user (client-side token removal)
    
    JWT tokens are stateless, so logout happens on client side
    by removing the token from storage.
    """
    # Clear the cookie
    response.delete_cookie(key="access_token")
    
    logger.info(f"User logged out: {current_user.phone}")
    return {"message": "Logged out successfully"}


# ============================================================================
# ADMIN: ORGANIZATION MANAGEMENT
# ============================================================================

@router.get("/admin/organizations", dependencies=[Depends(get_current_user)])
async def list_organizations_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all organizations (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    orgs = db.query(Organization).all()
    result = []
    for org in orgs:
        user_count = db.query(User).filter(User.organization_id == org.id).count()
        result.append({
            "id": org.id,
            "code": org.code,
            "name": org.name,
            "invitation_code": org.invitation_code,
            "user_count": user_count,
            "expires_at": org.expires_at.isoformat() if org.expires_at else None,
            "is_active": org.is_active if hasattr(org, 'is_active') else True,
            "created_at": org.created_at.isoformat() if org.created_at else None
        })
    return result


@router.post("/admin/organizations", dependencies=[Depends(get_current_user)])
async def create_organization_admin(
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new organization (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    if not all(k in request for k in ["code", "name"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing required fields: code, name")
    
    existing = db.query(Organization).filter(Organization.code == request["code"]).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Organization '{request['code']}' exists")
    
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
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate unique invitation code")

    new_org = Organization(
        code=request["code"],
        name=request["name"],
        invitation_code=invitation_code,
        created_at=datetime.utcnow()
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update organization (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Organization ID {org_id} not found")
    
    # Update code (if provided)
    if "code" in request:
        new_code = (request["code"] or "").strip()
        if not new_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization code cannot be empty")
        if len(new_code) > 50:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization code too long (max 50)")
        if new_code != org.code:
            conflict = db.query(Organization).filter(Organization.code == new_code).first()
            if conflict:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Organization '{new_code}' exists")
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
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate unique invitation code")
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
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid date format. Use ISO format (YYYY-MM-DD)")
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete organization (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Organization ID {org_id} not found")
    
    user_count = db.query(User).filter(User.organization_id == org_id).count()
    if user_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                          detail=f"Cannot delete organization with {user_count} users")
    
    db.delete(org)
    db.commit()
    
    logger.warning(f"Admin {current_user.phone} deleted organization: {org.code}")
    return {"message": f"Organization {org.code} deleted successfully"}


# ============================================================================
# ADMIN: USER MANAGEMENT
# ============================================================================

@router.get("/admin/users", dependencies=[Depends(get_current_user)])
async def list_users_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = 1,
    page_size: int = 50,
    search: str = "",
    organization_id: int = None
):
    """
    List users with pagination and filtering (ADMIN ONLY)
    
    Query Parameters:
    - page: Page number (starting from 1)
    - page_size: Number of items per page (default: 50)
    - search: Search by name or phone number
    - organization_id: Filter by organization
    """
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
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
    
    result = []
    for user in users:
        org = db.query(Organization).filter(Organization.id == user.organization_id).first()
        
        # Mask phone number for privacy (show first 3 and last 4 digits)
        # Example: 13812345678 -> 138****5678
        masked_phone = user.phone
        if len(user.phone) == 11:
            masked_phone = user.phone[:3] + "****" + user.phone[-4:]
        
        result.append({
            "id": user.id,
            "phone": masked_phone,  # Masked for display
            "phone_real": user.phone,  # Real phone for editing (admin only)
            "name": user.name,
            "organization_id": user.organization_id,  # For editing
            "organization_code": org.code if org else None,
            "organization_name": org.name if org else None,
            "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            "created_at": user.created_at.isoformat() if user.created_at else None
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user information (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User ID {user_id} not found")
    
    # Update phone (with validation)
    if "phone" in request:
        new_phone = request["phone"].strip()
        if not new_phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Phone cannot be empty")
        if len(new_phone) != 11 or not new_phone.isdigit() or not new_phone.startswith('1'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                              detail="Phone must be 11 digits starting with 1")
        
        # Check if phone already exists (for another user)
        if new_phone != user.phone:
            existing = db.query(User).filter(User.phone == new_phone).first()
            if existing:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, 
                                  detail=f"Phone number {new_phone} already registered")
        user.phone = new_phone
    
    # Update name (with validation)
    if "name" in request:
        new_name = request["name"].strip()
        if not new_name or len(new_name) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                              detail="Name must be at least 2 characters")
        if any(char.isdigit() for char in new_name):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                              detail="Name cannot contain numbers")
        user.name = new_name
    
    # Update organization
    if "organization_id" in request:
        org_id = request["organization_id"]
        if org_id:
            org = db.query(Organization).filter(Organization.id == org_id).first()
            if not org:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, 
                                  detail=f"Organization ID {org_id} not found")
            user.organization_id = org_id
    
    db.commit()
    db.refresh(user)
    
    # Get updated organization info
    org = db.query(Organization).filter(Organization.id == user.organization_id).first()
    
    logger.info(f"Admin {current_user.phone} updated user: {user.phone}")
    
    return {
        "message": "User updated successfully",
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete user (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User ID {user_id} not found")
    
    # Prevent deleting self
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                          detail="Cannot delete your own account")
    
    user_phone = user.phone
    db.delete(user)
    db.commit()
    
    logger.warning(f"Admin {current_user.phone} deleted user: {user_phone}")
    return {"message": f"User {user_phone} deleted successfully"}


@router.put("/admin/users/{user_id}/unlock", dependencies=[Depends(get_current_user)])
async def unlock_user_admin(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unlock user account (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User ID {user_id} not found")
    
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    
    logger.info(f"Admin {current_user.phone} unlocked user: {user.phone}")
    return {"message": f"User {user.phone} unlocked successfully"}


@router.put("/admin/users/{user_id}/reset-password", dependencies=[Depends(get_current_user)])
async def reset_user_password_admin(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset user password to default (12345678) (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User ID {user_id} not found")
    
    # Prevent admin from resetting their own password this way
    if user.id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot reset your own password")
    
    # Reset password to default
    from utils.auth import hash_password
    user.password_hash = hash_password("12345678")
    user.failed_login_attempts = 0  # Also unlock if locked
    user.locked_until = None
    db.commit()
    
    logger.info(f"Admin {current_user.phone} reset password for user: {user.phone}")
    return {"message": f"Password reset to 12345678 for user {user.phone}"}


# ============================================================================
# ADMIN: SYSTEM SETTINGS (.ENV MANAGEMENT)
# ============================================================================

@router.get("/admin/settings", dependencies=[Depends(get_current_user)])
async def get_settings_admin(current_user: User = Depends(get_current_user)):
    """Get system settings from .env (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
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
    current_user: User = Depends(get_current_user)
):
    """Update system settings in .env (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    forbidden_keys = ['JWT_SECRET_KEY', 'DATABASE_URL']
    for key in request:
        if key in forbidden_keys:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                              detail=f"Cannot modify {key} via API")
    
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
        "message": "Settings updated successfully",
        "warning": "⚠️ Server restart required for changes to take effect!",
        "updated_keys": list(request.keys())
    }


@router.get("/admin/stats", dependencies=[Depends(get_current_user)])
async def get_stats_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get system statistics (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    total_users = db.query(User).count()
    total_orgs = db.query(Organization).count()
    
    now = datetime.utcnow()
    locked_users = db.query(User).filter(
        User.locked_until != None,
        User.locked_until > now
    ).count()
    
    users_by_org = {}
    orgs = db.query(Organization).all()
    for org in orgs:
        count = db.query(User).filter(User.organization_id == org.id).count()
        users_by_org[org.code] = count
    
    week_ago = now - timedelta(days=7)
    recent_registrations = db.query(User).filter(User.created_at >= week_ago).count()
    
    return {
        "total_users": total_users,
        "total_organizations": total_orgs,
        "locked_users": locked_users,
        "users_by_org": users_by_org,
        "recent_registrations": recent_registrations
    }


# ============================================================================
# API Key Management Endpoints (ADMIN ONLY)
# ============================================================================

@router.get("/admin/api_keys", dependencies=[Depends(get_current_user)])
async def list_api_keys_admin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all API keys with usage stats (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create new API key (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    from utils.auth import generate_api_key
    from datetime import datetime as dt, timedelta
    
    name = request.get("name")
    description = request.get("description", "")
    quota_limit = request.get("quota_limit")
    expires_days = request.get("expires_days")  # Optional: days until expiration
    
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")
    
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
        "message": "API key created successfully",
        "key": key,
        "name": name,
        "quota_limit": quota_limit or "unlimited",
        "warning": "⚠️ Save this key securely - it won't be shown again!"
    }


@router.put("/admin/api_keys/{key_id}", dependencies=[Depends(get_current_user)])
async def update_api_key_admin(
    key_id: int,
    request: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update API key settings (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    from models.auth import APIKey
    
    key_record = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key_record:
        raise HTTPException(status_code=404, detail="API key not found")
    
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
        "message": "API key updated successfully",
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete/revoke API key (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    from models.auth import APIKey
    
    key_record = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key_record:
        raise HTTPException(status_code=404, detail="API key not found")
    
    key_name = key_record.name
    db.delete(key_record)
    db.commit()
    
    return {
        "message": f"API key '{key_name}' deleted successfully"
    }


@router.put("/admin/api_keys/{key_id}/toggle", dependencies=[Depends(get_current_user)])
async def toggle_api_key_admin(
    key_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Toggle API key active status (ADMIN ONLY)"""
    if not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    
    from models.auth import APIKey
    
    key_record = db.query(APIKey).filter(APIKey.id == key_id).first()
    if not key_record:
        raise HTTPException(status_code=404, detail="API key not found")
    
    key_record.is_active = not key_record.is_active
    db.commit()
    
    status_text = "activated" if key_record.is_active else "deactivated"
    
    return {
        "message": f"API key '{key_record.name}' {status_text}",
        "is_active": key_record.is_active
    }

