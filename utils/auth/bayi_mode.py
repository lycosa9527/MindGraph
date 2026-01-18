"""
Bayi Mode Authentication for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Bayi token decryption and validation functions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import base64
import hashlib
import json
import logging
from datetime import datetime
from urllib.parse import unquote

from .config import BAYI_CLOCK_SKEW_TOLERANCE

logger = logging.getLogger(__name__)

# Optional crypto imports
AES = None
unpad = None

try:
    from Crypto.Cipher import AES as CryptoAES
    from Crypto.Util.Padding import unpad as crypto_unpad
    AES = CryptoAES
    unpad = crypto_unpad
except ImportError:
    pass


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
        raise ValueError(
            "pycryptodome is required for bayi token decryption. "
            "Install with: pip install pycryptodome"
        )

    try:
        # Decode URL encoding
        token = unquote(encrypted_token)
        logger.debug(
            "Decrypting bayi token - length: %d, ends with '==': %s",
            len(token), token.endswith('==')
        )

        # Generate secret key using SHA256 (same as CryptoJS)
        secret_key = hashlib.sha256(key.encode('utf-8')).digest()

        # Decode base64 token (CryptoJS uses base64 encoding)
        try:
            encrypted_bytes = base64.b64decode(token, validate=True)
            logger.debug(
                "Base64 decoded successfully - encrypted bytes length: %d",
                len(encrypted_bytes)
            )
        except Exception as e:
            logger.error("Base64 decode failed: %s, token preview: %s", e, token[:50])
            raise ValueError(f"Invalid base64 token: {str(e)}") from e

        # Decrypt using AES-ECB mode
        cipher = AES.new(secret_key, AES.MODE_ECB)
        decrypted_bytes = cipher.decrypt(encrypted_bytes)
        logger.debug(
            "Decryption successful - decrypted bytes length: %d",
            len(decrypted_bytes)
        )

        # Remove PKCS7 padding
        try:
            decrypted_text = unpad(decrypted_bytes, AES.block_size).decode('utf-8')
            logger.debug(
                "Unpadded successfully - decrypted text length: %d",
                len(decrypted_text)
            )
        except Exception as e:
            logger.error(
                "Unpad failed: %s, decrypted bytes preview: %s",
                e, decrypted_bytes[:50]
            )
            raise ValueError(f"Padding removal failed: {str(e)}") from e

        # Parse JSON
        try:
            result = json.loads(decrypted_text)
            logger.debug("JSON parsed successfully - keys: %s", list(result.keys()))
            return result
        except Exception as e:
            logger.error(
                "JSON parse failed: %s, decrypted text: %s",
                e, decrypted_text[:200]
            )
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
        logger.warning(
            "Bayi token validation failed: 'from' field is '%s', expected 'bayi'",
            body.get('from')
        )
        return False

    # Check timestamp (must be within last 5 minutes)
    timestamp = body.get('timestamp')
    if not timestamp:
        logger.warning("Bayi token validation failed: missing timestamp")
        return False

    try:
        # Convert timestamp to datetime (Unix timestamps are always UTC)
        if isinstance(timestamp, (int, float)):
            token_time = datetime.utcfromtimestamp(timestamp)
        elif isinstance(timestamp, str):
            try:
                token_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                if token_time.tzinfo is None:
                    token_time = token_time.replace(tzinfo=None)
            except ValueError:
                token_time = datetime.utcfromtimestamp(float(timestamp))
        else:
            logger.warning(
                "Bayi token validation failed: invalid timestamp type: %s",
                type(timestamp)
            )
            return False

        now = datetime.utcnow()
        time_diff = (now - token_time).total_seconds()

        logger.debug(
            "Timestamp validation - now (UTC): %s, token_time (UTC): %s, "
            "diff: %ds (%.1f minutes)",
            now, token_time, time_diff, time_diff/60
        )

        # Allow tokens slightly in the future (within clock skew tolerance)
        if time_diff < -BAYI_CLOCK_SKEW_TOLERANCE:
            logger.warning(
                "Bayi token validation failed: timestamp is too far in the future "
                "(diff: %ds, tolerance: %ds, now: %s, token_time: %s)",
                time_diff, BAYI_CLOCK_SKEW_TOLERANCE, now, token_time
            )
            return False

        if time_diff < 0:
            logger.debug(
                "Bayi token timestamp is slightly in the future but within tolerance "
                "(diff: %ds, tolerance: %ds)",
                time_diff, BAYI_CLOCK_SKEW_TOLERANCE
            )

        if time_diff > 300:  # 5 minutes = 300 seconds
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
