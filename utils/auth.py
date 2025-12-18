"""
Authentication Utilities for MindGraph
Author: lycosa9527
Made by: MindSpring Team

JWT tokens, password hashing, rate limiting, and security functions.
"""

import os
import time
import json
import hashlib
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from collections import defaultdict
from urllib.parse import unquote

from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.orm import Session
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

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

# Reverse Proxy Configuration
TRUSTED_PROXY_IPS = os.getenv("TRUSTED_PROXY_IPS", "").split(",") if os.getenv("TRUSTED_PROXY_IPS") else []

# Authentication Mode
AUTH_MODE = os.getenv("AUTH_MODE", "standard").strip().lower()  # standard, enterprise, demo, bayi

# Enterprise Mode Configuration
ENTERPRISE_DEFAULT_ORG_CODE = os.getenv("ENTERPRISE_DEFAULT_ORG_CODE", "DEMO-001").strip()
ENTERPRISE_DEFAULT_USER_PHONE = os.getenv("ENTERPRISE_DEFAULT_USER_PHONE", "enterprise@system.com").strip()

# Demo Mode Configuration
DEMO_PASSKEY = os.getenv("DEMO_PASSKEY", "888888").strip()
ADMIN_DEMO_PASSKEY = os.getenv("ADMIN_DEMO_PASSKEY", "999999").strip()

# Bayi Mode Configuration
BAYI_DECRYPTION_KEY = os.getenv("BAYI_DECRYPTION_KEY", "v8IT7XujLPsM7FYuDPRhPtZk").strip()
BAYI_DEFAULT_ORG_CODE = os.getenv("BAYI_DEFAULT_ORG_CODE", "BAYI-001").strip()
BAYI_CLOCK_SKEW_TOLERANCE = int(os.getenv("BAYI_CLOCK_SKEW_TOLERANCE", "10"))  # Allow 10 seconds clock skew tolerance

# Bayi IP Whitelist Configuration (Option 1: Simple In-Memory Set)
BAYI_IP_WHITELIST_STR = os.getenv("BAYI_IP_WHITELIST", "").strip()
BAYI_IP_WHITELIST = set()  # Set of whitelisted IP addresses

# ============================================================================
# Cookie Security Helpers
# ============================================================================

def is_https(request: Request) -> bool:
    """
    Detect if request is over HTTPS
    
    Checks multiple sources:
    1. X-Forwarded-Proto header (set by reverse proxy like Nginx)
    2. Request URL scheme
    3. FORCE_SECURE_COOKIES environment variable (for production)
    
    Returns:
        True if HTTPS detected, False otherwise
    """
    # Check X-Forwarded-Proto header (set by reverse proxy)
    forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
    if forwarded_proto == "https":
        return True
    
    # Check if URL scheme is https
    if hasattr(request.url, 'scheme') and request.url.scheme == "https":
        return True
    
    # Check environment variable for production mode (force secure cookies)
    if os.getenv("FORCE_SECURE_COOKIES", "").lower() == "true":
        return True
    
    return False

# Parse IP whitelist on startup (only log if in bayi mode)
if BAYI_IP_WHITELIST_STR:
    for ip_entry in BAYI_IP_WHITELIST_STR.split(","):
        ip_entry = ip_entry.strip()
        if not ip_entry:
            continue
        try:
            # Validate and normalize IP address
            import ipaddress
            ip_addr = ipaddress.ip_address(ip_entry)
            BAYI_IP_WHITELIST.add(str(ip_addr))
            # Only log in bayi mode to avoid noise in other modes
            if AUTH_MODE == "bayi":
                logger.info(f"Added IP to bayi IP whitelist: {ip_entry}")
        except ValueError as e:
            if AUTH_MODE == "bayi":
                logger.warning(f"Invalid IP entry in BAYI_IP_WHITELIST: {ip_entry} - {e}")
    
    if AUTH_MODE == "bayi":
        if BAYI_IP_WHITELIST:
            logger.info(f"Bayi IP whitelist loaded: {len(BAYI_IP_WHITELIST)} IP(s)")
        else:
            logger.info("Bayi IP whitelist configured but no valid IPs found")

# Admin Configuration
ADMIN_PHONES = os.getenv("ADMIN_PHONES", "").split(",")

# Security Configuration
MAX_LOGIN_ATTEMPTS = 10
MAX_CAPTCHA_ATTEMPTS = 30
LOCKOUT_DURATION_MINUTES = 5
RATE_LIMIT_WINDOW_MINUTES = 15
CAPTCHA_SESSION_COOKIE_NAME = "captcha_session"

# ============================================================================
# Reverse Proxy Helpers
# ============================================================================

def get_client_ip(request: Request) -> str:
    """
    Get real client IP address, even behind reverse proxy (nginx, etc.)
    
    Checks headers in order:
    1. X-Forwarded-For (most common, can be comma-separated)
    2. X-Real-IP (nginx specific)
    3. request.client.host (fallback, direct connection)
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Client IP address string
        
    Example:
        With nginx proxy_pass:
        X-Forwarded-For: 203.0.113.45, 198.51.100.178
        Returns: 203.0.113.45 (leftmost = original client)
    """
    # Check X-Forwarded-For header (most common with reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs: "client, proxy1, proxy2"
        # The leftmost is the original client IP
        client_ip = forwarded_for.split(",")[0].strip()
        logger.debug(f"Client IP from X-Forwarded-For: {client_ip} (full: {forwarded_for})")
        return client_ip
    
    # Check X-Real-IP header (nginx-specific)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        logger.debug(f"Client IP from X-Real-IP: {real_ip}")
        return real_ip
    
    # Fallback to direct connection IP
    direct_ip = request.client.host if request.client else "unknown"
    logger.debug(f"Client IP from request.client.host: {direct_ip}")
    return direct_ip

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
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Get current authenticated user from JWT token (Authorization header or cookie)
    
    Supports four authentication modes:
    1. standard: Regular JWT authentication (phone/password login)
    2. enterprise: Skip JWT validation (for VPN/SSO deployments with network-level auth)
    3. demo: Regular JWT authentication (passkey login)
    4. bayi: Regular JWT authentication (token-based login via /loginByXz)
    
    IMPORTANT: Demo and bayi modes still require valid JWT tokens!
    Only enterprise mode bypasses authentication entirely.
    
    Authentication methods (in order of priority):
    1. Authorization: Bearer <token> header
    2. access_token cookie (for cookie-based authentication)
    
    Note:
        This function manages its own database session to avoid holding
        connections during long-running LLM requests. The session is closed
        immediately after auth check, before returning.
    """
    from config.database import SessionLocal
    
    # Enterprise Mode: Skip authentication, return enterprise user
    # This is for deployments behind VPN/SSO where network auth is sufficient
    if AUTH_MODE == "enterprise":
        db = SessionLocal()
        try:
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
            
            # Detach user from session so it can be used after close
            db.expunge(user)
            return user
        finally:
            db.close()  # Release connection immediately
    
    # Standard, Demo, and Bayi Mode: Validate JWT token
    # Demo mode uses passkey for login, bayi mode uses token decryption via /loginByXz
    # Both still require valid JWT tokens for API access
    
    token = None
    
    # Priority 1: Check Authorization header
    if credentials:
        token = credentials.credentials
    # Priority 2: Check cookie if no Authorization header
    elif request:
        token = request.cookies.get("access_token")
    
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token required for this endpoint"
        )
    
    payload = decode_access_token(token)
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Create session, query, and close immediately
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == int(user_id)).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Check organization status (locked or expired)
        if user.organization_id:
            org = db.query(Organization).filter(Organization.id == user.organization_id).first()
            if org:
                # Check if organization is locked
                is_active = org.is_active if hasattr(org, 'is_active') else True
                if not is_active:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Organization account is locked. Please contact support."
                    )
                
                # Check if organization subscription has expired
                if hasattr(org, 'expires_at') and org.expires_at:
                    if org.expires_at < datetime.utcnow():
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="Organization subscription has expired. Please contact support."
                        )
        
        # Detach user from session so it can be used after close
        db.expunge(user)
        return user
    finally:
        db.close()  # Release connection immediately


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
# Bayi Mode Token Decryption
# ============================================================================

def decrypt_bayi_token(encrypted_token: str, key: str) -> dict:
    """
    Decrypt bayi token using AES-ECB mode (compatible with CryptoJS)
    
    Args:
        encrypted_token: URL-encoded encrypted token string
        key: Decryption key (will be hashed with SHA256)
    
    Returns:
        Decrypted JSON object as dict
    
    Raises:
        ValueError: If decryption fails or token is invalid
    """
    try:
        # Decode URL encoding (FastAPI already decodes query params, but this is safe for double-encoding)
        token = unquote(encrypted_token)
        logger.debug(f"Decrypting bayi token - length: {len(token)}, ends with '==': {token.endswith('==')}")
        
        # Generate secret key using SHA256 (same as CryptoJS)
        secret_key = hashlib.sha256(key.encode('utf-8')).digest()
        
        # Decode base64 token (CryptoJS uses base64 encoding)
        try:
            encrypted_bytes = base64.b64decode(token, validate=True)
            logger.debug(f"Base64 decoded successfully - encrypted bytes length: {len(encrypted_bytes)}")
        except Exception as e:
            logger.error(f"Base64 decode failed: {e}, token preview: {token[:50]}")
            raise ValueError(f"Invalid base64 token: {str(e)}")
        
        # Decrypt using AES-ECB mode
        cipher = AES.new(secret_key, AES.MODE_ECB)
        decrypted_bytes = cipher.decrypt(encrypted_bytes)
        logger.debug(f"Decryption successful - decrypted bytes length: {len(decrypted_bytes)}")
        
        # Remove PKCS7 padding
        try:
            decrypted_text = unpad(decrypted_bytes, AES.block_size).decode('utf-8')
            logger.debug(f"Unpadded successfully - decrypted text length: {len(decrypted_text)}")
        except Exception as e:
            logger.error(f"Unpad failed: {e}, decrypted bytes preview: {decrypted_bytes[:50]}")
            raise ValueError(f"Padding removal failed: {str(e)}")
        
        # Parse JSON
        try:
            result = json.loads(decrypted_text)
            logger.debug(f"JSON parsed successfully - keys: {list(result.keys())}")
            return result
        except Exception as e:
            logger.error(f"JSON parse failed: {e}, decrypted text: {decrypted_text[:200]}")
            raise ValueError(f"Invalid JSON in token: {str(e)}")
    except ValueError:
        # Re-raise ValueError as-is (these are our validation errors)
        raise
    except Exception as e:
        logger.error(f"Bayi token decryption failed: {e}", exc_info=True)
        raise ValueError(f"Invalid token: {str(e)}")


def validate_bayi_token_body(body: dict) -> bool:
    """
    Validate decrypted bayi token body
    
    Checks:
    - body.from === 'bayi'
    - timestamp is within last 5 minutes (with clock skew tolerance)
    
    Args:
        body: Decrypted token body
    
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(body, dict):
        return False
    
    # Check 'from' field
    if body.get('from') != 'bayi':
        logger.warning(f"Bayi token validation failed: 'from' field is '{body.get('from')}', expected 'bayi'")
        return False
    
    # Check timestamp (must be within last 5 minutes)
    timestamp = body.get('timestamp')
    if not timestamp:
        logger.warning("Bayi token validation failed: missing timestamp")
        return False
    
    try:
        # Convert timestamp to datetime (Unix timestamps are always UTC)
        if isinstance(timestamp, (int, float)):
            # Use utcfromtimestamp to ensure UTC comparison
            token_time = datetime.utcfromtimestamp(timestamp)
        elif isinstance(timestamp, str):
            # Try parsing as ISO format or Unix timestamp
            try:
                token_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                # If no timezone info, assume UTC
                if token_time.tzinfo is None:
                    token_time = token_time.replace(tzinfo=None)  # Treat as UTC naive datetime
            except ValueError:
                token_time = datetime.utcfromtimestamp(float(timestamp))
        else:
            logger.warning(f"Bayi token validation failed: invalid timestamp type: {type(timestamp)}")
            return False
        
        # Check if timestamp is within last 5 minutes (both in UTC)
        # Allow small clock skew tolerance for future timestamps (network latency, minor clock differences)
        now = datetime.utcnow()
        time_diff = (now - token_time).total_seconds()
        
        logger.debug(f"Timestamp validation - now (UTC): {now}, token_time (UTC): {token_time}, diff: {time_diff}s ({time_diff/60:.1f} minutes)")
        
        # Allow tokens slightly in the future (within clock skew tolerance)
        # This handles minor clock synchronization differences and network latency
        if time_diff < -BAYI_CLOCK_SKEW_TOLERANCE:
            logger.warning(f"Bayi token validation failed: timestamp is too far in the future (diff: {time_diff}s, tolerance: {BAYI_CLOCK_SKEW_TOLERANCE}s, now: {now}, token_time: {token_time})")
            return False
        
        # Log but allow tokens within clock skew tolerance (future but acceptable)
        if time_diff < 0:
            logger.debug(f"Bayi token timestamp is slightly in the future but within tolerance (diff: {time_diff}s, tolerance: {BAYI_CLOCK_SKEW_TOLERANCE}s)")
        
        if time_diff > 300:  # 5 minutes = 300 seconds
            logger.warning(f"Bayi token validation failed: timestamp expired (diff: {time_diff}s = {time_diff/60:.1f} minutes, now: {now}, token_time: {token_time})")
            return False
        
        logger.debug(f"Timestamp validation passed - diff: {time_diff}s")
        return True
    except Exception as e:
        logger.error(f"Bayi token timestamp validation error: {e}")
        return False


# ============================================================================
# Bayi IP Whitelist Functions
# ============================================================================

def is_ip_whitelisted(client_ip: str) -> bool:
    """
    Check if client IP is in bayi IP whitelist.
    
    If IP is whitelisted, teachers from that IP can skip token authentication
    and gain immediate access in bayi mode.
    
    Args:
        client_ip: Client IP address string
    
    Returns:
        True if IP is whitelisted, False otherwise
    """
    if not BAYI_IP_WHITELIST:
        return False
    
    try:
        import ipaddress
        # Normalize IP address for comparison
        ip_addr = ipaddress.ip_address(client_ip)
        ip_str = str(ip_addr)
        
        # O(1) lookup in set
        if ip_str in BAYI_IP_WHITELIST:
            logger.debug(f"IP {client_ip} matched whitelist entry")
            return True
        
        return False
    except ValueError:
        logger.warning(f"Invalid IP address format: {client_ip}")
        return False


# ============================================================================
# Invitation Code Management
# ============================================================================

def load_invitation_codes() -> Dict[str, Tuple[str, Optional[datetime]]]:
    """
    Load invitation codes from environment variable
    
    Format: ORG_CODE:INVITATION_CODE:EXPIRY_DATE
    Invitation code format: AAAA-XXXXX (4 uppercase letters, dash, 5 uppercase letters/digits)
    Example: DEMO-001:DEMO-A1B2C:2025-12-31,SPRING-EDU:SPRN-9K2L1:never
    
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
captcha_session_attempts: Dict[str, list] = defaultdict(list)


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
        attempts_made = len(recent_attempts)
        if minutes_left == 1:
            return False, f"Too many login attempts ({attempts_made} attempts in {RATE_LIMIT_WINDOW_MINUTES} minutes). Please try again in {minutes_left} minute."
        return False, f"Too many login attempts ({attempts_made} attempts in {RATE_LIMIT_WINDOW_MINUTES} minutes). Please try again in {minutes_left} minutes."
    
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
        seconds_left = int((user.locked_until - datetime.utcnow()).total_seconds())
        minutes_left = (seconds_left // 60) + 1
        if minutes_left == 1:
            return True, f"Account temporarily locked due to too many failed attempts. Please try again in {minutes_left} minute."
        return True, f"Account temporarily locked due to too many failed attempts. Please try again in {minutes_left} minutes."
    
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
    3. User is bayi-admin@system.com AND server is in bayi mode (bayi admin)
    
    This ensures demo/bayi admin passkey only works in their respective modes for security.
    """
    # Check ADMIN_PHONES list (production admins)
    admin_phones = [p.strip() for p in ADMIN_PHONES if p.strip()]
    if current_user.phone in admin_phones:
        return True
    
    # Check demo admin (only in demo mode for security)
    if AUTH_MODE == "demo" and current_user.phone == "demo-admin@system.com":
        return True
    
    # Check bayi admin (only in bayi mode for security)
    if AUTH_MODE == "bayi" and current_user.phone == "bayi-admin@system.com":
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
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    api_key: str = Depends(api_key_header)
) -> Optional[User]:
    """
    Get current user from JWT token OR validate API key
    
    Priority:
    1. JWT token (Authorization header or cookie) - Returns User object
    2. API key (Dify, public API) - Returns None (but validates key)
    3. No auth - Raises 401 error
    
    Returns:
        User object if JWT valid, None if API key valid
    
    Raises:
        HTTPException(401) if both invalid
    
    Note:
        This function manages its own database session to avoid holding
        connections during long-running LLM requests. The session is closed
        immediately after auth check, before returning.
    """
    from config.database import SessionLocal
    
    # Priority 1: Try JWT token (for authenticated teachers)
    token = None
    
    # Check Authorization header first
    if credentials:
        token = credentials.credentials
    # Check cookie if no Authorization header
    elif request:
        token = request.cookies.get("access_token")
    
    if token:
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")
            
            if user_id:
                # Create session, query, and close immediately
                db = SessionLocal()
                try:
                    user = db.query(User).filter(User.id == int(user_id)).first()
                    if user:
                        # Detach user from session so it can be used after close
                        db.expunge(user)
                        worker_id = os.getenv('UVICORN_WORKER_ID', 'main')
                        # Include endpoint path for clarity when multiple parallel requests come in
                        endpoint = request.url.path if request else 'unknown'
                        logger.debug(f"Authenticated teacher: {user.name} (ID: {user.id}, Phone: {user.phone}) [Worker: {worker_id}] [{endpoint}]")
                        return user  # Authenticated teacher - full access
                finally:
                    db.close()  # Release connection immediately
        except HTTPException:
            # Invalid JWT, try API key instead
            pass
    
    # Priority 2: Try API key (for Dify, public API users)
    if api_key:
        # Create session for API key validation
        db = SessionLocal()
        try:
            if validate_api_key(api_key, db):
                track_api_key_usage(api_key, db)
                logger.info(f"Valid API key access")
                return None  # Valid API key, no user object
        finally:
            db.close()  # Release connection immediately
    
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

