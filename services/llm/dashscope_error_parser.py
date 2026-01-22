"""
DashScope Error Parser
======================

Comprehensive error parsing for Alibaba Cloud DashScope API errors.
Maps error codes and messages to proper exception types with user-friendly messages.

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Dict, NoReturn, Optional, Tuple
import json
import logging
import re

from services.infrastructure.http.error_handler import LLMProviderError
from services.llm.dashscope_errors import (
    has_chinese_characters,
    parse_400_errors,
    parse_401_errors,
    parse_403_errors,
    parse_404_errors,
    parse_429_errors,
    parse_500_errors,
    parse_503_errors,
    parse_content_filter_errors,
    parse_specialized_errors
)

logger = logging.getLogger(__name__)


def parse_dashscope_error(
    status_code: int,
    error_text: str,
    error_data: Optional[Dict] = None
) -> Tuple[Exception, str]:
    """
    Parse DashScope API error and return appropriate exception with user-friendly message.

    Args:
        status_code: HTTP status code
        error_text: Raw error text from API
        error_data: Parsed error JSON data (if available)

    Returns:
        Tuple of (exception, user_friendly_message)
        - exception: Appropriate exception to raise
        - user_friendly_message: User-facing error message
    """
    # Parse error data if not provided
    if error_data is None:
        try:
            error_data = json.loads(error_text)
        except (json.JSONDecodeError, TypeError):
            error_data = {}

    # Extract error information from various response formats
    # DashScope can return errors in different formats:
    # 1. {"error": {"code": "...", "message": "..."}}
    # 2. {"code": "...", "message": "..."}
    # 3. {"error": "..."}
    # 4. Plain text

    # Ensure error_data is a dict
    if not isinstance(error_data, dict):
        error_data = {}

    error_info = error_data.get('error', {})
    if not error_info and isinstance(error_data, dict):
        # Try direct access if 'error' key doesn't exist
        error_info = error_data

    error_code = error_info.get('code', '') if isinstance(error_info, dict) else ''
    error_message = error_info.get('message', '') if isinstance(error_info, dict) else ''

    # Fallback to error_text if message not found
    if not error_message:
        if isinstance(error_info, dict) and 'error' in error_info:
            error_message = error_info.get('error', error_text)
        elif isinstance(error_info, str):
            error_message = error_info
        else:
            error_message = error_text

    # Extract error code from message if not in code field
    # Some errors have format: "400-InvalidParameter: message"
    if not error_code and '-' in error_message:
        code_match = re.match(r'(\d+)-([A-Za-z.]+)', error_message)
        if code_match:
            error_code = code_match.group(2)
            if ':' in error_message:
                error_message = error_message.split(':', 1)[-1].strip()

    # Normalize error message for matching
    error_msg_lower = error_message.lower()
    has_chinese = has_chinese_characters(error_message)

    # Extract status code from error code if present (e.g., "400-InvalidParameter")
    if error_code and '-' in error_code:
        code_parts = error_code.split('-', 1)
        if code_parts[0].isdigit():
            # Use status code from error code if it's more specific
            error_code_status = int(code_parts[0])
            if error_code_status != status_code:
                # Prefer the status code from error code if different
                status_code = error_code_status
            error_code = code_parts[1] if len(code_parts) > 1 else error_code

    # Try content filter errors first (can occur with various status codes)
    result = parse_content_filter_errors(error_message, error_msg_lower, error_code, has_chinese)
    if result is not None:
        return result

    # Route to status code specific handlers
    if status_code == 400:
        result = parse_400_errors(error_message, error_msg_lower, error_code, has_chinese)
        if result is not None:
            return result

    elif status_code == 401:
        result = parse_401_errors(error_message, error_msg_lower, error_code, has_chinese)
        if result is not None:
            return result

    elif status_code == 403:
        result = parse_403_errors(error_message, error_msg_lower, error_code, has_chinese)
        if result is not None:
            return result

    elif status_code == 404:
        result = parse_404_errors(error_message, error_msg_lower, error_code, has_chinese)
        if result is not None:
            return result

    elif status_code == 429:
        result = parse_429_errors(error_message, error_msg_lower, error_code, has_chinese)
        if result is not None:
            return result

    elif status_code == 500:
        result = parse_500_errors(error_message, error_msg_lower, error_code, has_chinese)
        if result is not None:
            return result

    elif status_code == 503:
        result = parse_503_errors(error_message, error_msg_lower, error_code, has_chinese)
        if result is not None:
            return result

    # Try specialized errors
    result = parse_specialized_errors(
        error_message, error_msg_lower, error_code, has_chinese, status_code
    )
    if result is not None:
        return result

    # Default: Generic Provider Error
    user_msg = f"API错误: {error_message}" if has_chinese else f"API error: {error_message}"
    return LLMProviderError(
        f"DashScope API error ({status_code}): {error_message}",
        provider='dashscope',
        error_code=error_code or f'HTTP{status_code}'
    ), user_msg


def parse_and_raise_dashscope_error(
    status_code: int,
    error_text: str,
    error_data: Optional[Dict] = None
) -> NoReturn:
    """
    Parse DashScope error and raise appropriate exception.

    Args:
        status_code: HTTP status code
        error_text: Raw error text
        error_data: Parsed error JSON (optional)

    Raises:
        Appropriate exception based on error type
    """
    exception, user_message = parse_dashscope_error(status_code, error_text, error_data)

    # Log error with details
    logger.error(
        "DashScope API error (%d): %s - %s",
        status_code,
        exception.__class__.__name__,
        str(exception),
        extra={
            'status_code': status_code,
            'error_code': getattr(exception, 'error_code', None),
            'parameter': getattr(exception, 'parameter', None),
            'user_message': user_message
        }
    )

    # Attach user-friendly message to exception
    exception.user_message = user_message  # type: ignore[attr-defined]

    raise exception
