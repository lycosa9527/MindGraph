"""
Volcengine Doubao Error Parser
===============================

Comprehensive error parsing for Volcengine Doubao (ARK) API errors.
Maps error codes and messages to proper exception types with user-friendly messages.

Reference: https://www.volcengine.com/docs/82379/1299023?lang=zh

@author lycosa9527
@made_by MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Tuple
import logging
import re

from services.infrastructure.http.error_handler import (
    LLMServiceError,
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

    Args:
        text: Text to check

    Returns:
        True if text contains Chinese characters
    """
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def parse_doubao_error(
    error_code: str,
    error_message: str,
    status_code: Optional[int] = None
) -> Tuple[Exception, str]:
    """
    Parse Volcengine Doubao API error and return appropriate exception with user-friendly message.

    Args:
        error_code: Error code from API response (e.g., "BadRequest.MissingParameter")
        error_message: Error message from API response
        status_code: HTTP status code (optional, for fallback)

    Returns:
        Tuple of (exception, user_friendly_message)
        - exception: Appropriate exception to raise
        - user_friendly_message: User-facing error message
    """
    error_code_lower = error_code.lower()
    error_msg_lower = error_message.lower()
    has_chinese = _has_chinese_characters(error_message)

    # ===== 400 BadRequest - Parameter Errors =====
    if status_code == 400 or error_code == 'BadRequest':
        # MissingParameter
        if error_code == 'MissingParameter' or 'missing' in error_msg_lower and 'parameter' in error_msg_lower:
            if has_chinese:
                user_msg = "请求缺少必要参数，请查阅 API 文档"
            else:
                user_msg = "Request missing required parameters. Please check API documentation."
            return LLMInvalidParameterError(
                f"Missing parameter: {error_message}",
                parameter=None,
                error_code=error_code,
                provider='doubao'
            ), user_msg

        # InvalidParameter
        if error_code == 'InvalidParameter' or 'invalid' in error_code_lower and 'parameter' in error_code_lower:
            # Check for specific invalid parameter cases
            if 'instructions' in error_msg_lower and 'caching' in error_msg_lower:
                if has_chinese:
                    user_msg = "当配置过 instructions 字段信息，后续轮次无法配置 Caching 字段"
                else:
                    user_msg = "Cannot configure Caching field after instructions field is configured."
                return LLMInvalidParameterError(
                    f"Invalid parameter: {error_message}",
                    parameter='caching',
                    error_code=error_code,
                    provider='doubao'
                ), user_msg

            if has_chinese:
                user_msg = "请求包含非法参数，请查阅 API 文档"
            else:
                user_msg = "Request contains invalid parameters. Please check API documentation."
            return LLMInvalidParameterError(
                f"Invalid parameter: {error_message}",
                parameter=None,
                error_code=error_code,
                provider='doubao'
            ), user_msg

        # InvalidEndpoint.ClosedEndpoint
        if (error_code == 'InvalidEndpoint.ClosedEndpoint' or
            ('endpoint' in error_code_lower and 'closed' in error_msg_lower)):
            if has_chinese:
                user_msg = (
                    "推理接入点处于已被关闭或暂时不可用，请稍后重试，"
                    "或联系推理接入点管理员"
                )
            else:
                user_msg = (
                    "Endpoint is closed or temporarily unavailable. "
                    "Please try again later or contact endpoint administrator."
                )
            return LLMProviderError(
                f"Endpoint closed: {error_message}",
                provider='doubao',
                error_code=error_code
            ), user_msg

        # Content Security Detection Errors
        if 'RiskDetection' in error_code or 'SensitiveContentDetected' in error_code:
            # InputTextRiskDetection
            if ('InputTextRiskDetection' in error_code or
                ('input' in error_code_lower and 'text' in error_code_lower and
                 'risk' in error_code_lower)):
                if has_chinese:
                    user_msg = (
                        "火山引擎风险识别产品检测到输入文本可能包含敏感信息，"
                        "请您更换后重试"
                    )
                else:
                    user_msg = (
                        "Input text may contain sensitive content detected by "
                        "risk detection. Please modify and retry."
                    )
                return LLMContentFilterError(f"Input text risk detection: {error_message}"), user_msg

            # InputImageRiskDetection
            if ('InputImageRiskDetection' in error_code or
                ('input' in error_code_lower and 'image' in error_code_lower and
                 'risk' in error_code_lower)):
                if has_chinese:
                    user_msg = (
                        "火山引擎风险识别产品检测到输入图片可能包含敏感信息，"
                        "请您更换后重试"
                    )
                else:
                    user_msg = (
                        "Input image may contain sensitive content detected by "
                        "risk detection. Please modify and retry."
                    )
                return LLMContentFilterError(f"Input image risk detection: {error_message}"), user_msg

            # OutputTextRiskDetection
            if ('OutputTextRiskDetection' in error_code or
                ('output' in error_code_lower and 'text' in error_code_lower and
                 'risk' in error_code_lower)):
                if has_chinese:
                    user_msg = (
                        "火山引擎风险识别产品检测到输出文本可能包含敏感信息，"
                        "请您更换后重试"
                    )
                else:
                    user_msg = (
                        "Output text may contain sensitive content detected by "
                        "risk detection. Please modify and retry."
                    )
                return LLMContentFilterError(f"Output text risk detection: {error_message}"), user_msg

            # OutputImageRiskDetection
            if ('OutputImageRiskDetection' in error_code or
                ('output' in error_code_lower and 'image' in error_code_lower and
                 'risk' in error_code_lower)):
                if has_chinese:
                    user_msg = (
                        "火山引擎风险识别产品检测到输出图片可能包含敏感信息，"
                        "请您更换后重试"
                    )
                else:
                    user_msg = (
                        "Output image may contain sensitive content detected by "
                        "risk detection. Please modify and retry."
                    )
                return LLMContentFilterError(f"Output image risk detection: {error_message}"), user_msg

            # ContentSecurityDetectionError
            if 'ContentSecurityDetectionError' in error_code:
                if has_chinese:
                    user_msg = "火山引擎风险识别产品请求失败"
                else:
                    user_msg = "Content security detection request failed."
                return LLMContentFilterError(f"Content security detection error: {error_message}"), user_msg

            # SensitiveContentDetected
            if 'SensitiveContentDetected' in error_code:
                if 'SevereViolation' in error_code:
                    if has_chinese:
                        user_msg = "输入文本可能包含严重违规相关信息，请您使用其他 prompt"
                    else:
                        user_msg = (
                            "Input text may contain severe violation information. "
                            "Please use a different prompt."
                        )
                elif 'Violence' in error_code:
                    if has_chinese:
                        user_msg = "输入文本可能包含激进行为相关信息，请您使用其他 prompt"
                    else:
                        user_msg = (
                            "Input text may contain violence information. "
                            "Please use a different prompt."
                        )
                else:
                    if has_chinese:
                        user_msg = "输入文本可能包含敏感信息，请您使用其他 prompt"
                    else:
                        user_msg = (
                            "Input text may contain sensitive information. "
                            "Please use a different prompt."
                        )
                return LLMContentFilterError(f"Sensitive content detected: {error_message}"), user_msg

            # InputTextSensitiveContentDetected / InputImageSensitiveContentDetected
            if 'InputTextSensitiveContentDetected' in error_code:
                if has_chinese:
                    user_msg = "输入文本可能包含敏感信息，请您更换后重试"
                else:
                    user_msg = (
                        "Input text may contain sensitive information. "
                        "Please modify and retry."
                    )
                return LLMContentFilterError(f"Input text sensitive content: {error_message}"), user_msg

            if 'InputImageSensitiveContentDetected' in error_code:
                if has_chinese:
                    user_msg = "输入图像可能包含敏感信息，请您更换后重试"
                else:
                    user_msg = (
                        "Input image may contain sensitive information. "
                        "Please modify and retry."
                    )
                return LLMContentFilterError(f"Input image sensitive content: {error_message}"), user_msg

        # Generic BadRequest
        if has_chinese:
            user_msg = "请求参数错误，请检查参数配置"
        else:
            user_msg = "Bad request. Please check parameter configuration."
        return LLMInvalidParameterError(
            f"Bad request: {error_message}",
            parameter=None,
            error_code=error_code,
            provider='doubao'
        ), user_msg

    # ===== 401 Unauthorized =====
    if status_code == 401 or error_code == 'Unauthorized':
        if has_chinese:
            user_msg = "认证失败，请检查 API Key 配置"
        else:
            user_msg = "Authentication failed. Please check API Key configuration."
        return LLMAccessDeniedError(
            f"Unauthorized: {error_message}",
            provider='doubao',
            error_code=error_code
        ), user_msg

    # ===== 403 Forbidden =====
    if status_code == 403 or error_code == 'Forbidden':
        # OperationDenied
        if (error_code.startswith('OperationDenied') or
            ('operation' in error_code_lower and 'denied' in error_code_lower)):
            if 'InvalidState' in error_code:
                if has_chinese:
                    user_msg = "请求所关联的资源处于非可用状态，不可调用"
                else:
                    user_msg = "Resource is in invalid state and cannot be called."
                return LLMProviderError(
                    f"Operation denied: {error_message}",
                    provider='doubao',
                    error_code=error_code
                ), user_msg

            if has_chinese:
                user_msg = "操作被拒绝，请检查权限配置"
            else:
                user_msg = "Operation denied. Please check permissions."
            return LLMAccessDeniedError(
                f"Operation denied: {error_message}",
                provider='doubao',
                error_code=error_code
            ), user_msg

        if has_chinese:
            user_msg = "访问被拒绝，请检查权限配置"
        else:
            user_msg = "Access forbidden. Please check permissions."
        return LLMAccessDeniedError(
            f"Forbidden: {error_message}",
            provider='doubao',
            error_code=error_code
        ), user_msg

    # ===== 404 NotFound =====
    if status_code == 404 or error_code == 'NotFound':
        # InvalidEndpointOrModel.NotFound
        if 'InvalidEndpointOrModel' in error_code or 'NotFound' in error_code:
            if 'ModelNotOpen' in error_code or 'not activated' in error_msg_lower:
                if has_chinese:
                    user_msg = (
                        "当前账号暂未开通模型服务，请前往火山方舟控制台开通管理页"
                        "开通对应模型服务"
                    )
                else:
                    user_msg = (
                        "Model service not activated. Please activate the model "
                        "service in Ark Console."
                    )
                return LLMModelNotFoundError(
                    f"Model not open: {error_message}",
                    provider='doubao',
                    error_code=error_code
                ), user_msg

            if ('ModelIDAccessDisabled' in error_code or
                ('model id' in error_msg_lower and 'not allowed' in error_msg_lower)):
                if has_chinese:
                    user_msg = (
                        "你的账号不允许使用模型ID来调用模型，"
                        "请使用有权限的推理接入点 ID"
                    )
                else:
                    user_msg = (
                        "Model ID access disabled. Please use a custom "
                        "endpoint ID instead."
                    )
                return LLMModelNotFoundError(
                    f"Model ID access disabled: {error_message}",
                    provider='doubao',
                    error_code=error_code
                ), user_msg

            if 'UnsupportedModel' in error_code or 'does not support' in error_msg_lower:
                if has_chinese:
                    user_msg = "当前模型不支持该功能，请参考文档选择兼容的模型"
                else:
                    user_msg = (
                        "Model does not support this feature. Please refer to "
                        "documentation for compatible models."
                    )
                return LLMModelNotFoundError(
                    f"Unsupported model: {error_message}",
                    provider='doubao',
                    error_code=error_code
                ), user_msg

            if has_chinese:
                user_msg = "模型或者推理接入点不存在或者您无权访问它"
            else:
                user_msg = (
                    "Model or endpoint does not exist or you do not have "
                    "access to it."
                )
            return LLMModelNotFoundError(
                f"Model or endpoint not found: {error_message}",
                provider='doubao',
                error_code=error_code
            ), user_msg

        if has_chinese:
            user_msg = "资源不存在，请检查资源ID"
        else:
            user_msg = "Resource not found. Please check resource ID."
        return LLMProviderError(
            f"Not found: {error_message}",
            provider='doubao',
            error_code=error_code
        ), user_msg

    # ===== 429 TooManyRequests - Rate Limit Errors =====
    if (status_code == 429 or error_code == 'TooManyRequests' or
        'RateLimit' in error_code or 'QuotaExceeded' in error_code):
        # RateLimitExceeded.EndpointRPMExceeded
        if ('EndpointRPMExceeded' in error_code or
            ('rpm' in error_msg_lower and 'endpoint' in error_msg_lower)):
            if has_chinese:
                user_msg = (
                    "请求所关联的推理接入点已超过 RPM (Requests Per Minute) 限制, "
                    "请稍后重试"
                )
            else:
                user_msg = "Endpoint RPM limit exceeded. Please try again later."
            return LLMRateLimitError(f"Endpoint RPM limit exceeded: {error_message}"), user_msg

        # RateLimitExceeded.EndpointTPMExceeded
        if ('EndpointTPMExceeded' in error_code or
            ('tpm' in error_msg_lower and 'endpoint' in error_msg_lower)):
            if has_chinese:
                user_msg = (
                    "请求所关联的推理接入点已超过 TPM (Tokens Per Minute) 限制, "
                    "请稍后重试"
                )
            else:
                user_msg = "Endpoint TPM limit exceeded. Please try again later."
            return LLMRateLimitError(f"Endpoint TPM limit exceeded: {error_message}"), user_msg

        # ModelAccountRpmRateLimitExceeded
        if ('ModelAccountRpmRateLimitExceeded' in error_code or
            ('model' in error_code_lower and 'rpm' in error_code_lower)):
            if has_chinese:
                user_msg = (
                    "请求已超过帐户模型 RPM (Requests Per Minute) 限制: "
                    "请您稍后重试, 或者联系平台技术同学进行解决"
                )
            else:
                user_msg = (
                    "Model account RPM limit exceeded. Please try again later "
                    "or contact platform support."
                )
            return LLMRateLimitError(f"Model account RPM limit exceeded: {error_message}"), user_msg

        # ModelAccountTpmRateLimitExceeded
        if ('ModelAccountTpmRateLimitExceeded' in error_code or
            ('model' in error_code_lower and 'tpm' in error_code_lower)):
            if has_chinese:
                user_msg = (
                    "请求已超过帐户模型 TPM (Tokens Per Minute) 限制: "
                    "请您稍后重试, 或者联系平台技术同学进行解决"
                )
            else:
                user_msg = (
                    "Model account TPM limit exceeded. Please try again later "
                    "or contact platform support."
                )
            return LLMRateLimitError(f"Model account TPM limit exceeded: {error_message}"), user_msg

        # APIAccountRpmRateLimitExceeded
        if ('APIAccountRpmRateLimitExceeded' in error_code or
            ('api' in error_code_lower and 'rpm' in error_code_lower)):
            if has_chinese:
                user_msg = "当前账号该接口的RPM (Requests Per Minute)限制已超出，请稍后重试"
            else:
                user_msg = "API account RPM limit exceeded. Please try again later."
            return LLMRateLimitError(f"API account RPM limit exceeded: {error_message}"), user_msg

        # ModelAccountIpmRateLimitExceeded
        if 'ModelAccountIpmRateLimitExceeded' in error_code or ('ipm' in error_code_lower):
            if has_chinese:
                user_msg = (
                    "请求已超过账户模型 IPM (Images Per Minute) 限制: "
                    "请您稍后重试, 或者联系平台技术同学进行解决"
                )
            else:
                user_msg = (
                    "Model account IPM limit exceeded. Please try again later "
                    "or contact platform support."
                )
            return LLMRateLimitError(f"Model account IPM limit exceeded: {error_message}"), user_msg

        # QuotaExceeded
        if 'QuotaExceeded' in error_code or 'quota' in error_msg_lower:
            if 'free trial' in error_msg_lower or '免费试用' in error_message:
                if has_chinese:
                    user_msg = (
                        "当前账号对模型的免费试用额度已消耗完毕，如需继续调用，"
                        "请前往火山方舟控制台开通管理页开通对应模型服务"
                    )
                else:
                    user_msg = (
                        "Free trial quota exhausted. Please activate model "
                        "service in Ark Console."
                    )
                return LLMQuotaExhaustedError(
                    f"Free trial quota exhausted: {error_message}",
                    provider='doubao',
                    error_code=error_code
                ), user_msg

            if 'usage quota' in error_msg_lower or '限额' in error_message:
                if has_chinese:
                    user_msg = "使用的额度超出限额，将在指定时间重置"
                else:
                    user_msg = "Usage quota exceeded. It will reset at the specified time."
                return LLMQuotaExhaustedError(
                    f"Usage quota exceeded: {error_message}",
                    provider='doubao',
                    error_code=error_code
                ), user_msg

            if has_chinese:
                user_msg = "配额已用尽，请稍后重试或联系平台技术支持"
            else:
                user_msg = (
                    "Quota exceeded. Please try again later or contact "
                    "platform support."
                )
            return LLMQuotaExhaustedError(
                f"Quota exceeded: {error_message}",
                provider='doubao',
                error_code=error_code
            ), user_msg

        # ServerOverloaded
        if ('ServerOverloaded' in error_code or 'server overload' in error_msg_lower or
            '资源紧张' in error_message):
            if has_chinese:
                user_msg = (
                    "服务资源紧张，请您稍后重试。常出现在调用流量突增或刚开始调用"
                    "长时间未使用的推理接入点"
                )
            else:
                user_msg = (
                    "Server overloaded. Please try again later. Common when "
                    "traffic spikes or starting unused endpoints."
                )
            return LLMRateLimitError(f"Server overloaded: {error_message}"), user_msg

        # SetLimitExceeded
        if ('SetLimitExceeded' in error_code or 'inference limit' in error_msg_lower or
            '推理限额' in error_message):
            if has_chinese:
                user_msg = (
                    "当前账号对模型已达到设置的推理限额值，如需继续调用，"
                    "请前往火山方舟控制台开通管理页修改限额值或关闭安心体验模式"
                )
            else:
                user_msg = (
                    "Inference limit reached. Please adjust limit in Ark Console "
                    "or disable Safe Experience Mode."
                )
            return LLMQuotaExhaustedError(
                f"Inference limit exceeded: {error_message}",
                provider='doubao',
                error_code=error_code
            ), user_msg

        # InflightBatchsizeExceeded
        if ('InflightBatchsizeExceeded' in error_code or
            ('concurrent' in error_msg_lower and 'limit' in error_msg_lower)):
            if has_chinese:
                user_msg = (
                    "您已经达到当前充值金额下的最大并发数限制，"
                    "您可以充值解锁更大并发额度或降低并发数"
                )
            else:
                user_msg = (
                    "Concurrent request limit exceeded. Please recharge to unlock "
                    "higher concurrency or reduce concurrency."
                )
            return LLMRateLimitError(f"Concurrent limit exceeded: {error_message}"), user_msg

        # AccountRateLimitExceeded
        if 'AccountRateLimitExceeded' in error_code or ('rpm' in error_msg_lower and 'tpm' in error_msg_lower):
            user_msg = "请求超出RPM / TPM限制" if has_chinese else "Request exceeds RPM / TPM limit."
            return LLMRateLimitError(f"Account rate limit exceeded: {error_message}"), user_msg

        # Generic rate limit
        user_msg = "请求频率超过限制，请稍后重试" if has_chinese else "Rate limit exceeded. Please try again later."
        return LLMRateLimitError(f"Rate limit exceeded: {error_message}"), user_msg

    # ===== 500 InternalServerError =====
    if status_code == 500 or error_code == 'InternalServerError' or 'InternalServiceError' in error_code:
        user_msg = "内部系统异常，请您稍后重试" if has_chinese else "Internal service error. Please try again later."
        return LLMServiceError(f"Internal service error: {error_message}"), user_msg

    # ===== Default: Generic Provider Error =====
    user_msg = f"API错误: {error_message}" if has_chinese else f"API error: {error_message}"
    return LLMProviderError(
        f"Doubao API error ({error_code}): {error_message}",
        provider='doubao',
        error_code=error_code
    ), user_msg


def parse_and_raise_doubao_error(error_code: str, error_message: str, status_code: Optional[int] = None):
    """
    Parse Doubao error and raise appropriate exception.

    Args:
        error_code: Error code from API response
        error_message: Error message from API response
        status_code: HTTP status code (optional)

    Raises:
        Appropriate exception based on error type
    """
    exception, user_message = parse_doubao_error(error_code, error_message, status_code)

    # Log error with details
    logger.error(
        "Doubao API error (%s): %s - %s",
        error_code,
        exception.__class__.__name__,
        str(exception),
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
