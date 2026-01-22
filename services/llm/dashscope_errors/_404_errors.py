"""
404 Not Found Error Parser
===========================

Handles resource not found errors.
"""
from typing import Optional, Tuple

from services.infrastructure.http.error_handler import (
    LLMModelNotFoundError,
    LLMInvalidParameterError,
    LLMProviderError
)


def parse_404_errors(
    error_message: str,
    error_msg_lower: str,
    error_code: str,
    has_chinese: bool
) -> Optional[Tuple[Exception, str]]:
    """Parse 404 Not Found errors."""
    # Model not found
    if (error_code == 'ModelNotFound' or
            error_code == 'model_not_found' or
            ('model' in error_msg_lower and
             ('not' in error_msg_lower and 'found' in error_msg_lower))):
        if has_chinese:
            user_msg = (
                "模型不存在，请检查模型名称是否正确（注意大小写）或是否已开通服务"
            )
        else:
            user_msg = (
                "Model not found. Please check model name (case-sensitive) "
                "or if service is enabled."
            )
        return LLMModelNotFoundError(
            f"Model not found: {error_message}",
            provider='dashscope',
            error_code=error_code or 'ModelNotFound'
        ), user_msg

    # Model not supported for OpenAI compatibility
    if (error_code == 'model_not_supported' or
            ('unsupported model' in error_msg_lower and
             'openai compatibility' in error_msg_lower)):
        if has_chinese:
            user_msg = (
                "当前模型不支持OpenAI兼容方式接入，请使用DashScope原生方式调用"
            )
        else:
            user_msg = (
                "Model not supported for OpenAI compatibility. "
                "Please use DashScope native API."
            )
        return LLMInvalidParameterError(
            f"Model not supported for OpenAI compatibility: {error_message}",
            parameter='model',
            error_code=error_code or 'model_not_supported',
            provider='dashscope'
        ), user_msg

    # Workspace not found
    if (error_code == 'WorkSpaceNotFound' or
            ('workspace' in error_msg_lower and
             'not found' in error_msg_lower)):
        user_msg = "工作空间不存在，请检查工作空间ID" if has_chinese else "Workspace not found. Please check workspace ID."
        return LLMProviderError(
            f"Workspace not found: {error_message}",
            provider='dashscope',
            error_code=error_code or 'WorkSpaceNotFound'
        ), user_msg

    # Generic not found
    if 'not found' in error_msg_lower:
        user_msg = "资源不存在，请检查资源ID" if has_chinese else "Resource not found. Please check resource ID."
        return LLMProviderError(
            f"Resource not found: {error_message}",
            provider='dashscope',
            error_code=error_code or 'NotFound'
        ), user_msg

    return None
