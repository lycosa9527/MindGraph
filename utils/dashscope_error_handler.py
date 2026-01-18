"""
DashScope Error Handler
=======================

Comprehensive error handling for DashScope API errors.
Maps DashScope error codes to user-friendly messages and handles retries.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from enum import Enum
from typing import Dict, Any, Optional, Tuple
import logging


logger = logging.getLogger(__name__)


class DashScopeErrorType(Enum):
    """DashScope error types."""
    INVALID_PARAMETER = "InvalidParameter"
    INVALID_API_KEY = "InvalidApiKey"
    ARREARAGE = "Arrearage"
    THROTTLING = "Throttling"
    INTERNAL_ERROR = "InternalError"
    MODEL_NOT_FOUND = "ModelNotFound"
    ACCESS_DENIED = "AccessDenied"
    DATA_INSPECTION_FAILED = "DataInspectionFailed"
    BAD_REQUEST = "BadRequest"
    UNKNOWN = "Unknown"


class DashScopeError(Exception):
    """Custom exception for DashScope API errors."""

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        error_type: Optional[DashScopeErrorType] = None,
        status_code: Optional[int] = None,
        retryable: bool = False,
        retry_after: Optional[int] = None
    ):
        self.message = message
        self.error_code = error_code
        self.error_type = error_type
        self.status_code = status_code
        self.retryable = retryable
        self.retry_after = retry_after
        super().__init__(self.message)


def parse_dashscope_error(response_data: Dict[str, Any], status_code: int) -> DashScopeError:
    """
    Parse DashScope API error response and create appropriate exception.

    Args:
        response_data: JSON response from DashScope API
        status_code: HTTP status code

    Returns:
        DashScopeError with appropriate error details
    """
    # Extract error information
    error_code = response_data.get("code") or response_data.get("error", {}).get("code")
    error_message = response_data.get("message") or response_data.get("error", {}).get("message")
    error_type_str = response_data.get("type") or response_data.get("error", {}).get("type")

    # Determine error type
    error_type = DashScopeErrorType.UNKNOWN
    if error_type_str:
        for etype in DashScopeErrorType:
            if etype.value in error_type_str:
                error_type = etype
                break

    # Determine if retryable
    retryable = status_code in (429, 500, 502, 503, 504)
    retry_after = None
    if status_code == 429:
        # Extract retry-after from headers if available
        retry_after = 60  # Default 60 seconds for rate limiting

    # Map error codes to user-friendly messages
    user_message = _get_user_friendly_message(error_code, error_message, error_type, status_code)

    return DashScopeError(
        message=user_message,
        error_code=error_code,
        error_type=error_type,
        status_code=status_code,
        retryable=retryable,
        retry_after=retry_after
    )


def _get_user_friendly_message(
    error_code: Optional[str],
    error_message: Optional[str],
    error_type: DashScopeErrorType,
    status_code: int
) -> str:
    """
    Get user-friendly error message based on error code and type.

    Maps DashScope error codes to Chinese/English user-friendly messages.
    """
    # Default message
    default_msg = error_message or f"DashScope API error (status: {status_code})"

    # Map specific error codes to messages
    # Includes both DashScope native format (PascalCase) and OpenAI-compatible format (snake_case)
    error_messages: Dict[str, Dict[str, str]] = {
        # API Key errors
        "InvalidApiKey": {
            "zh": "API密钥无效，请检查配置",
            "en": "Invalid API key, please check configuration"
        },
        "invalid_api_key": {  # OpenAI-compatible format
            "zh": "API密钥无效，请检查配置",
            "en": "Invalid API key, please check configuration"
        },
        # Account errors
        "Arrearage": {
            "zh": "账号欠费，请充值后重试",
            "en": "Account arrears, please recharge and retry"
        },
        # Parameter errors
        "InvalidParameter": {
            "zh": "参数错误，请检查请求参数",
            "en": "Invalid parameter, please check request parameters"
        },
        "invalid_request_error": {  # OpenAI-compatible format
            "zh": "请求参数错误，请检查请求格式",
            "en": "Invalid request error, please check request format"
        },
        # Rate limiting
        "Throttling": {
            "zh": "请求频率过高，请稍后重试",
            "en": "Request rate limit exceeded, please retry later"
        },
        "Throttling.RateQuota": {
            "zh": "请求频率超限，请降低调用频率",
            "en": "Request rate quota exceeded, please reduce call frequency"
        },
        "Throttling.AllocationQuota": {
            "zh": "Token配额不足，请稍后重试",
            "en": "Token quota insufficient, please retry later"
        },
        "rate_limit_exceeded": {  # OpenAI-compatible format
            "zh": "请求频率超限，请稍后重试",
            "en": "Rate limit exceeded, please retry later"
        },
        # Model errors
        "ModelNotFound": {
            "zh": "模型不存在或未授权，请检查模型名称",
            "en": "Model not found or not authorized, please check model name"
        },
        "model_not_found": {  # OpenAI-compatible format
            "zh": "模型不存在，请检查模型名称",
            "en": "Model not found, please check model name"
        },
        # Access errors
        "AccessDenied": {
            "zh": "访问被拒绝，请检查权限配置",
            "en": "Access denied, please check permissions"
        },
        # Content errors
        "DataInspectionFailed": {
            "zh": "内容审核未通过，请修改输入内容",
            "en": "Content inspection failed, please modify input content"
        },
        # Server errors
        "InternalError": {
            "zh": "服务内部错误，请稍后重试",
            "en": "Internal server error, please retry later"
        },
        "internal_error": {  # OpenAI-compatible format
            "zh": "服务内部错误，请稍后重试",
            "en": "Internal server error, please retry later"
        },
        "BadRequest": {
            "zh": "请求格式错误，请检查请求参数",
            "en": "Bad request format, please check request parameters"
        },
    }

    # Try to find specific error code mapping
    if error_code:
        # Try exact match first
        if error_code in error_messages:
            return error_messages[error_code]["zh"]

        # Try partial match (e.g., "Throttling.RateQuota" -> "Throttling")
        for code_key, messages in error_messages.items():
            if code_key in error_code or error_code.startswith(code_key):
                return messages["zh"]

    # Try error type mapping
    if error_type != DashScopeErrorType.UNKNOWN:
        type_key = error_type.value
        if type_key in error_messages:
            return error_messages[type_key]["zh"]

    # Status code based messages
    if status_code == 401:
        return "API密钥无效或已过期，请检查配置"
    elif status_code == 403:
        return "访问被拒绝，请检查API密钥权限"
    elif status_code == 404:
        return "模型不存在，请检查模型名称"
    elif status_code == 429:
        return "请求频率过高，请稍后重试"
    elif status_code == 500:
        return "服务内部错误，请稍后重试"
    elif status_code == 503:
        return "服务暂时不可用，请稍后重试"

    return default_msg


def handle_dashscope_response(response, raise_on_error: bool = True) -> Tuple[bool, Optional[DashScopeError]]:
    """
    Handle DashScope API response and check for errors.

    Args:
        response: httpx.Response object
        raise_on_error: If True, raise exception on error; otherwise return error

    Returns:
        Tuple of (success: bool, error: Optional[DashScopeError])

    Raises:
        DashScopeError if raise_on_error=True and error detected
    """
    try:
        response.raise_for_status()
        return True, None
    except Exception as original_error:
        # Try to parse error response
        error = None
        try:
            error_data = response.json()
            error = parse_dashscope_error(error_data, response.status_code)
        except Exception:
            # If we can't parse JSON, create generic error
            error = DashScopeError(
                message=f"HTTP {response.status_code}: {response.text[:200]}",
                status_code=response.status_code,
                retryable=response.status_code in (429, 500, 502, 503, 504)
            )

        if raise_on_error:
            raise error from original_error

        return False, error


def should_retry(error: DashScopeError, attempt: int, max_retries: int = 3) -> bool:
    """
    Determine if error should be retried.

    Args:
        error: DashScopeError instance
        attempt: Current attempt number (1-based)
        max_retries: Maximum number of retries

    Returns:
        True if should retry, False otherwise
    """
    if attempt > max_retries:
        return False

    # Don't retry non-retryable errors
    if not error.retryable:
        return False

    # Don't retry authentication/authorization errors
    if error.status_code in (401, 403):
        return False

    # Don't retry invalid parameter errors
    if error.error_type == DashScopeErrorType.INVALID_PARAMETER:
        return False

    return True


def get_retry_delay(attempt: int, error: Optional[DashScopeError] = None) -> float:
    """
    Calculate retry delay with exponential backoff.

    Args:
        attempt: Current attempt number (1-based)
        error: Optional DashScopeError (may contain retry_after)

    Returns:
        Delay in seconds
    """
    # Use retry_after from error if available
    if error and error.retry_after:
        return float(error.retry_after)

    # Exponential backoff: 1s, 2s, 4s, 8s...
    base_delay = 1.0
    return min(base_delay * (2 ** (attempt - 1)), 60.0)  # Cap at 60 seconds
