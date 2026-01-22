"""
401 Unauthorized and 403 Access Denied Error Parsers
====================================================

Handles authentication and authorization errors.
"""
from typing import Optional, Tuple

from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMInvalidParameterError,
    LLMQuotaExhaustedError,
    LLMProviderError
)


def parse_401_errors(
    error_message: str,
    error_msg_lower: str,
    error_code: str,
    has_chinese: bool
) -> Optional[Tuple[Exception, str]]:
    """Parse 401 Unauthorized errors."""
    if ('invalid api' in error_msg_lower or
            'api.*key' in error_msg_lower or
            error_code in ['InvalidApiKey', 'invalid_api_key']):
        if has_chinese:
            user_msg = (
                "API密钥无效，请检查API密钥配置。常见原因：环境变量读取错误、"
                "密钥填写错误、地域不匹配"
            )
        else:
            user_msg = (
                "Invalid API key. Common causes: environment variable read "
                "error, incorrect key, region mismatch."
            )
        return LLMAccessDeniedError(
            f"Invalid API key: {error_message}",
            provider='dashscope',
            error_code=error_code or 'InvalidApiKey'
        ), user_msg

    if ('not authorized' in error_msg_lower or
            'unauthorized' in error_msg_lower):
        if has_chinese:
            user_msg = "未授权访问，请检查权限设置"
        else:
            user_msg = "Not authorized. Please check permissions."
        return LLMAccessDeniedError(
            f"Unauthorized: {error_message}",
            provider='dashscope',
            error_code=error_code or 'Unauthorized'
        ), user_msg

    user_msg = "认证失败，请检查API密钥" if has_chinese else "Authentication failed. Please check API key."
    return LLMAccessDeniedError(
        f"Unauthorized: {error_message}",
        provider='dashscope',
        error_code=error_code or 'Unauthorized'
    ), user_msg


def parse_403_errors(
    error_message: str,
    error_msg_lower: str,
    error_code: str,
    has_chinese: bool
) -> Optional[Tuple[Exception, str]]:
    """Parse 403 Access Denied errors."""
    # Quota exhausted
    if error_code == 'AccessDenied.Unpurchased' or 'not purchased' in error_msg_lower:
        user_msg = "未开通阿里云百炼服务，请先开通服务" if has_chinese else "Service not purchased. Please purchase service first."
        return LLMAccessDeniedError(
            f"Service not purchased: {error_message}",
            provider='dashscope',
            error_code=error_code or 'AccessDenied.Unpurchased'
        ), user_msg

    # Model access denied
    if (error_code == 'Model.AccessDenied' or
            'model access denied' in error_msg_lower):
        if has_chinese:
            user_msg = "无权访问此模型，请检查模型权限或申请模型访问权限"
        else:
            user_msg = (
                "Access denied to model. Please check model permissions or "
                "apply for access."
            )
        return LLMAccessDeniedError(
            f"Model access denied: {error_message}",
            provider='dashscope',
            error_code=error_code or 'Model.AccessDenied'
        ), user_msg

    # App access denied
    if (error_code == 'App.AccessDenied' or
            'app access denied' in error_msg_lower):
        if has_chinese:
            user_msg = "无权访问应用，请检查应用权限和发布状态"
        else:
            user_msg = (
                "Access denied to app. Please check app permissions and "
                "publish status."
            )
        return LLMAccessDeniedError(
            f"App access denied: {error_message}",
            provider='dashscope',
            error_code=error_code or 'App.AccessDenied'
        ), user_msg

    # Workspace access denied
    if (error_code == 'Workspace.AccessDenied' or
            'workspace access denied' in error_msg_lower):
        if has_chinese:
            user_msg = "无权访问工作空间，请检查工作空间权限"
        else:
            user_msg = (
                "Access denied to workspace. Please check workspace "
                "permissions."
            )
        return LLMAccessDeniedError(
            f"Workspace access denied: {error_message}",
            provider='dashscope',
            error_code=error_code or 'Workspace.AccessDenied'
        ), user_msg

    # Free tier only
    if (error_code == 'AllocationQuota.FreeTierOnly' or
            ('free tier' in error_msg_lower and
             'exhausted' in error_msg_lower)):
        if has_chinese:
            user_msg = (
                "免费额度已用完，如需付费调用请关闭'免费额度用完即停'模式"
            )
        else:
            user_msg = (
                "Free tier exhausted. To continue with paid calls, disable "
                "'free tier only' mode."
            )
        return LLMQuotaExhaustedError(
            f"Free tier exhausted: {error_message}",
            provider='dashscope',
            error_code=error_code or 'AllocationQuota.FreeTierOnly'
        ), user_msg

    # Policy expired
    if 'policy expired' in error_msg_lower:
        if has_chinese:
            user_msg = "文件上传凭证已过期，请重新生成凭证"
        else:
            user_msg = (
                "File upload credential expired. Please regenerate credential."
            )
        return LLMProviderError(
            f"Policy expired: {error_message}",
            provider='dashscope',
            error_code=error_code or 'AccessDenied.PolicyExpired'
        ), user_msg

    # Call mode not supported
    if (('not support' in error_msg_lower and
         'asynchronous' in error_msg_lower) or
            ('not support' in error_msg_lower and
             'synchronous' in error_msg_lower)):
        if has_chinese:
            user_msg = "接口不支持当前调用方式，请检查调用模式"
        else:
            user_msg = (
                "Interface does not support current call mode. "
                "Please check call mode."
            )
        return LLMInvalidParameterError(
            f"Call mode not supported: {error_message}",
            parameter='async/sync',
            error_code=error_code or 'AccessDenied.CallMode',
            provider='dashscope'
        ), user_msg

    # Generic access denied
    if has_chinese:
        user_msg = "访问被拒绝，请检查权限设置"
    else:
        user_msg = "Access denied. Please check permissions."
    return LLMAccessDeniedError(
        f"Access denied: {error_message}",
        provider='dashscope',
        error_code=error_code or 'AccessDenied'
    ), user_msg
