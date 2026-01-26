"""
Tencent Cloud Hunyuan Error Parser
===================================

Comprehensive error parsing for Tencent Cloud Hunyuan API errors.
Maps error codes and messages to proper exception types with user-friendly messages.

Reference: https://cloud.tencent.cn/document/product/1729/101847

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司
(Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Tuple, NoReturn
import logging
import re

from services.infrastructure.http.error_handler import (
    LLMServiceError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMContentFilterError,
    LLMProviderError,
    LLMInvalidParameterError,
    LLMQuotaExhaustedError,
    LLMModelNotFoundError,
    LLMAccessDeniedError
)

logger = logging.getLogger(__name__)


def _has_chinese_characters(text: str) -> bool:
    """
    Check if text contains Chinese characters.
    More robust than checking for 'zh' substring.

    Args:
        text: Text to check

    Returns:
        True if text contains Chinese characters
    """
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def parse_hunyuan_error(
    error_code: str,
    error_message: str,
    status_code: Optional[int] = None
) -> Tuple[Exception, str]:
    """
    Parse Tencent Cloud Hunyuan API error and return appropriate exception with user-friendly message.

    Args:
        error_code: Error code from API response (e.g., "AuthFailure.SignatureFailure")
        error_message: Error message from API response
        status_code: HTTP status code (optional, for fallback)

    Returns:
        Tuple of (exception, user_friendly_message)
        - exception: Appropriate exception to raise
        - user_friendly_message: User-facing error message
    """
    error_code.lower()
    error_message.lower()
    has_chinese = _has_chinese_characters(error_message)

    # ===== Authentication Errors (AuthFailure.*) =====
    if error_code.startswith('AuthFailure'):
        if 'InvalidAuthorization' in error_code:
            if has_chinese:
                user_msg = "请求头Authorization格式错误，请检查认证配置"
            else:
                user_msg = (
                    "Invalid Authorization header format. "
                    "Please check authentication configuration."
                )
            return LLMAccessDeniedError(
                f"Invalid authorization: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'InvalidSecretId' in error_code:
            user_msg = "密钥类型错误，请使用云API密钥" if has_chinese else "Invalid secret ID type. Please use cloud API key."
            return LLMAccessDeniedError(
                f"Invalid secret ID: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'SecretIdNotFound' in error_code:
            if has_chinese:
                user_msg = "密钥不存在或已被删除，请检查密钥配置"
            else:
                user_msg = (
                    "Secret ID not found or deleted. "
                    "Please check key configuration."
                )
            return LLMAccessDeniedError(
                f"Secret ID not found: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'SignatureExpire' in error_code:
            if has_chinese:
                user_msg = "签名已过期，请检查本地时间是否与标准时间同步"
            else:
                user_msg = (
                    "Signature expired. Please check if local time is "
                    "synchronized with standard time."
                )
            return LLMAccessDeniedError(
                f"Signature expired: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'SignatureFailure' in error_code:
            user_msg = "签名错误，请检查签名计算过程" if has_chinese else "Signature error. Please check signature calculation."
            return LLMAccessDeniedError(
                f"Signature failure: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'TokenFailure' in error_code:
            user_msg = "Token错误，请检查token配置" if has_chinese else "Token error. Please check token configuration."
            return LLMAccessDeniedError(
                f"Token failure: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'UnauthorizedOperation' in error_code:
            user_msg = "请求未授权，请检查权限配置" if has_chinese else "Unauthorized operation. Please check permissions."
            return LLMAccessDeniedError(
                f"Unauthorized operation: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        # Generic AuthFailure
        if has_chinese:
            user_msg = "认证失败，请检查API密钥和签名配置"
        else:
            user_msg = (
                "Authentication failed. Please check API key and "
                "signature configuration."
            )
        return LLMAccessDeniedError(
            f"Authentication failure: {error_message}",
            provider='hunyuan',
            error_code=error_code
        ), user_msg

    # ===== Parameter Errors =====
    if error_code == 'InvalidParameter' or error_code == 'InvalidParameter.InvalidParameter':
        if has_chinese:
            user_msg = "参数错误，请检查参数格式和类型"
        else:
            user_msg = (
                "Invalid parameter. Please check parameter format and type."
            )
        return LLMInvalidParameterError(
            f"Invalid parameter: {error_message}",
            parameter=None,
            error_code=error_code,
            provider='hunyuan'
        ), user_msg

    if error_code == 'InvalidParameterValue' or error_code.startswith('InvalidParameterValue'):
        if 'Model' in error_code:
            user_msg = "模型不存在，请检查模型名称" if has_chinese else "Model not found. Please check model name."
            return LLMModelNotFoundError(
                f"Model not found: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'ParameterValueError' in error_code:
            if has_chinese:
                user_msg = "参数字段或值有误，请检查参数配置"
            else:
                user_msg = (
                    "Parameter field or value error. "
                    "Please check parameter configuration."
                )
            return LLMInvalidParameterError(
                f"Invalid parameter value: {error_message}",
                parameter=None,
                error_code=error_code,
                provider='hunyuan'
            ), user_msg

        if has_chinese:
            user_msg = "参数取值错误，请检查参数值"
        else:
            user_msg = (
                "Invalid parameter value. Please check parameter values."
            )
        return LLMInvalidParameterError(
            f"Invalid parameter value: {error_message}",
            parameter=None,
            error_code=error_code,
            provider='hunyuan'
        ), user_msg

    if error_code == 'InvalidRequest':
        if has_chinese:
            user_msg = "请求格式错误，请检查请求body格式"
        else:
            user_msg = (
                "Invalid request format. Please check request body format."
            )
        return LLMInvalidParameterError(
            f"Invalid request: {error_message}",
            parameter='body',
            error_code=error_code,
            provider='hunyuan'
        ), user_msg

    if error_code == 'MissingParameter':
        if has_chinese:
            user_msg = "缺少必需参数，请检查参数配置"
        else:
            user_msg = (
                "Missing required parameter. Please check parameter "
                "configuration."
            )
        return LLMInvalidParameterError(
            f"Missing parameter: {error_message}",
            parameter=None,
            error_code=error_code,
            provider='hunyuan'
        ), user_msg

    if error_code == 'UnknownParameter':
        if has_chinese:
            user_msg = "未知参数错误，请移除未定义的参数"
        else:
            user_msg = "Unknown parameter. Please remove undefined parameters."
        return LLMInvalidParameterError(
            f"Unknown parameter: {error_message}",
            parameter=None,
            error_code=error_code,
            provider='hunyuan'
        ), user_msg

    # ===== Rate Limit Errors =====
    if (error_code == 'LimitExceeded' or
            error_code == 'RequestLimitExceeded' or
            error_code.startswith('RequestLimitExceeded')):
        user_msg = (
            "请求频率超过限制，请稍后重试" if has_chinese else
            "Request rate limit exceeded. Please try again later."
        )
        return LLMRateLimitError(f"Rate limit: {error_message}"), user_msg

    # ===== Quota/Resource Errors =====
    if error_code.startswith('FailedOperation'):
        if ('FreeResourcePackExhausted' in error_code or
                'ResourcePackExhausted' in error_code):
            if has_chinese:
                user_msg = "资源包余量已用尽，请购买资源包或开通后付费"
            else:
                user_msg = (
                    "Resource pack exhausted. Please purchase resource pack "
                    "or enable postpaid."
                )
            return LLMQuotaExhaustedError(
                f"Resource pack exhausted: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'EngineServerLimitExceeded' in error_code:
            user_msg = "引擎层请求超过限额，请稍后重试" if has_chinese else "Engine server limit exceeded. Please try again later."
            return LLMRateLimitError(f"Engine limit exceeded: {error_message}"), user_msg

        if 'EngineRequestTimeout' in error_code:
            user_msg = "引擎层请求超时，请稍后重试" if has_chinese else "Engine request timeout. Please try again later."
            return LLMTimeoutError(f"Engine timeout: {error_message}"), user_msg

        if 'EngineServerError' in error_code:
            user_msg = "引擎层内部错误，请稍后重试" if has_chinese else "Engine server error. Please try again later."
            return LLMServiceError(f"Engine error: {error_message}"), user_msg

        if 'ServiceNotActivated' in error_code:
            if has_chinese:
                user_msg = "服务未开通，请前往控制台申请试用"
            else:
                user_msg = (
                    "Service not activated. Please apply for trial in console."
                )
            return LLMAccessDeniedError(
                f"Service not activated: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'ServiceStop' in error_code or 'ServiceStopArrears' in error_code:
            user_msg = "服务已停用，请检查账户状态" if has_chinese else "Service stopped. Please check account status."
            return LLMAccessDeniedError(
                f"Service stopped: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'UserUnAuthError' in error_code:
            if has_chinese:
                user_msg = "用户未实名认证，请先进行实名认证"
            else:
                user_msg = (
                    "User not authenticated. Please complete real-name "
                    "authentication."
                )
            return LLMAccessDeniedError(
                f"User authentication required: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

    if error_code.startswith('ResourceUnavailable'):
        if 'InArrears' in error_code:
            user_msg = "账号已欠费，请及时充值" if has_chinese else "Account in arrears. Please recharge."
            return LLMQuotaExhaustedError(
                f"Account in arrears: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'LowBalance' in error_code:
            user_msg = "余额不足，请及时充值" if has_chinese else "Insufficient balance. Please recharge."
            return LLMQuotaExhaustedError(
                f"Insufficient balance: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'StopUsing' in error_code:
            user_msg = "账号已停服，请检查账户状态" if has_chinese else "Account service stopped. Please check account status."
            return LLMAccessDeniedError(
                f"Service stopped: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

        if 'NotExist' in error_code:
            if has_chinese:
                user_msg = "计费状态未知，请确认是否已在控制台开通服务"
            else:
                user_msg = (
                    "Billing status unknown. Please confirm if service is "
                    "activated in console."
                )
            return LLMAccessDeniedError(
                f"Service status unknown: {error_message}",
                provider='hunyuan',
                error_code=error_code
            ), user_msg

    if error_code == 'ResourceInsufficient.ChargeResourceExhaust':
        if has_chinese:
            user_msg = "计费资源已耗尽，请购买资源包或充值"
        else:
            user_msg = (
                "Billing resources exhausted. Please purchase resource pack "
                "or recharge."
            )
        return LLMQuotaExhaustedError(
            f"Billing resources exhausted: {error_message}",
            provider='hunyuan',
            error_code=error_code
        ), user_msg

    # ===== Content Filter Errors =====
    if error_code.startswith('OperationDenied'):
        if 'TextIllegalDetected' in error_code:
            user_msg = "文本包含违法违规信息，审核不通过" if has_chinese else "Text contains illegal content. Review failed."
            return LLMContentFilterError(f"Content filter: {error_message}"), user_msg

        if 'ImageIllegalDetected' in error_code:
            user_msg = "图片可能包含敏感信息，请重试" if has_chinese else "Image may contain sensitive information. Please retry."
            return LLMContentFilterError(f"Content filter: {error_message}"), user_msg

    if error_code == 'FailedOperation.GenerateImageFailed':
        user_msg = "图片包含敏感内容" if has_chinese else "Image contains sensitive content."
        return LLMContentFilterError(f"Content filter: {error_message}"), user_msg

    # ===== IP/Network Errors =====
    if error_code == 'IpInBlacklist':
        user_msg = "IP地址在黑名单中，请联系客服" if has_chinese else "IP address in blacklist. Please contact support."
        return LLMAccessDeniedError(
            f"IP blacklisted: {error_message}",
            provider='hunyuan',
            error_code=error_code
        ), user_msg

    if error_code == 'IpNotInWhitelist':
        user_msg = "IP地址不在白名单中，请添加IP到白名单" if has_chinese else "IP address not in whitelist. Please add IP to whitelist."
        return LLMAccessDeniedError(
            f"IP not whitelisted: {error_message}",
            provider='hunyuan',
            error_code=error_code
        ), user_msg

    # ===== Request Size Errors =====
    if error_code == 'RequestSizeLimitExceeded':
        if has_chinese:
            user_msg = "请求包超过限制大小，请减小请求内容"
        else:
            user_msg = (
                "Request size exceeds limit. Please reduce request content."
            )
        return LLMInvalidParameterError(
            f"Request too large: {error_message}",
            parameter='messages',
            error_code=error_code,
            provider='hunyuan'
        ), user_msg

    if error_code == 'ResponseSizeLimitExceeded':
        if has_chinese:
            user_msg = "返回包超过限制大小，请调整请求参数"
        else:
            user_msg = (
                "Response size exceeds limit. Please adjust request parameters."
            )
        return LLMInvalidParameterError(
            f"Response too large: {error_message}",
            parameter='max_tokens',
            error_code=error_code,
            provider='hunyuan'
        ), user_msg

    # ===== Service Errors =====
    if error_code == 'InternalError':
        user_msg = "内部错误，请稍后重试" if has_chinese else "Internal error. Please try again later."
        return LLMServiceError(f"Internal error: {error_message}"), user_msg

    if error_code == 'ServiceUnavailable':
        user_msg = "服务暂时不可用，请稍后重试" if has_chinese else "Service temporarily unavailable. Please try again later."
        return LLMServiceError(f"Service unavailable: {error_message}"), user_msg

    if error_code == 'FailedOperation':
        user_msg = "操作失败，请稍后重试" if has_chinese else "Operation failed. Please try again later."
        return LLMServiceError(f"Operation failed: {error_message}"), user_msg

    if error_code == 'ResourceNotFound':
        user_msg = "资源不存在，请检查资源ID" if has_chinese else "Resource not found. Please check resource ID."
        return LLMProviderError(
            f"Resource not found: {error_message}",
            provider='hunyuan',
            error_code=error_code
        ), user_msg

    if error_code == 'InvalidAction':
        user_msg = "接口不存在，请检查接口名称" if has_chinese else "Interface not found. Please check interface name."
        return LLMProviderError(
            f"Invalid action: {error_message}",
            provider='hunyuan',
            error_code=error_code
        ), user_msg

    if error_code == 'UnsupportedOperation':
        if has_chinese:
            user_msg = "操作不支持，请检查操作类型"
        else:
            user_msg = (
                "Operation not supported. Please check operation type."
            )
        return LLMInvalidParameterError(
            f"Unsupported operation: {error_message}",
            parameter=None,
            error_code=error_code,
            provider='hunyuan'
        ), user_msg

    if error_code == 'UnsupportedProtocol':
        if has_chinese:
            user_msg = "请求协议错误，仅支持GET和POST请求"
        else:
            user_msg = "Unsupported protocol. Only GET and POST are supported."
        return LLMInvalidParameterError(
            f"Unsupported protocol: {error_message}",
            parameter='method',
            error_code=error_code,
            provider='hunyuan'
        ), user_msg

    if error_code == 'UnsupportedRegion':
        if has_chinese:
            user_msg = "接口不支持所传地域，请检查地域配置"
        else:
            user_msg = (
                "Region not supported. Please check region configuration."
            )
        return LLMInvalidParameterError(
            f"Unsupported region: {error_message}",
            parameter='region',
            error_code=error_code,
            provider='hunyuan'
        ), user_msg

    # ===== Default: Generic Provider Error =====
    # Handles unknown error codes including numeric codes (e.g., "2003", "400")
    # These may be Tencent Cloud internal error codes or HTTP status codes
    user_msg = f"API错误: {error_message}" if has_chinese else f"API error: {error_message}"
    return LLMProviderError(
        f"Hunyuan API error ({error_code}): {error_message}",
        provider='hunyuan',
        error_code=error_code
    ), user_msg


def parse_and_raise_hunyuan_error(error_code: str, error_message: str, status_code: Optional[int] = None) -> NoReturn:
    """
    Parse Hunyuan error and raise appropriate exception.

    Args:
        error_code: Error code from API response
        error_message: Error message from API response
        status_code: HTTP status code (optional)

    Raises:
        Appropriate exception based on error type
    """
    exception, user_message = parse_hunyuan_error(error_code, error_message, status_code)

    # Log error with details
    logger.error(
        f"Hunyuan API error ({error_code}): {exception.__class__.__name__} - {str(exception)}",
        extra={
            'error_code': error_code,
            'status_code': status_code,
            'parameter': getattr(exception, 'parameter', None),
            'user_message': user_message
        }
    )

    # Attach user-friendly message to exception
    exception.user_message = user_message  # type: ignore[attr-defined]

    raise exception

