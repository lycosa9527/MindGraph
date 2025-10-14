"""
Authentication Utilities for MindGraph
Author: lycosa9527
Made by: MindSpring Team

JWT tokens, password hashing, rate limiting, and security functions.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from collections import defaultdict

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from models.auth import User, Organization
from config.database import get_db

import logging

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

# Authentication Mode
AUTH_MODE = os.getenv("AUTH_MODE", "standard").strip().lower()  # standard, enterprise, demo

# Enterprise Mode Configuration
ENTERPRISE_DEFAULT_ORG_CODE = os.getenv("ENTERPRISE_DEFAULT_ORG_CODE", "DEMO-001").strip()
ENTERPRISE_DEFAULT_USER_PHONE = os.getenv("ENTERPRISE_DEFAULT_USER_PHONE", "enterprise@system.com").strip()

# Demo Mode Configuration
DEMO_PASSKEY = os.getenv("DEMO_PASSKEY", "888888").strip()
ADMIN_DEMO_PASSKEY = os.getenv("ADMIN_DEMO_PASSKEY", "999999").strip()

# Admin Configuration
ADMIN_PHONES = os.getenv("ADMIN_PHONES", "").split(",")

# Security Configuration
MAX_LOGIN_ATTEMPTS = 5
MAX_CAPTCHA_ATTEMPTS = 10
LOCKOUT_DURATION_MINUTES = 15
RATE_LIMIT_WINDOW_MINUTES = 15

# ============================================================================
# Password Hashing
# ============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Handles bcrypt's 72-byte limit gracefully by truncating if necessary.
    """
    try:
        return pwd_context.hash(password)
    except ValueError as e:
        if "password cannot be longer than 72 bytes" in str(e):
            # Truncate password to 72 bytes for bcrypt compatibility
            password_bytes = password.encode('utf-8')[:72]
            password_truncated = password_bytes.decode('utf-8', errors='ignore')
            logger.warning("Password exceeded 72 bytes, truncated for bcrypt compatibility")
            return pwd_context.hash(password_truncated)
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash
    
    Handles errors gracefully, including:
    - Corrupted password hashes in database
    - Bcrypt 72-byte limit errors
    - Invalid hash formats
    """
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError as e:
        # Handle bcrypt 72-byte limit
        if "password cannot be longer than 72 bytes" in str(e):
            try:
                password_bytes = plain_password.encode('utf-8')[:72]
                password_truncated = password_bytes.decode('utf-8', errors='ignore')
                logger.warning("Password exceeded 72 bytes during verification, truncated")
                return pwd_context.verify(password_truncated, hashed_password)
            except Exception as inner_e:
                logger.error(f"Password verification failed after truncation: {inner_e}")
                return False
        else:
            logger.error(f"Password verification error: {e}")
            return False
    except Exception as e:
        # Handle corrupted hashes or other bcrypt errors
        logger.error(f"Password hash verification failed (possibly corrupted hash in database): {e}")
        return False


# ============================================================================
# JWT Token Management
# ============================================================================

security = HTTPBearer()


def create_access_token(user: User) -> str:
    """
    Create JWT access token for user
    
    Token payload includes:
    - sub: user_id
    - phone: user phone number
    - org_id: organization id
    - exp: expiration timestamp
    """
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRY_HOURS)
    
    payload = {
        "sub": str(user.id),
        "phone": user.phone,
        "org_id": user.organization_id,
        "exp": expire
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def decode_access_token(token: str) -> dict:
    """
    Decode and validate JWT token
    
    Returns payload if valid, raises HTTPException if invalid/expired
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        logger.warning(f"Invalid token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token
    
    Supports three authentication modes:
    1. standard: Regular JWT authentication (phone/password login)
    2. enterprise: Skip JWT validation (for VPN/SSO deployments with network-level auth)
    3. demo: Regular JWT authentication (passkey login)
    
    IMPORTANT: Demo mode still requires valid JWT tokens!
    Only enterprise mode bypasses authentication entirely.
    """
    # Enterprise Mode: Skip authentication, return enterprise user
    # This is for deployments behind VPN/SSO where network auth is sufficient
    if AUTH_MODE == "enterprise":
        org = db.query(Organization).filter(
            Organization.code == ENTERPRISE_DEFAULT_ORG_CODE
        ).first()
        
        if not org:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Enterprise organization {ENTERPRISE_DEFAULT_ORG_CODE} not found"
            )
        
        user = db.query(User).filter(User.phone == ENTERPRISE_DEFAULT_USER_PHONE).first()
        
        if not user:
            # Auto-create enterprise user (use short password for bcrypt compatibility)
            user = User(
                phone=ENTERPRISE_DEFAULT_USER_PHONE,
                password_hash=hash_password("ent-no-pwd"),
                name="Enterprise User",
                organization_id=org.id,
                created_at=datetime.utcnow()
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("Created enterprise mode user")
        
        return user
    
    # Standard AND Demo Mode: Validate JWT token
    # Demo mode uses passkey for login, but still requires valid JWT tokens
    token = credentials.credentials
    payload = decode_access_token(token)
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    return user


# ============================================================================
# Demo Mode Passkey
# ============================================================================

def display_demo_info():
    """Display demo mode information on startup"""
    if AUTH_MODE == "demo":
        logger.info("=" * 60)
        logger.info("DEMO MODE ACTIVE")
        logger.info(f"Passkey: {DEMO_PASSKEY}")
        logger.info(f"Passkey length: {len(DEMO_PASSKEY)} characters")
        logger.info("Access: /demo")
        logger.info("=" * 60)


def verify_demo_passkey(passkey: str) -> bool:
    """
    Verify demo passkey (regular or admin)
    Returns True if valid, False otherwise
    """
    # Strip whitespace from input passkey to handle client-side issues
    passkey = passkey.strip() if passkey else ""
    return passkey in [DEMO_PASSKEY, ADMIN_DEMO_PASSKEY]


def is_admin_demo_passkey(passkey: str) -> bool:
    """Check if passkey is for admin demo access"""
    # Strip whitespace from input passkey to handle client-side issues
    passkey = passkey.strip() if passkey else ""
    return passkey == ADMIN_DEMO_PASSKEY


# ============================================================================
# Invitation Code Management
# ============================================================================

def load_invitation_codes() -> Dict[str, Tuple[str, Optional[datetime]]]:
    """
    Load invitation codes from environment variable
    
    Format: ORG_CODE:INVITATION_CODE:EXPIRY_DATE
    Example: DEMO-001:DEMO2024:2025-12-31,SPRING-EDU:SPRING123:never
    
    Returns:
        Dict[org_code] = (invitation_code, expiry_datetime or None)
    """
    codes = {}
    env_codes = os.getenv("INVITATION_CODES", "")
    
    if not env_codes:
        return codes
    
    for code_str in env_codes.split(","):
        parts = code_str.strip().split(":")
        if len(parts) >= 2:
            org_code = parts[0]
            invitation_code = parts[1]
            expiry = None
            
            if len(parts) >= 3 and parts[2].lower() != "never":
                try:
                    expiry = datetime.strptime(parts[2], "%Y-%m-%d")
                except ValueError:
                    logger.warning(f"Invalid expiry date for {org_code}: {parts[2]}")
            
            codes[org_code] = (invitation_code, expiry)
    
    return codes


def validate_invitation_code(org_code: str, invitation_code: str) -> bool:
    """
    Validate invitation code for an organization
    
    Returns True if valid and not expired, False otherwise
    """
    codes = load_invitation_codes()
    
    if org_code not in codes:
        return False
    
    stored_code, expiry = codes[org_code]
    
    # Check code match (case-insensitive)
    if stored_code.upper() != invitation_code.upper():
        return False
    
    # Check expiry
    if expiry and datetime.now() > expiry:
        logger.warning(f"Invitation code expired for {org_code}")
        return False
    
    return True


# ============================================================================
# Rate Limiting & Security
# ============================================================================

# In-memory storage for rate limiting
# For production with multiple servers, use Redis
login_attempts: Dict[str, list] = defaultdict(list)
ip_attempts: Dict[str, list] = defaultdict(list)
captcha_attempts: Dict[str, list] = defaultdict(list)


def check_rate_limit(
    identifier: str,
    attempts_dict: Dict[str, list],
    max_attempts: int
) -> Tuple[bool, str]:
    """
    Check if rate limit is exceeded
    
    Args:
        identifier: Phone number or IP address
        attempts_dict: Dictionary tracking attempts
        max_attempts: Maximum attempts allowed
    
    Returns:
        (is_allowed, error_message)
    """
    now = time.time()
    window_start = now - (RATE_LIMIT_WINDOW_MINUTES * 60)
    
    # Get recent attempts
    recent_attempts = [t for t in attempts_dict[identifier] if t > window_start]
    attempts_dict[identifier] = recent_attempts
    
    if len(recent_attempts) >= max_attempts:
        minutes_left = int((recent_attempts[0] + (RATE_LIMIT_WINDOW_MINUTES * 60) - now) / 60) + 1
        return False, f"Too many attempts. Try again in {minutes_left} minutes."
    
    return True, ""


def record_failed_attempt(identifier: str, attempts_dict: Dict[str, list]):
    """Record a failed attempt"""
    attempts_dict[identifier].append(time.time())


def clear_attempts(identifier: str, attempts_dict: Dict[str, list]):
    """Clear attempts on successful action"""
    if identifier in attempts_dict:
        del attempts_dict[identifier]


# ============================================================================
# Account Lockout
# ============================================================================

def check_account_lockout(user: User) -> Tuple[bool, str]:
    """
    Check if user account is locked
    
    Returns:
        (is_locked, error_message)
    """
    if user.locked_until and user.locked_until > datetime.utcnow():
        minutes_left = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
        return True, f"Account locked. Try again in {minutes_left} minutes."
    
    return False, ""


def lock_account(user: User, db: Session):
    """Lock user account for LOCKOUT_DURATION_MINUTES"""
    user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
    db.commit()
    logger.warning(f"Account locked: {user.phone}")


def reset_failed_attempts(user: User, db: Session):
    """Reset failed login attempts on successful login"""
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    db.commit()


def increment_failed_attempts(user: User, db: Session):
    """Increment failed login attempts"""
    user.failed_login_attempts += 1
    db.commit()
    
    if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
        lock_account(user, db)


# ============================================================================
# Admin Check
# ============================================================================

def is_admin(current_user: User) -> bool:
    """Check if user is admin based on phone number"""
    admin_phones = [p.strip() for p in ADMIN_PHONES if p.strip()]
    return current_user.phone in admin_phones

