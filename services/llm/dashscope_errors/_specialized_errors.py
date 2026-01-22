"""
Specialized Error Parser
========================

Handles specialized errors including WebSocket, Audio/Video, Flow, Schema, etc.
"""
from typing import Optional, Tuple

from services.infrastructure.http.error_handler import (
    LLMInvalidParameterError,
    LLMProviderError,
    LLMServiceError,
    LLMTimeoutError,
    LLMContentFilterError,
    LLMQuotaExhaustedError
)


def parse_specialized_errors(
    error_message: str,
    error_msg_lower: str,
    error_code: str,
    has_chinese: bool,
    status_code: int
) -> Optional[Tuple[Exception, str]]:
    """Parse specialized errors (WebSocket, Audio/Video, Flow, Schema, etc.)."""
    # 409 Conflict
    if status_code == 409:
        if ('already exists' in error_msg_lower and
                'model instance' in error_msg_lower):
            if has_chinese:
                user_msg = "已存在重名的部署实例，请指定不同的后缀名"
            else:
                user_msg = (
                    "Model instance already exists. "
                    "Please specify different suffix."
                )
            return LLMInvalidParameterError(
                f"Model instance conflict: {error_message}",
                parameter='model',
                error_code=error_code or 'Conflict',
                provider='dashscope'
            ), user_msg

    # Content Filter (fallback)
    if (error_code in ['DataInspectionFailed', 'data_inspection_failed',
                       'DataInspection'] and status_code != 400):
        if has_chinese:
            user_msg = "内容可能包含不当信息，请修改输入内容"
        else:
            user_msg = (
                "Content may contain inappropriate information. "
                "Please modify input."
            )
        return LLMContentFilterError(f"Content filter: {error_message}"), user_msg

    # Quota Exhausted (fallback)
    if (error_code in ['Throttling.AllocationQuota', 'Arrearage',
                       'insufficient_quota'] and
            status_code not in [403, 429]):
        if has_chinese:
            user_msg = "配额已用完，请检查账户余额或配额设置"
        else:
            user_msg = (
                "Quota exhausted. Please check account balance or "
                "quota settings."
            )
        return LLMQuotaExhaustedError(
            f"Quota exhausted: {error_message}",
            provider='dashscope',
            error_code=error_code
        ), user_msg

    # WebSocket-specific errors
    if 'websocket' in error_msg_lower or 'ws' in error_msg_lower:
        # Invalid payload
        if 'invalid payload' in error_msg_lower:
            if has_chinese:
                user_msg = "WebSocket payload数据格式错误，请检查JSON格式"
            else:
                user_msg = (
                    "Invalid WebSocket payload format. "
                    "Please check JSON format."
                )
            return LLMInvalidParameterError(
                f"Invalid WebSocket payload: {error_message}",
                parameter='payload',
                error_code=error_code or 'WebSocket.InvalidPayload',
                provider='dashscope'
            ), user_msg

        # Connection timeout
        if 'timeout' in error_msg_lower and 'connection' in error_msg_lower:
            if has_chinese:
                user_msg = "WebSocket连接超时，请检查网络连接和防火墙设置"
            else:
                user_msg = (
                    "WebSocket connection timeout. Please check network and "
                    "firewall settings."
                )
            return LLMTimeoutError(f"WebSocket connection timeout: {error_message}"), user_msg

        # Client disconnect
        if 'client disconnected' in error_msg_lower:
            if has_chinese:
                user_msg = "客户端在任务结束前断开连接，请检查代码逻辑"
            else:
                user_msg = (
                    "Client disconnected before task finished. "
                    "Please check code logic."
                )
            return LLMServiceError(f"Client disconnected: {error_message}"), user_msg

        # Message too big
        if 'message was too big' in error_msg_lower:
            if has_chinese:
                user_msg = "WebSocket消息过大，请分段发送数据"
            else:
                user_msg = (
                    "WebSocket message too big. Please send data in segments."
                )
            return LLMInvalidParameterError(
                f"Message too big: {error_message}",
                parameter='data',
                error_code=error_code or 'WebSocket.MessageTooBig',
                provider='dashscope'
            ), user_msg

    # Audio/Video processing errors
    if 'audio' in error_msg_lower or 'video' in error_msg_lower:
        # Audio format unsupported
        if 'unsupported audio format' in error_msg_lower:
            if has_chinese:
                user_msg = "音频格式不支持，请使用WAV（16bit）、MP3或M4A格式"
            else:
                user_msg = (
                    "Unsupported audio format. Please use WAV (16bit), "
                    "MP3, or M4A."
                )
            return LLMInvalidParameterError(
                f"Unsupported audio format: {error_message}",
                parameter='audio',
                error_code=error_code or 'InvalidParameter.AudioFormat',
                provider='dashscope'
            ), user_msg

        # No valid audio
        if ('no valid audio' in error_msg_lower or
                'no valid audio error' in error_msg_lower):
            if has_chinese:
                user_msg = "未检测到有效语音，请检查音频输入和格式"
            else:
                user_msg = (
                    "No valid audio detected. Please check audio input "
                    "and format."
                )
            return LLMInvalidParameterError(
                f"No valid audio: {error_message}",
                parameter='audio',
                error_code=error_code or 'InvalidParameter.NoValidAudio',
                provider='dashscope'
            ), user_msg

    # Flow/Application errors
    if 'flow' in error_msg_lower:
        # Flow not published
        if (error_code == 'FlowNotPublished' or
                'flow has not published' in error_msg_lower):
            if has_chinese:
                user_msg = "流程未发布，请发布流程后再重试"
            else:
                user_msg = (
                    "Flow not published. Please publish flow and retry."
                )
            return LLMProviderError(
                f"Flow not published: {error_message}",
                provider='dashscope',
                error_code=error_code or 'FlowNotPublished'
            ), user_msg

    # Schema errors
    if 'schema' in error_msg_lower:
        # Invalid schema
        if (error_code == 'InvalidSchema' or
                'database schema is invalid' in error_msg_lower):
            if has_chinese:
                user_msg = "数据库Schema无效，请输入数据库Schema信息"
            else:
                user_msg = (
                    "Invalid database schema. Please input database schema "
                    "information."
                )
            return LLMInvalidParameterError(
                f"Invalid schema: {error_message}",
                parameter='schema',
                error_code=error_code or 'InvalidSchema',
                provider='dashscope'
            ), user_msg

        # Invalid schema format
        if (error_code == 'InvalidSchemaFormat' or
                'schema format is invalid' in error_msg_lower):
            if has_chinese:
                user_msg = "数据库Schema格式错误，请检查并修正数据表信息格式"
            else:
                user_msg = (
                    "Invalid schema format. Please check and correct data "
                    "table format."
                )
            return LLMInvalidParameterError(
                f"Invalid schema format: {error_message}",
                parameter='schema',
                error_code=error_code or 'InvalidSchemaFormat',
                provider='dashscope'
            ), user_msg

    # Unsupported operation errors
    if (error_code == 'UnsupportedOperation' or
            'unsupported operation' in error_msg_lower):
        if has_chinese:
            user_msg = "不支持的操作，请检查操作对象和操作类型是否匹配"
        else:
            user_msg = (
                "Unsupported operation. Please check if operation object "
                "and type match."
            )
        return LLMProviderError(
            f"Unsupported operation: {error_message}",
            provider='dashscope',
            error_code=error_code or 'UnsupportedOperation'
        ), user_msg

    # Service unavailable errors
    if (error_code == 'ServiceUnavailableError' or
            'service unavailable' in error_msg_lower):
        if has_chinese:
            user_msg = "服务不可用，请检查服务状态"
        else:
            user_msg = "Service unavailable. Please check service status."
        return LLMServiceError(f"Service unavailable: {error_message}"), user_msg

    return None
