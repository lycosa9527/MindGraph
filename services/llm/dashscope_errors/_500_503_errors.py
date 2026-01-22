"""
500 Internal Server Error and 503 Service Unavailable Error Parsers
====================================================================

Handles server-side errors and service unavailability.
"""
from typing import Optional, Tuple

from services.infrastructure.http.error_handler import (
    LLMTimeoutError,
    LLMProviderError,
    LLMServiceError
)


def parse_500_errors(
    error_message: str,
    error_msg_lower: str,
    error_code: str,
    has_chinese: bool
) -> Optional[Tuple[Exception, str]]:
    """Parse 500 Internal Error errors."""
    # Request timeout
    if (error_code == 'InternalError.Timeout' or
            error_code == 'RequestTimeOut' or
            'timeout' in error_msg_lower or
            'timed out' in error_msg_lower):
        if has_chinese:
            user_msg = "请求超时（300秒），建议使用流式输出方式发起请求"
        else:
            user_msg = (
                "Request timeout (300s). Recommend using streaming output."
            )
        return LLMTimeoutError(f"Request timeout: {error_message}"), user_msg

    # File upload error
    if (error_code == 'InternalError.FileUpload' or
            'oss upload error' in error_msg_lower):
        if has_chinese:
            user_msg = "文件上传失败，请检查OSS配置和网络"
        else:
            user_msg = (
                "File upload failed. Please check OSS configuration "
                "and network."
            )
        return LLMProviderError(
            f"File upload error: {error_message}",
            provider='dashscope',
            error_code=error_code or 'InternalError.FileUpload'
        ), user_msg

    # Upload result failed
    if (error_code == 'InternalError.Upload' or
            'failed to upload result' in error_msg_lower):
        if has_chinese:
            user_msg = "生成结果上传失败，请检查存储配置或稍后重试"
        else:
            user_msg = (
                "Failed to upload result. Please check storage configuration "
                "or retry later."
            )
        return LLMProviderError(
            f"Upload result failed: {error_message}",
            provider='dashscope',
            error_code=error_code or 'InternalError.Upload'
        ), user_msg

    # Algorithm error
    if (error_code == 'InternalError.Algo' or
            'inference internal error' in error_msg_lower or
            'algorithm process error' in error_msg_lower):
        if has_chinese:
            user_msg = "算法处理错误，请稍后重试"
        else:
            user_msg = "Algorithm processing error. Please try again later."
        return LLMServiceError(f"Algorithm error: {error_message}"), user_msg

    # Model serving error
    if (error_code == 'ModelServiceFailed' or
            'model serving' in error_msg_lower or
            'inference error' in error_msg_lower):
        if has_chinese:
            user_msg = "模型服务调用失败，请稍后重试"
        else:
            user_msg = "Model service call failed. Please try again later."
        return LLMServiceError(f"Model serving error: {error_message}"), user_msg

    # Plugin invoke failed
    if (error_code == 'InvokePluginFailed' or
            'failed to invoke plugin' in error_msg_lower):
        if has_chinese:
            user_msg = "插件调用失败，请检查插件配置和可用性"
        else:
            user_msg = (
                "Plugin invoke failed. Please check plugin configuration "
                "and availability."
            )
        return LLMServiceError(f"Plugin invoke failed: {error_message}"), user_msg

    # App process failed
    if (error_code == 'AppProcessFailed' or
            'failed to proceed application request' in error_msg_lower):
        if has_chinese:
            user_msg = "应用流程处理失败，请检查应用配置和流程节点"
        else:
            user_msg = (
                "App process failed. Please check app configuration "
                "and flow nodes."
            )
        return LLMServiceError(f"App process failed: {error_message}"), user_msg

    # Rewrite failed
    if (error_code == 'RewriteFailed' or
            'failed to rewrite content' in error_msg_lower):
        if has_chinese:
            user_msg = "Prompt改写失败，请稍后重试"
        else:
            user_msg = "Prompt rewrite failed. Please try again later."
        return LLMServiceError(f"Rewrite failed: {error_message}"), user_msg

    # Retrieval failed
    if (error_code == 'RetrivalFailed' or
            'failed to retrieve data' in error_msg_lower):
        if has_chinese:
            user_msg = "文档检索失败，请检查文档索引和检索配置"
        else:
            user_msg = (
                "Document retrieval failed. Please check document index "
                "and retrieval configuration."
            )
        return LLMServiceError(f"Retrieval failed: {error_message}"), user_msg

    # System error
    if error_code == 'SystemError' or 'system error' in error_msg_lower:
        user_msg = "系统错误，请稍后重试" if has_chinese else "System error. Please try again later."
        return LLMServiceError(f"System error: {error_message}"), user_msg

    # Generic internal error
    if ('internal error' in error_msg_lower or
            'internal server error' in error_msg_lower):
        if has_chinese:
            user_msg = "服务器内部错误，请稍后重试"
        else:
            user_msg = "Internal server error. Please try again later."
        return LLMServiceError(f"Internal error: {error_message}"), user_msg

    if has_chinese:
        user_msg = "服务器内部错误，请稍后重试"
    else:
        user_msg = "Internal server error. Please try again later."
    return LLMServiceError(f"Internal error: {error_message}"), user_msg


def parse_503_errors(
    error_message: str,
    error_msg_lower: str,
    error_code: str,
    has_chinese: bool
) -> Optional[Tuple[Exception, str]]:
    """Parse 503 Service Unavailable errors."""
    # Model serving error
    if (error_code == 'ModelServingError' or
            ('too many requests' in error_msg_lower and
             'system capacity limits' in error_msg_lower)):
        if has_chinese:
            user_msg = "网络资源处于饱和状态，暂时无法处理请求，请稍后再试"
        else:
            user_msg = "Network resources saturated. Please try again later."
        return LLMServiceError(f"Model serving error: {error_message}"), user_msg

    # Model unavailable
    if (error_code == 'ModelUnavailable' or
            'model is unavailable' in error_msg_lower):
        if has_chinese:
            user_msg = "模型暂时无法提供服务，请稍后重试"
        else:
            user_msg = (
                "Model temporarily unavailable. Please try again later."
            )
        return LLMServiceError(f"Model unavailable: {error_message}"), user_msg

    if has_chinese:
        user_msg = "服务暂时不可用，请稍后重试"
    else:
        user_msg = (
            "Service temporarily unavailable. Please try again later."
        )
    return LLMServiceError(f"Service unavailable: {error_message}"), user_msg
