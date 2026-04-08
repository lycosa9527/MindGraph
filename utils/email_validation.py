"""
Email validation helpers for API endpoints (localized errors).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from email_validator import EmailNotValidError, validate_email as ev_validate

from fastapi import HTTPException, status

from models.domain.messages import Language, Messages


def validate_email_for_api(value: str, lang: Language) -> str:
    """
    Validate and normalize email (RFC-style). Raises HTTPException 400 with localized detail on failure.
    """
    value = value.strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("email_invalid_format", lang),
        )
    try:
        return ev_validate(value, check_deliverability=False).normalized
    except EmailNotValidError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("email_invalid_format", lang),
        ) from None


def validate_email_code_digits(code: str, lang: Language) -> str:
    """Validate 6-digit verification code; raises HTTPException 400 with localized detail on failure."""
    code = code.strip()
    if len(code) != 6 or not code.isdigit():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=Messages.error("email_code_format_invalid", lang),
        )
    return code
