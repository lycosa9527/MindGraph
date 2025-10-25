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
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.orm import Session

from models.auth import User, Organization, APIKey
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

# bcrypt configuration
BCRYPT_ROUNDS = 12


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt 5.0+ directly
    
    Handles bcrypt's 72-byte limit by truncating if necessary.
    Uses bcrypt directly (no passlib wrapper) for better compatibility.
    
    Args:
        password: Plain text password to hash
        
    Returns:
        Bcrypt hash string (UTF-8 decoded)
        
    Raises:
        Exception: If hashing fails
    """
    # Ensure password is a string
    if not isinstance(password, str):
        password = str(password)
    
    # Convert to bytes and truncate to bcrypt's 72-byte limit if needed
    password_bytes = password.encode('utf-8')
    
    if len(password_bytes) > 72:
        # Truncate to 71 bytes for multi-byte character safety
        password_bytes = password_bytes[:71]
        password_decoded = password_bytes.decode('utf-8', errors='ignore')
        
        # Ensure result is actually under 72 bytes after re-encoding
        while len(password_decoded.encode('utf-8')) > 72:
            password_decoded = password_decoded[:-1]
        
        password_bytes = password_decoded.encode('utf-8')
        logger.warning(f"Password truncated to {len(password_bytes)} bytes for bcrypt compatibility")
    
    try:
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Password hashing failed: {e}")
        logger.error(f"Password length: {len(password)} chars, {len(password_bytes)} bytes")
        raise


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a bcrypt hash
    
    Handles errors gracefully:
    - Corrupted password hashes in database
    - Bcrypt 72-byte limit
    - Invalid hash formats
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hash string from database
        
    Returns:
        True if password matches, False otherwise
    """
    try:
        # Ensure password is a string
        if not isinstance(plain_password, str):
            plain_password = str(plain_password)
        
        # Apply same truncation logic as hash_password
        password_bytes = plain_password.encode('utf-8')
        
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:71]
            password_decoded = password_bytes.decode('utf-8', errors='ignore')
            
            while len(password_decoded.encode('utf-8')) > 72:
                password_decoded = password_decoded[:-1]
            
            password_bytes = password_decoded.encode('utf-8')
            logger.warning(f"Password truncated during verification")
        
        # Verify password against hash
        return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification failed: {e}")
        return False


# ============================================================================
# JWT Token Management
# ============================================================================

security = HTTPBearer(auto_error=False)

# API Key security scheme for public API
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


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
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token required for this endpoint"
        )
    
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


def get_user_from_cookie(token: str, db: Session) -> Optional[User]:
    """
    Get user from cookie token without HTTPBearer dependency
    
    Used for page routes to verify authentication from cookies.
    Returns User if valid token, None if invalid/expired.
    """
    if not token:
        return None
    
    try:
        # Decode token
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        
        if not user_id:
            return None
        
        # Get user from database
        user = db.query(User).filter(User.id == int(user_id)).first()
        return user
        
    except JWTError:
        logger.debug("Invalid or expired cookie token")
        return None
    except Exception as e:
        logger.error(f"Error validating cookie token: {e}")
        return None


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
    """
    Check if user is admin
    
    Admin access granted if:
    1. User phone in ADMIN_PHONES env variable (production admins)
    2. User is demo-admin@system.com AND server is in demo mode (demo admin)
    
    This ensures demo admin passkey only works in demo mode for security.
    """
    # Check ADMIN_PHONES list (production admins)
    admin_phones = [p.strip() for p in ADMIN_PHONES if p.strip()]
    if current_user.phone in admin_phones:
        return True
    
    # Check demo admin (only in demo mode for security)
    if AUTH_MODE == "demo" and current_user.phone == "demo-admin@system.com":
        return True
    
    return False


# ============================================================================
# API Key Management
# ============================================================================

def validate_api_key(api_key: str, db: Session) -> bool:
    """
    Validate API key and check quota
    
    Returns True if valid and within quota
    Raises HTTPException if quota exceeded
    Returns False if invalid
    """
    if not api_key:
        return False
    
    # Query database for key
    key_record = db.query(APIKey).filter(
        APIKey.key == api_key,
        APIKey.is_active == True
    ).first()
    
    if not key_record:
        logger.warning(f"Invalid API key attempted: {api_key[:12]}...")
        return False
    
    # Check expiration
    if key_record.expires_at and key_record.expires_at < datetime.utcnow():
        logger.warning(f"Expired API key used: {key_record.name}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired"
        )
    
    # Check quota
    if key_record.quota_limit and key_record.usage_count >= key_record.quota_limit:
        logger.warning(f"API key quota exceeded: {key_record.name}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"API key quota exceeded. Limit: {key_record.quota_limit}"
        )
    
    return True


def track_api_key_usage(api_key: str, db: Session):
    """Increment usage counter for API key"""
    key_record = db.query(APIKey).filter(APIKey.key == api_key).first()
    if key_record:
        key_record.usage_count += 1
        key_record.last_used_at = datetime.utcnow()
        db.commit()
        logger.info(f"API key used: {key_record.name} (usage: {key_record.usage_count}/{key_record.quota_limit or 'unlimited'})")


def get_current_user_or_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    api_key: str = Depends(api_key_header),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user from JWT token OR validate API key
    
    Priority:
    1. JWT token (authenticated teachers) - Returns User object
    2. API key (Dify, public API) - Returns None (but validates key)
    3. No auth - Raises 401 error
    
    Returns:
        User object if JWT valid, None if API key valid
    
    Raises:
        HTTPException(401) if both invalid
    """
    # Priority 1: Try JWT token (for authenticated teachers)
    if credentials:
        try:
            token = credentials.credentials
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            
            if user_id:
                user = db.query(User).filter(User.id == int(user_id)).first()
                if user:
                    logger.info(f"Authenticated teacher: {user.name}")
                    return user  # Authenticated teacher - full access
        except HTTPException:
            # Invalid JWT, try API key instead
            pass
    
    # Priority 2: Try API key (for Dify, public API users)
    if api_key:
        if validate_api_key(api_key, db):
            track_api_key_usage(api_key, db)
            logger.info(f"Valid API key access")
            return None  # Valid API key, no user object
    
    # No valid authentication
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: provide JWT token (Authorization: Bearer) or API key (X-API-Key header)"
    )


def generate_api_key(name: str, description: str, quota_limit: int, db: Session) -> str:
    """
    Generate a new API key
    
    Args:
        name: Name for the key (e.g., "Dify Integration")
        description: Description of the key's purpose
        quota_limit: Maximum number of requests (None = unlimited)
        db: Database session
    
    Returns:
        Generated API key string (mg_...)
    """
    import secrets
    
    # Generate secure random key with MindGraph prefix
    key = f"mg_{secrets.token_urlsafe(32)}"
    
    # Create database record
    api_key_record = APIKey(
        key=key,
        name=name,
        description=description,
        quota_limit=quota_limit,
        usage_count=0,
        is_active=True,
        created_at=datetime.utcnow()
    )
    
    db.add(api_key_record)
    db.commit()
    db.refresh(api_key_record)
    
    logger.info(f"Generated API key: {name} (quota: {quota_limit or 'unlimited'})")
    
    return key


# ============================================================================
# WebSocket Authentication
# ============================================================================

async def get_current_user_ws(
    websocket,  # WebSocket type imported later to avoid circular imports
    db: Session = Depends(get_db)
) -> User:
    """
    Get current user from WebSocket connection.
    Extracts JWT from query params or cookies.
    
    Args:
        websocket: WebSocket connection
        db: Database session
    
    Returns:
        User object if authenticated
    
    Raises:
        WebSocketDisconnect if authentication fails
    """
    from fastapi import WebSocket
    from fastapi.exceptions import WebSocketDisconnect
    
    # Try query params first
    token = websocket.query_params.get('token')
    
    # Try cookies if no token in query
    if not token:
        token = websocket.cookies.get('access_token')
    
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        raise WebSocketDisconnect(code=4001, reason="No token provided")
    
    try:
        # Decode and validate token
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            await websocket.close(code=4001, reason="Invalid token")
            raise WebSocketDisconnect(code=4001, reason="Invalid token")
        
        # Get user from database
        user = db.query(User).filter(User.id == int(user_id)).first()
        
        if not user:
            await websocket.close(code=4001, reason="User not found")
            raise WebSocketDisconnect(code=4001, reason="User not found")
        
        return user
        
    except HTTPException as e:
        await websocket.close(code=4001, reason="Invalid token")
        raise WebSocketDisconnect(code=4001, reason=str(e.detail))

