"""
Password Hashing for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Secure password hashing and verification using bcrypt.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

import bcrypt

from .config import BCRYPT_ROUNDS

logger = logging.getLogger(__name__)


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
        logger.warning(
            "Password truncated to %d bytes for bcrypt compatibility",
            len(password_bytes)
        )

    try:
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error("Password hashing failed: %s", e)
        logger.error(
            "Password length: %d chars, %d bytes", len(password), len(password_bytes)
        )
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
