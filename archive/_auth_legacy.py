"""
Authentication Utilities for MindGraph
Author: lycosa9527
Made by: MindSpring Team

JWT tokens, password hashing, rate limiting, and security functions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from urllib.parse import unquote
import base64
import hashlib
import ipaddress
import json
import logging
import os
import secrets
import time
import uuid

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from fastapi.websockets import WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy.orm import Session
import bcrypt

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
except ImportError:
    AES = None
    unpad = None

from config.database import SessionLocal, get_db
from models.auth import User, Organization, APIKey

# Lazy imports for Redis modules (to avoid circular imports)
# These are imported conditionally inside functions when needed
try:
    from services.redis.redis_client import get_redis, is_redis_available
    from services.redis.redis_org_cache import org_cache
    from services.redis.redis_user_cache import user_cache
    from services.redis.redis_session_manager import get_session_manager, _hash_token
    from services.redis.redis_bayi_whitelist import get_bayi_whitelist
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False
    get_redis = None
    is_redis_available = None
    org_cache = None
    user_cache = None
    get_session_manager = None
    _hash_token = None
    get_bayi_whitelist = None





logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# JWT Configuration
JWT_ALGORITHM = "HS256"
# Redis key for JWT secret storage
_JWT_SECRET_REDIS_KEY = "jwt:secret"
# Cached JWT secret (to avoid Redis lookup on every request)
_jwt_secret_cache: Optional[str] = None
# File path for JWT secret backup (for recovery after Redis flush)
_JWT_SECRET_BACKUP_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", ".jwt_secret")


def _save_jwt_secret_backup(secret: str) -> bool:
    """
    Save JWT secret to a file for backup/recovery.

    This allows recovery after Redis flush without invalidating all user tokens.
    The file is stored in the data directory with restricted permissions.

    Args:
        secret: JWT secret to backup

    Returns:
        True if saved successfully, False otherwise
    """
    try:
        # Ensure data directory exists
        data_dir = os.path.dirname(_JWT_SECRET_BACKUP_FILE)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)

        # Write secret to file with restricted permissions
        with open(_JWT_SECRET_BACKUP_FILE, 'w', encoding='utf-8') as f:
            f.write(secret)

        # Set file permissions to owner-only (Unix)
        try:
            os.chmod(_JWT_SECRET_BACKUP_FILE, 0o600)
        except (OSError, AttributeError):
            # Windows doesn't support chmod, skip
            pass

        logger.info("[Auth] JWT secret backed up to file")
        return True
    except Exception as e:
        logger.warning("[Auth] Failed to backup JWT secret to file: %s", e)
        return False


def _load_jwt_secret_backup() -> Optional[str]:
    """
    Load JWT secret from backup file.

    Returns:
        JWT secret if found and valid, None otherwise
    """
    try:
        if not os.path.exists(_JWT_SECRET_BACKUP_FILE):
            return None

        with open(_JWT_SECRET_BACKUP_FILE, 'r', encoding='utf-8') as f:
            secret = f.read().strip()

        # Validate secret format (should be URL-safe base64)
        if secret and len(secret) >= 32:
            logger.info("[Auth] Restored JWT secret from backup file")
            return secret

        return None
    except Exception as e:
        logger.warning("[Auth] Failed to load JWT secret backup: %s", e)
        return None


def get_jwt_secret() -> str:
    """
    Get or generate JWT secret from Redis (shared across all workers).

    Security benefits:
    - Auto-generated cryptographically secure 64-char secret
    - Shared across all workers via Redis (multi-worker safe)
    - No manual configuration required (removed from .env)
    - Persistent backup to file for recovery after Redis flush
    - Users only re-login if both Redis AND backup file are lost (very rare)

    Uses SET NX (set if not exists) to ensure only one worker generates
    the secret, preventing race conditions.

    Returns:
        JWT secret string (64 chars, cryptographically secure)
    """
    global _jwt_secret_cache
    # Return cached value if available (avoids Redis lookup on every JWT operation)
    if _jwt_secret_cache:
        return _jwt_secret_cache

    if not _REDIS_AVAILABLE:
        raise RuntimeError(
            "Redis client not available. Redis is required for JWT secret storage."
        )

    if is_redis_available is None:
        raise RuntimeError("is_redis_available function not available")
    if get_redis is None:
        raise RuntimeError("get_redis function not available")

    try:
        if not is_redis_available():
            # Redis required - fail with clear error
            raise RuntimeError(
                "Redis is required for JWT secret storage. "
                "Please ensure Redis is running and REDIS_URL is configured."
            )

        redis = get_redis()
        if not redis:
            raise RuntimeError("Failed to connect to Redis for JWT secret retrieval")

        # Try to get existing secret from Redis
        secret = redis.get(_JWT_SECRET_REDIS_KEY)
        if secret:
            # Handle both bytes and string (depends on Redis client decode_responses setting)
            secret_str = secret.decode('utf-8') if isinstance(secret, bytes) else secret
            # Update global cache
            _jwt_secret_cache = secret_str
            logger.debug("[Auth] Retrieved JWT secret from Redis")
            return secret_str

        # Redis doesn't have the secret - try to restore from backup
        backup_secret = _load_jwt_secret_backup()
        if backup_secret:
            # Restore to Redis (atomic set-if-not-exists)
            if redis.set(_JWT_SECRET_REDIS_KEY, backup_secret, nx=True):
                logger.info("[Auth] Restored JWT secret from backup to Redis")
                _jwt_secret_cache = backup_secret
                return backup_secret

            # Another worker restored it first, fetch theirs
            secret = redis.get(_JWT_SECRET_REDIS_KEY)
            if secret:
                secret_str = secret.decode('utf-8') if isinstance(secret, bytes) else secret
                _jwt_secret_cache = secret_str
                return secret_str

        # Generate new secret (SET NX ensures only one worker creates it)
        new_secret = secrets.token_urlsafe(48)  # 64 chars, cryptographically secure

        # Atomic set-if-not-exists to handle race condition
        if redis.set(_JWT_SECRET_REDIS_KEY, new_secret, nx=True):
            logger.info("[Auth] Generated new JWT secret (stored in Redis)")
            _jwt_secret_cache = new_secret
            # Backup to file for future recovery
            _save_jwt_secret_backup(new_secret)
            return new_secret

        # Another worker created it first, fetch theirs
        secret = redis.get(_JWT_SECRET_REDIS_KEY)
        if secret:
            # Handle both bytes and string (depends on Redis client decode_responses setting)
            secret_str = secret.decode('utf-8') if isinstance(secret, bytes) else secret
            _jwt_secret_cache = secret_str
            # Backup to file (in case they didn't)
            _save_jwt_secret_backup(secret_str)
            return secret_str

        # Should never happen, but handle gracefully
        raise RuntimeError("Failed to retrieve or generate JWT secret from Redis")

    except ImportError as exc:
        raise RuntimeError(
            "Redis client not available. Redis is required for JWT secret storage."
        ) from exc
    except Exception as e:
        logger.error("[Auth] JWT secret retrieval failed: %s", e)
        raise
# Access token: Short-lived (1 hour default), refreshed automatically
ACCESS_TOKEN_EXPIRY_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRY_MINUTES", "60"))
# Refresh token: Long-lived (7 days default), stored in httpOnly cookie
REFRESH_TOKEN_EXPIRY_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRY_DAYS", "7"))
# Legacy - kept for backward compatibility during transition
JWT_EXPIRY_HOURS = ACCESS_TOKEN_EXPIRY_MINUTES // 60 if ACCESS_TOKEN_EXPIRY_MINUTES >= 60 else 1

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

# Public Dashboard Configuration
PUBLIC_DASHBOARD_PASSKEY = os.getenv("PUBLIC_DASHBOARD_PASSKEY", "123456").strip()

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
            ip_addr_obj = ipaddress.ip_address(ip_entry)
            BAYI_IP_WHITELIST.add(str(ip_addr_obj))
            # Only log in bayi mode to avoid noise in other modes
            if AUTH_MODE == "bayi":
                logger.info("Added IP to bayi IP whitelist: %s", ip_entry)
        except ValueError as e:
            if AUTH_MODE == "bayi":
                logger.warning("Invalid IP entry in BAYI_IP_WHITELIST: %s - %s", ip_entry, e)

    if AUTH_MODE == "bayi":
        if BAYI_IP_WHITELIST:
            logger.info("Bayi IP whitelist loaded: %d IP(s)", len(BAYI_IP_WHITELIST))
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
        logger.debug("Client IP from X-Forwarded-For: %s (full: %s)", client_ip, forwarded_for)
        return client_ip

    # Check X-Real-IP header (nginx-specific)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        logger.debug("Client IP from X-Real-IP: %s", real_ip)
        return real_ip

    # Fallback to direct connection IP
    direct_ip = request.client.host if request.client else "unknown"
    logger.debug("Client IP from request.client.host: %s", direct_ip)
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
        logger.warning("Password truncated to %d bytes for bcrypt compatibility", len(password_bytes))

    try:
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error("Password hashing failed: %s", e)
        logger.error("Password length: %d chars, %d bytes", len(password), len(password_bytes))
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
            logger.warning("Password truncated during verification")

        # Verify password against hash
        return bcrypt.checkpw(password_bytes, hashed_password.encode('utf-8'))
    except Exception as e:
        logger.error("Password verification failed: %s", e)
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
    - jti: JWT ID (unique token identifier for session tracking)
    - exp: expiration timestamp
    - type: token type (access)
    """
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRY_MINUTES)

    # Generate unique token ID for session tracking
    token_id = str(uuid.uuid4())

    payload = {
        "sub": str(user.id),
        "phone": user.phone,
        "org_id": user.organization_id,
        "jti": token_id,
        "type": "access",
        "exp": expire
    }

    token = jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)
    return token


def create_refresh_token(user_id: int) -> tuple[str, str]:
    """
    Create a secure refresh token

    Args:
        user_id: User ID (kept for API compatibility)

    Returns:
        tuple: (refresh_token, token_hash) - the raw token and its hash for storage
    """
    # user_id parameter kept for API compatibility but not used in implementation
    _ = user_id

    # Generate cryptographically secure random token
    refresh_token = secrets.token_urlsafe(32)

    # Hash for storage (never store the raw token)
    token_hash = hashlib.sha256(refresh_token.encode('utf-8')).hexdigest()

    return refresh_token, token_hash


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for lookup"""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def compute_device_hash(request: Request) -> str:
    """
    Compute a device fingerprint hash from request headers.

    Uses multiple signals for more robust device identification:
    - User-Agent: Browser and OS identification
    - Accept-Language: Language preferences
    - Accept-Encoding: Compression support (stable across sessions)
    - Sec-CH-UA-Platform: Client hint for OS platform (if available)
    - Sec-CH-UA-Mobile: Client hint for mobile/desktop (if available)

    Note: We deliberately exclude IP address as it can change frequently
    (e.g., mobile networks, VPN). The goal is to identify the same browser
    on the same device, not the network location.

    This is not foolproof but adds a layer of security. The hash is
    truncated to 16 characters to balance uniqueness with storage efficiency.
    """
    # Core headers (always present)
    user_agent = request.headers.get("User-Agent", "")
    accept_language = request.headers.get("Accept-Language", "")
    accept_encoding = request.headers.get("Accept-Encoding", "")

    # Client hints (modern browsers only, more stable than User-Agent)
    sec_ch_platform = request.headers.get("Sec-CH-UA-Platform", "")
    sec_ch_mobile = request.headers.get("Sec-CH-UA-Mobile", "")

    # Build fingerprint from stable signals
    fingerprint_parts = [
        user_agent,
        accept_language,
        accept_encoding,
        sec_ch_platform,
        sec_ch_mobile
    ]

    fingerprint = "|".join(fingerprint_parts)
    return hashlib.sha256(fingerprint.encode('utf-8')).hexdigest()[:16]  # pylint: disable=redefined-outer-name


def decode_access_token(token: str) -> dict:
    """
    Decode and validate JWT token

    Returns payload if valid, raises HTTPException if invalid/expired
    """
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        # Token expiration is expected behavior when users are inactive
        # Log at DEBUG level to reduce noise, but still log invalid tokens as WARNING
        error_msg = str(e)
        if "expired" in error_msg.lower() or "exp" in error_msg.lower():
            logger.debug("Token expired: %s (expected when user inactive)", e)
        else:
            logger.warning("Invalid token: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        ) from e


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
    # Enterprise Mode: Skip authentication, return enterprise user
    # This is for deployments behind VPN/SSO where network auth is sufficient
    if AUTH_MODE == "enterprise":
        db = SessionLocal()
        try:
            # Use cache for org lookup (with SQLite fallback)
            if not _REDIS_AVAILABLE or org_cache is None:
                org = None
            else:
                org = org_cache.get_by_code(ENTERPRISE_DEFAULT_ORG_CODE)
            if not org:
                org = db.query(Organization).filter(
                    Organization.code == ENTERPRISE_DEFAULT_ORG_CODE
                ).first()
                if not org:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Enterprise organization {ENTERPRISE_DEFAULT_ORG_CODE} not found"
                    )

            # Use cache for user lookup (with SQLite fallback)
            user = None
            if _REDIS_AVAILABLE and user_cache:
                user = user_cache.get_by_phone(ENTERPRISE_DEFAULT_USER_PHONE)

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

                # Cache the newly created user (non-blocking)
                try:
                    if _REDIS_AVAILABLE and user_cache:
                        user_cache.cache_user(user)
                except Exception as e:
                    logger.warning("Failed to cache enterprise user: %s", e)

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
    token_exp = payload.get("exp", 0)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    # Session validation: Check if session exists in Redis
    if not _REDIS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is required for session validation"
        )
    if get_session_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session manager not available"
        )
    if _hash_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token hashing not available"
        )
    session_manager = get_session_manager()
    token_hash = _hash_token(token)

    # DEBUG: Log session validation attempt
    now = int(time.time())
    exp_info = f"exp={token_exp}, expired_ago={(now - token_exp) if token_exp > 0 else 'unknown'}s"
    logger.info("[Auth] get_current_user session check: user=%s, token=%s..., %s", user_id, token_hash[:8], exp_info)

    if not session_manager.is_session_valid(int(user_id), token):
        logger.info("[Auth] get_current_user FAILED: user=%s, token=%s... - session invalid", user_id, token_hash[:8])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalidated. Please login again."
        )

    logger.debug("[Auth] get_current_user session VALID: user=%s", user_id)

    # Use cache for user lookup (with SQLite fallback)
    user = None
    if _REDIS_AVAILABLE and user_cache:
        user = user_cache.get_by_id(int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Check organization status (locked or expired) using cache
    if user.organization_id:
        org = None
        if _REDIS_AVAILABLE and org_cache:
            org = org_cache.get_by_id(user.organization_id)
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

    return user


def get_user_from_cookie(token: str, db: Session) -> Optional[User]:
    """
    Get user from cookie token without HTTPBearer dependency

    Used for page routes to verify authentication from cookies.
    Returns User if valid token, None if invalid/expired.

    Note: User object is returned attached to the session. If you need to use
    the user after closing the session, call db.expunge(user) before closing.
    For simple column access (phone, id, name), detached objects work fine.
    """
    if not token:
        return None

    try:
        # Decode token - jwt.decode automatically validates expiration
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")

        if not user_id:
            return None

        # Session validation: Check if session exists in Redis
        if not _REDIS_AVAILABLE:
            return None
        if get_session_manager is None:
            return None
        session_manager = get_session_manager()
        if not session_manager.is_session_valid(int(user_id), token):
            logger.debug("Session invalid for user %s in get_user_from_cookie", user_id)
            return None

        # Use cache for user lookup (with SQLite fallback)
        user = None
        if user_cache:
            user = user_cache.get_by_id(int(user_id))
        if not user:
            # Fallback to DB if not in cache
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                db.expunge(user)
                if user_cache:
                    user_cache.cache_user(user)  # Cache it for next time
        return user

    except JWTError as e:
        # JWTError includes ExpiredSignatureError and other JWT-related errors
        # Log at debug level for expired tokens (expected behavior)
        error_msg = str(e).lower()
        if "expired" in error_msg or "exp" in error_msg:
            logger.debug("Expired cookie token: %s", e)
        else:
            logger.debug("Invalid cookie token: %s", e)
        return None
    except Exception as e:
        logger.error("Error validating cookie token: %s", e, exc_info=True)
        return None


# ============================================================================
# Demo Mode Passkey
# ============================================================================

def display_demo_info():
    """Display demo mode information on startup"""
    if AUTH_MODE == "demo":
        logger.info("=" * 60)
        logger.info("DEMO MODE ACTIVE")
        logger.info("Passkey: %s", DEMO_PASSKEY)
        logger.info("Passkey length: %d characters", len(DEMO_PASSKEY))
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


def verify_dashboard_passkey(passkey: str) -> bool:
    """
    Verify public dashboard passkey
    Returns True if valid, False otherwise
    """
    # Strip whitespace from input passkey to handle client-side issues
    passkey = passkey.strip() if passkey else ""
    return passkey == PUBLIC_DASHBOARD_PASSKEY


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
    if AES is None or unpad is None:
        raise ValueError("pycryptodome is required for bayi token decryption. Install with: pip install pycryptodome")

    try:
        # Decode URL encoding (FastAPI already decodes query params, but this is safe for double-encoding)
        token = unquote(encrypted_token)
        logger.debug("Decrypting bayi token - length: %d, ends with '==': %s", len(token), token.endswith('=='))

        # Generate secret key using SHA256 (same as CryptoJS)
        secret_key = hashlib.sha256(key.encode('utf-8')).digest()

        # Decode base64 token (CryptoJS uses base64 encoding)
        try:
            encrypted_bytes = base64.b64decode(token, validate=True)
            logger.debug("Base64 decoded successfully - encrypted bytes length: %d", len(encrypted_bytes))
        except Exception as e:
            logger.error("Base64 decode failed: %s, token preview: %s", e, token[:50])
            raise ValueError(f"Invalid base64 token: {str(e)}") from e

        # Decrypt using AES-ECB mode
        cipher = AES.new(secret_key, AES.MODE_ECB)
        decrypted_bytes = cipher.decrypt(encrypted_bytes)
        logger.debug("Decryption successful - decrypted bytes length: %d", len(decrypted_bytes))

        # Remove PKCS7 padding
        try:
            decrypted_text = unpad(decrypted_bytes, AES.block_size).decode('utf-8')
            logger.debug("Unpadded successfully - decrypted text length: %d", len(decrypted_text))
        except Exception as e:
            logger.error("Unpad failed: %s, decrypted bytes preview: %s", e, decrypted_bytes[:50])
            raise ValueError(f"Padding removal failed: {str(e)}") from e

        # Parse JSON
        try:
            result = json.loads(decrypted_text)
            logger.debug("JSON parsed successfully - keys: %s", list(result.keys()))
            return result
        except Exception as e:
            logger.error("JSON parse failed: %s, decrypted text: %s", e, decrypted_text[:200])
            raise ValueError(f"Invalid JSON in token: {str(e)}") from e
    except ValueError:
        # Re-raise ValueError as-is (these are our validation errors)
        raise
    except Exception as e:
        logger.error("Bayi token decryption failed: %s", e, exc_info=True)
        raise ValueError(f"Invalid token: {str(e)}") from e


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
        logger.warning("Bayi token validation failed: 'from' field is '%s', expected 'bayi'", body.get('from'))
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
            logger.warning("Bayi token validation failed: invalid timestamp type: %s", type(timestamp))
            return False

        # Check if timestamp is within last 5 minutes (both in UTC)
        # Allow small clock skew tolerance for future timestamps
        # (network latency, minor clock differences)
        now = datetime.utcnow()
        time_diff = (now - token_time).total_seconds()

        logger.debug(
            "Timestamp validation - now (UTC): %s, token_time (UTC): %s, "
            "diff: %ds (%.1f minutes)",
            now, token_time, time_diff, time_diff/60
        )

        # Allow tokens slightly in the future (within clock skew tolerance)
        # This handles minor clock synchronization differences and network latency
        if time_diff < -BAYI_CLOCK_SKEW_TOLERANCE:
            logger.warning(
                "Bayi token validation failed: timestamp is too far in the future "
                "(diff: %ds, tolerance: %ds, now: %s, token_time: %s)",
                time_diff, BAYI_CLOCK_SKEW_TOLERANCE, now, token_time
            )
            return False

        # Log but allow tokens within clock skew tolerance (future but acceptable)
        if time_diff < 0:
            logger.debug(
                "Bayi token timestamp is slightly in the future but within tolerance "
                "(diff: %ds, tolerance: %ds)",
                time_diff, BAYI_CLOCK_SKEW_TOLERANCE
            )

        if time_diff > 300:  # 5 minutes = 300 seconds
            # Token expiration is expected behavior (tokens expire after 5 minutes)
            # Log at DEBUG level to reduce noise, similar to JWT token expiration
            logger.debug(
                "Bayi token validation failed: timestamp expired "
                "(diff: %ds = %.1f minutes, now: %s, token_time: %s) - "
                "expected when token is old",
                time_diff, time_diff/60, now, token_time
            )
            return False

        logger.debug("Timestamp validation passed - diff: %ds", time_diff)
        return True
    except Exception as e:
        logger.error("Bayi token timestamp validation error: %s", e)
        return False


# ============================================================================
# Bayi IP Whitelist Functions
# ============================================================================

def is_ip_whitelisted(client_ip: str) -> bool:
    """
    Check if client IP is in bayi IP whitelist.

    If IP is whitelisted, teachers from that IP can skip token authentication
    and gain immediate access in bayi mode.

    Uses Redis Set for multi-worker support and dynamic management.
    Falls back to in-memory set if Redis unavailable (backward compatibility).

    Args:
        client_ip: Client IP address string

    Returns:
        True if IP is whitelisted, False otherwise
    """
    # Try Redis first (for multi-worker support and dynamic management)
    if _REDIS_AVAILABLE and get_bayi_whitelist is not None:
        try:
            whitelist = get_bayi_whitelist()
            # Check if Redis is being used by attempting the operation
            # The is_ip_whitelisted method handles Redis availability internally
            result = whitelist.is_ip_whitelisted(client_ip)
            if result:
                return True
            # If Redis check returned False, fall through to in-memory check
            # (in case IP was added to in-memory but not yet synced to Redis)
        except Exception as e:
            logger.debug("[Auth] Redis IP whitelist check failed, falling back to in-memory: %s", e)

    # Fallback to in-memory set (backward compatibility)
    if not BAYI_IP_WHITELIST:
        return False

    try:
        # Normalize IP address for comparison
        normalized_ip = ipaddress.ip_address(client_ip)
        ip_str = str(normalized_ip)

        # O(1) lookup in set
        if ip_str in BAYI_IP_WHITELIST:
            logger.debug("IP %s matched whitelist entry (in-memory fallback)", client_ip)
            return True

        return False
    except ValueError:
        logger.warning("Invalid IP address format: %s", client_ip)
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
                    logger.warning("Invalid expiry date for %s: %s", org_code, parts[2])

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
        logger.warning("Invitation code expired for %s", org_code)
        return False

    return True


# ============================================================================
# Rate Limiting & Security (Redis-backed, shared across workers)
# ============================================================================
# Note: Rate limiter functions are imported at the top of this file from
# services.redis.redis_rate_limiter and are available for use throughout


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
            return True, (
                f"Account temporarily locked due to too many failed attempts. "
                f"Please try again in {minutes_left} minute."
            )
        return True, (
            f"Account temporarily locked due to too many failed attempts. "
            f"Please try again in {minutes_left} minutes."
        )

    return False, ""


def lock_account(user: User, db: Session):
    """Lock user account for LOCKOUT_DURATION_MINUTES"""
    user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
    db.commit()

    # Invalidate and re-cache user (lock status changed)
    if _REDIS_AVAILABLE and user_cache:
        try:
            user_cache.invalidate(user.id, user.phone)
            user_cache.cache_user(user)  # Non-blocking cache update
        except Exception as e:
            # Non-critical - cache will be updated on next read
            logger.debug("[Auth] Failed to update cache after lock_account: %s", e)

    logger.warning("Account locked: %s", user.phone)


def reset_failed_attempts(user: User, db: Session):
    """Reset failed login attempts on successful login"""
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    db.commit()

    # Invalidate and re-cache user (lock status and last_login changed)
    if _REDIS_AVAILABLE and user_cache:
        try:
            user_cache.invalidate(user.id, user.phone)
            user_cache.cache_user(user)  # Non-blocking cache update
        except Exception as e:
            # Non-critical - cache will be updated on next read
            logger.debug("[Auth] Failed to update cache after reset_failed_attempts: %s", e)


def increment_failed_attempts(user: User, db: Session):
    """Increment failed login attempts"""
    user.failed_login_attempts += 1
    db.commit()

    if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
        lock_account(user, db)
    else:
        # Invalidate and re-cache user (failed_login_attempts changed)
        if _REDIS_AVAILABLE and user_cache:
            try:
                user_cache.invalidate(user.id, user.phone)
                user_cache.cache_user(user)  # Non-blocking cache update
            except Exception as e:
                # Non-critical - cache will be updated on next read
                logger.debug("[Auth] Failed to update cache after increment_failed_attempts: %s", e)


# ============================================================================
# Role Check Functions
# ============================================================================

def is_admin(current_user: User) -> bool:
    """
    Check if user is admin (full access to all data)

    Admin access granted if:
    1. User has role='admin' in database
    2. User phone in ADMIN_PHONES env variable (production admins)
    3. User is demo-admin@system.com AND server is in demo mode (demo admin)
    4. User is bayi-admin@system.com AND server is in bayi mode (bayi admin)

    This ensures demo/bayi admin passkey only works in their respective modes for security.
    """
    # Check database role field
    if hasattr(current_user, 'role') and current_user.role == 'admin':
        return True

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


def is_manager(current_user: User) -> bool:
    """
    Check if user is a manager (org-scoped admin access)

    Manager can access admin dashboard but only sees their organization's data.
    """
    if hasattr(current_user, 'role') and current_user.role == 'manager':
        return True
    return False


def is_admin_or_manager(current_user: User) -> bool:
    """
    Check if user has any elevated access (admin or manager)

    Used for routes that both admin and manager can access.
    """
    return is_admin(current_user) or is_manager(current_user)


def get_user_role(current_user: User) -> str:
    """
    Get the effective role of a user

    Returns: 'admin', 'manager', or 'user'
    """
    if is_admin(current_user):
        return 'admin'
    if is_manager(current_user):
        return 'manager'
    return 'user'


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
        APIKey.is_active.is_(True)
    ).first()

    if not key_record:
        logger.warning("Invalid API key attempted: %s...", api_key[:12])
        return False

    # Check expiration
    if key_record.expires_at and key_record.expires_at < datetime.utcnow():
        logger.warning("Expired API key used: %s", key_record.name)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired"
        )

    # Check quota
    if key_record.quota_limit and key_record.usage_count >= key_record.quota_limit:
        logger.warning("API key quota exceeded: %s", key_record.name)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"API key quota exceeded. Limit: {key_record.quota_limit}"
        )

    return True


def track_api_key_usage(api_key: str, db: Session):
    """Increment usage counter for API key"""
    try:
        key_record = db.query(APIKey).filter(APIKey.key == api_key).first()
        if key_record:
            key_record.usage_count += 1
            key_record.last_used_at = datetime.utcnow()
            db.commit()
            quota_info = key_record.quota_limit or 'unlimited'
            logger.debug(
                "[Auth] API key used: %s (usage: %s/%s)",
                key_record.name, key_record.usage_count, quota_info
            )
        else:
            logger.warning("[Auth] API key usage tracking failed: key record not found")
    except Exception as e:
        logger.error("[Auth] Failed to track API key usage: %s", e, exc_info=True)


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
                # Session validation: Check if session exists in Redis
                if not _REDIS_AVAILABLE:
                    user = None
                elif get_session_manager is None:
                    user = None
                else:
                    session_manager = get_session_manager()
                    if session_manager.is_session_valid(int(user_id), token):
                        # Use cache for user lookup (with SQLite fallback)
                        if user_cache is not None:
                            user = user_cache.get_by_id(int(user_id))
                        else:
                            user = None
                    else:
                        user = None

                if user:
                        worker_id = os.getenv('UVICORN_WORKER_ID', 'main')
                        # Include endpoint path for clarity when multiple parallel requests come in
                        endpoint = request.url.path if request else 'unknown'
                        logger.debug(
                            "Authenticated teacher: %s (ID: %d, Phone: %s) [Worker: %s] [%s]",
                            user.name, user.id, user.phone, worker_id, endpoint
                        )
                        return user  # Authenticated teacher - full access
        except HTTPException:
            # Invalid JWT, try API key instead
            pass

    # Priority 2: Try API key (for Dify, public API users)
    if api_key:
        # Create session for API key validation
        db = SessionLocal()
        try:
            if validate_api_key(api_key, db):
                # Get API key record to store ID in request state
                key_record = db.query(APIKey).filter(APIKey.key == api_key).first()

                if key_record:
                    if request and hasattr(request, 'state'):
                        # Store API key ID in request state for token tracking
                        request.state.api_key_id = key_record.id
                        request.state.api_key_name = key_record.name
                        logger.debug("[Auth] Stored API key ID %d in request state", key_record.id)
                    else:
                        logger.warning("[Auth] Request state not available, cannot store api_key_id for token tracking")

                    track_api_key_usage(api_key, db)
                    # Include endpoint path for clarity when multiple parallel requests come in
                    endpoint = request.url.path if request else 'unknown'
                    logger.info(
                        "[Auth] Valid API key access: %s (ID: %d) [%s]",
                        key_record.name, key_record.id, endpoint
                    )
                else:
                    logger.warning("[Auth] API key validated but record not found in database")
                    track_api_key_usage(api_key, db)
                    logger.info("[Auth] Valid API key access (record lookup failed)")

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

    quota_info = quota_limit or 'unlimited'
    logger.info("Generated API key: %s (quota: %s)", name, quota_info)

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

        # Session validation: Check if session exists in Redis
        if not _REDIS_AVAILABLE:
            await websocket.close(code=4001, reason="Redis unavailable")
            raise WebSocketDisconnect(code=4001, reason="Redis unavailable")
        if get_session_manager is None:
            await websocket.close(code=4001, reason="Session manager unavailable")
            raise WebSocketDisconnect(code=4001, reason="Session manager unavailable")
        session_manager = get_session_manager()
        if not session_manager.is_session_valid(int(user_id), token):
            await websocket.close(code=4001, reason="Session expired or invalidated")
            raise WebSocketDisconnect(code=4001, reason="Session expired or invalidated")

        # Use cache for user lookup (with SQLite fallback)
        user = None
        if user_cache:
            user = user_cache.get_by_id(int(user_id))
        if not user:
            # Fallback to DB if not in cache
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                db.expunge(user)
                if user_cache:
                    user_cache.cache_user(user)  # Cache it for next time

        if not user:
            await websocket.close(code=4001, reason="User not found")
            raise WebSocketDisconnect(code=4001, reason="User not found")

        return user

    except HTTPException as e:
        await websocket.close(code=4001, reason="Invalid token")
        raise WebSocketDisconnect(code=4001, reason=str(e.detail)) from e
