"""
Invitation Code Management for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Functions for managing organization invitation codes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def load_invitation_codes() -> Dict[str, Tuple[str, Optional[datetime]]]:
    """
    Load invitation codes from environment variable

    Format: ORG_CODE:INVITATION_CODE:EXPIRY_DATE
    Invitation code format: AAAA-XXXXX (4 uppercase letters, dash, 5 letters/digits)
    Example: DEMO-001:DEMO-A1B2C:2025-12-31,SPRING-EDU:SPRN-9K2L1:never

    Returns:
        Dict[org_code] = (invitation_code, expiry_datetime or None)
    """
    codes: Dict[str, Tuple[str, Optional[datetime]]] = {}
    env_codes = os.getenv("INVITATION_CODES", "")

    if not env_codes:
        return codes

    for code_str in env_codes.split(","):
        parts = code_str.strip().split(":")
        if len(parts) >= 2:
            org_code = parts[0]
            invitation_code = parts[1]
            expiry: Optional[datetime] = None

            if len(parts) >= 3 and parts[2].lower() != "never":
                try:
                    expiry = datetime.strptime(parts[2], "%Y-%m-%d")
                except ValueError:
                    logger.warning(
                        "Invalid expiry date for %s: %s", org_code, parts[2]
                    )

            codes[org_code] = (invitation_code, expiry)

    return codes


def validate_invitation_code(org_code: str, invitation_code: str) -> bool:
    """
    Validate invitation code for an organization

    Args:
        org_code: Organization code
        invitation_code: Invitation code to validate

    Returns:
        True if valid and not expired, False otherwise
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
