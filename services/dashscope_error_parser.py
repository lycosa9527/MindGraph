"""
DashScope Error Parser
======================

Comprehensive error parsing for Alibaba Cloud DashScope API errors.
Maps error codes and messages to proper exception types with user-friendly messages.

@author lycosa9527
@made_by MindSpring Team
"""

import re
import logging
from typing import Dict, Optional, Tuple
from services.error_handler import (
    LLMServiceError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMContentFilterError,
    LLMProviderError,
    LLMValidationError,
    LLMInvalidParameterError,
    LLMQuotaExhaustedError,
    LLMModelNotFoundError,
    LLMAccessDeniedError
)

logger = logging.getLogger(__name__)


# Exception classes are now defined in error_handler.py


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
            import json
            error_data = json.loads(error_text)
        except (json.JSONDecodeError, TypeError):
            error_data = {}
    
    error_info = error_data.get('error', {})
    error_code = error_info.get('code', '')
    error_message = error_info.get('message', error_text)
    
    # Normalize error message for matching
    error_msg_lower = error_message.lower()
    has_chinese = _has_chinese_characters(error_message)
    
    # ===== 400 Bad Request - Invalid Parameter Errors =====
    if status_code == 400:
        # Enable thinking errors
        if 'enable_thinking' in error_msg_lower and ('must be set to false' in error_msg_lower or 'only support stream' in error_msg_lower):
            user_msg = "思考模式仅支持流式输出，请使用流式调用方式" if has_chinese else "Thinking mode only supports streaming. Please use streaming calls."
            return LLMInvalidParameterError(
                f"Invalid enable_thinking parameter: {error_message}",
                parameter='enable_thinking',
                error_code=error_code or 'InvalidParameter.EnableThinking',
                provider='dashscope'
            ), user_msg
        
        # Thinking budget errors
        if 'thinking_budget' in error_msg_lower and 'must be a positive integer' in error_msg_lower:
            user_msg = "思维链长度参数超出范围，请参考模型列表设置正确的值" if has_chinese else "Thinking budget parameter out of range. Please check model limits."
            return LLMInvalidParameterError(f"Invalid thinking_budget: {error_message}", parameter='thinking_budget', error_code=error_code or 'InvalidParameter.ThinkingBudget'
            , provider='dashscope'), user_msg
        
        # Stream mode required errors
        if 'only support stream mode' in error_msg_lower or 'stream=true' in error_msg_lower:
            user_msg = "该模型仅支持流式输出，请启用流式输出" if has_chinese else "This model only supports streaming. Please enable streaming."
            return LLMInvalidParameterError(f"Stream mode required: {error_message}", parameter='stream', error_code=error_code or 'InvalidParameter.StreamRequired'
            , provider='dashscope'), user_msg
        
        # Enable search errors
        if 'does not support enable_search' in error_msg_lower:
            user_msg = "当前模型不支持联网搜索功能" if has_chinese else "This model does not support web search."
            return LLMInvalidParameterError(f"enable_search not supported: {error_message}", parameter='enable_search', error_code=error_code or 'InvalidParameter.EnableSearch'
            , provider='dashscope'), user_msg
        
        # Language not supported
        if '暂时不支持当前设置的语种' in error_message or 'language' in error_msg_lower and 'not supported' in error_msg_lower:
            user_msg = "不支持当前设置的语种，请使用正确的语种编码" if has_chinese else "Language not supported. Please use correct language code."
            return LLMInvalidParameterError(f"Unsupported language: {error_message}", parameter='source_lang/target_lang', error_code=error_code or 'InvalidParameter.Language'
            , provider='dashscope'), user_msg
        
        # Incremental output errors
        if 'incremental_output' in error_msg_lower:
            user_msg = "思考模式需要启用增量输出，请将incremental_output设置为true" if has_chinese else "Thinking mode requires incremental output. Set incremental_output to true."
            return LLMInvalidParameterError(f"Invalid incremental_output: {error_message}", parameter='incremental_output', error_code=error_code or 'InvalidParameter.IncrementalOutput'
            , provider='dashscope'), user_msg
        
        # Input length errors
        if 'range of input length' in error_msg_lower or 'input length should be' in error_msg_lower:
            user_msg = "输入内容过长，超过了模型限制。请缩短输入内容或开启新对话" if has_chinese else "Input too long. Please shorten input or start new conversation."
            return LLMInvalidParameterError(f"Input length exceeded: {error_message}", parameter='messages', error_code=error_code or 'InvalidParameter.InputLength'
            , provider='dashscope'), user_msg
        
        # Max tokens errors
        if 'range of max_tokens' in error_msg_lower or 'max_tokens should be' in error_msg_lower:
            user_msg = "max_tokens参数超出范围，请参考模型最大输出Token数设置" if has_chinese else "max_tokens out of range. Please check model limits."
            return LLMInvalidParameterError(f"Invalid max_tokens: {error_message}", parameter='max_tokens', error_code=error_code or 'InvalidParameter.MaxTokens'
            , provider='dashscope'), user_msg
        
        # Temperature errors
        if 'temperature should be' in error_msg_lower or ('temperature' in error_msg_lower and 'must be float' in error_msg_lower):
            user_msg = "temperature参数应在[0.0, 2.0)范围内" if has_chinese else "Temperature must be in [0.0, 2.0) range."
            return LLMInvalidParameterError(f"Invalid temperature: {error_message}", parameter='temperature', error_code=error_code or 'InvalidParameter.Temperature'
            , provider='dashscope'), user_msg
        
        # Top_p errors
        if 'range of top_p' in error_msg_lower or ('top_p' in error_msg_lower and 'must be float' in error_msg_lower):
            user_msg = "top_p参数应在(0.0, 1.0]范围内" if has_chinese else "top_p must be in (0.0, 1.0] range."
            return LLMInvalidParameterError(f"Invalid top_p: {error_message}", parameter='top_p', error_code=error_code or 'InvalidParameter.TopP'
            , provider='dashscope'), user_msg
        
        # Top_k errors
        if 'top_k' in error_msg_lower and 'greater than or equal to 0' in error_msg_lower:
            user_msg = "top_k参数应大于等于0" if has_chinese else "top_k must be >= 0."
            return LLMInvalidParameterError(f"Invalid top_k: {error_message}", parameter='top_k', error_code=error_code or 'InvalidParameter.TopK'
            , provider='dashscope'), user_msg
        
        # Repetition penalty errors
        if 'repetition_penalty' in error_msg_lower and 'greater than 0.0' in error_msg_lower:
            user_msg = "repetition_penalty参数应大于0" if has_chinese else "repetition_penalty must be > 0."
            return LLMInvalidParameterError(f"Invalid repetition_penalty: {error_message}", parameter='repetition_penalty', error_code=error_code or 'InvalidParameter.RepetitionPenalty'
            , provider='dashscope'), user_msg
        
        # Presence penalty errors
        if 'presence_penalty' in error_msg_lower and 'in [-2.0, 2.0]' in error_msg_lower:
            user_msg = "presence_penalty参数应在[-2.0, 2.0]范围内" if has_chinese else "presence_penalty must be in [-2.0, 2.0] range."
            return LLMInvalidParameterError(f"Invalid presence_penalty: {error_message}", parameter='presence_penalty', error_code=error_code or 'InvalidParameter.PresencePenalty'
            , provider='dashscope'), user_msg
        
        # Parameter n errors
        if 'range of n should be' in error_msg_lower or ('range of n' in error_msg_lower and '[1, 4]' in error_msg_lower):
            user_msg = "参数n应在[1, 4]范围内" if has_chinese else "Parameter n must be in [1, 4] range."
            return LLMInvalidParameterError(f"Invalid n parameter: {error_message}", parameter='n', error_code=error_code or 'InvalidParameter.N'
            , provider='dashscope'), user_msg
        
        # Seed errors
        if 'range of seed' in error_msg_lower or ('seed' in error_msg_lower and 'must be integer' in error_msg_lower):
            user_msg = "seed参数超出范围，应在[0, 9223372036854775807]范围内" if has_chinese else "Seed parameter out of range. Must be in [0, 9223372036854775807]."
            return LLMInvalidParameterError(f"Invalid seed: {error_message}", parameter='seed', error_code=error_code or 'InvalidParameter.Seed'
            , provider='dashscope'), user_msg
        
        # Stop parameter errors
        if ('stop' in error_msg_lower and 'parameter must be' in error_msg_lower) or ('stop' in error_msg_lower and 'must be of type' in error_msg_lower):
            user_msg = "stop参数格式错误，应为字符串或字符串数组" if has_chinese else "Invalid stop parameter format. Must be string or string array."
            return LLMInvalidParameterError(f"Invalid stop parameter: {error_message}", parameter='stop', error_code=error_code or 'InvalidParameter.Stop'
            , provider='dashscope'), user_msg
        
        # Tool choice errors
        if ('tool_choice' in error_msg_lower and 'should be' in error_msg_lower) or ('tool_choice' in error_msg_lower and 'one of' in error_msg_lower):
            user_msg = "tool_choice参数错误，应为'auto'或'none'" if has_chinese else "tool_choice must be 'auto' or 'none'."
            return LLMInvalidParameterError(f"Invalid tool_choice: {error_message}", parameter='tool_choice', error_code=error_code or 'InvalidParameter.ToolChoice'
            , provider='dashscope'), user_msg
        
        # Result format errors
        if 'result_format' in error_msg_lower and 'must be' in error_msg_lower and 'message' in error_msg_lower:
            user_msg = "思考模式需要将result_format设置为'message'" if has_chinese else "Thinking mode requires result_format to be 'message'."
            return LLMInvalidParameterError(f"Invalid result_format: {error_message}", parameter='result_format', error_code=error_code or 'InvalidParameter.ResultFormat'
            , provider='dashscope'), user_msg
        
        # Request method errors
        if 'request method' in error_msg_lower and 'not supported' in error_msg_lower:
            user_msg = "请求方法不支持，请使用POST方法" if has_chinese else "Request method not supported. Please use POST method."
            return LLMInvalidParameterError(f"Invalid request method: {error_message}", parameter='method', error_code=error_code or 'InvalidParameter.RequestMethod'
            , provider='dashscope'), user_msg
        
        # Messages with tool role errors
        if 'messages with role "tool"' in error_msg_lower or ('tool' in error_msg_lower and 'must be a response' in error_msg_lower):
            user_msg = "工具调用消息格式错误，请先添加Assistant消息" if has_chinese else "Invalid tool message format. Add Assistant message first."
            return LLMInvalidParameterError(f"Invalid tool message format: {error_message}", parameter='messages', error_code=error_code or 'InvalidParameter.ToolMessage'
            , provider='dashscope'), user_msg
        
        # Required body errors
        if 'required body invalid' in error_msg_lower or 'request body format' in error_msg_lower:
            user_msg = "请求体格式错误，请检查JSON格式" if has_chinese else "Invalid request body format. Please check JSON format."
            return LLMInvalidParameterError(f"Invalid request body: {error_message}", parameter='body', error_code=error_code or 'InvalidParameter.RequestBody'
            , provider='dashscope'), user_msg
        
        # Content field errors
        if 'content field is a required field' in error_msg_lower or ('content' in error_msg_lower and 'must be a string' in error_msg_lower):
            user_msg = "content字段是必需的，且必须为字符串类型" if has_chinese else "Content field is required and must be a string."
            return LLMInvalidParameterError(f"Invalid content field: {error_message}", parameter='content', error_code=error_code or 'InvalidParameter.Content'
            , provider='dashscope'), user_msg
        
        # Prompt or messages required
        if ('prompt' in error_msg_lower and 'messages' in error_msg_lower and 'must exist' in error_msg_lower) or ('either' in error_msg_lower and 'prompt' in error_msg_lower and 'messages' in error_msg_lower):
            user_msg = "必须提供prompt或messages参数" if has_chinese else "Either 'prompt' or 'messages' must be provided."
            return LLMInvalidParameterError(f"Missing prompt or messages: {error_message}", parameter='prompt/messages', error_code=error_code or 'InvalidParameter.PromptOrMessages'
            , provider='dashscope'), user_msg
        
        # JSON mode response format errors
        if 'messages' in error_msg_lower and 'must contain' in error_msg_lower and 'json' in error_msg_lower and 'response_format' in error_msg_lower:
            user_msg = "使用JSON模式时，提示词中需包含'json'关键词" if has_chinese else "When using JSON mode, prompt must contain 'json' keyword."
            return LLMInvalidParameterError(f"JSON mode requires 'json' in prompt: {error_message}", parameter='messages/response_format', error_code=error_code or 'InvalidParameter.JsonModePrompt'
            , provider='dashscope'), user_msg
        
        # Tool names errors
        if 'tool names' in error_msg_lower and 'not allowed' in error_msg_lower and 'search' in error_msg_lower:
            user_msg = "工具名称不能设置为'search'" if has_chinese else "Tool name cannot be 'search'."
            return LLMInvalidParameterError(f"Invalid tool name: {error_message}", parameter='tools', error_code=error_code or 'InvalidParameter.ToolName'
            , provider='dashscope'), user_msg
        
        # Response format errors
        if 'unknown format of response_format' in error_msg_lower or ('response_format' in error_msg_lower and 'should be a dict' in error_msg_lower):
            user_msg = "response_format格式错误，应为{'type': 'json_object'}" if has_chinese else "Invalid response_format. Should be {'type': 'json_object'}."
            return LLMInvalidParameterError(f"Invalid response_format: {error_message}", parameter='response_format', error_code=error_code or 'InvalidParameter.ResponseFormat'
            , provider='dashscope'), user_msg
        
        # Enable thinking restricted errors
        if ('enable_thinking' in error_msg_lower and 'restricted to true' in error_msg_lower) or ('enable_thinking' in error_msg_lower and 'must be true' in error_msg_lower):
            user_msg = "该模型必须启用思考模式，请将enable_thinking设置为true" if has_chinese else "This model requires thinking mode. Set enable_thinking to true."
            return LLMInvalidParameterError(f"enable_thinking must be true: {error_message}", parameter='enable_thinking', error_code=error_code or 'InvalidParameter.EnableThinkingRequired'
            , provider='dashscope'), user_msg
        
        # Audio output stream errors
        if 'audio' in error_msg_lower and 'output only support' in error_msg_lower and 'stream' in error_msg_lower:
            user_msg = "音频输出仅支持流式输出，请设置stream=true" if has_chinese else "Audio output only supports streaming. Set stream=true."
            return LLMInvalidParameterError(f"Audio output requires streaming: {error_message}", parameter='stream', error_code=error_code or 'InvalidParameter.AudioStream'
            , provider='dashscope'), user_msg
        
        # Empty messages array
        if ('is too short' in error_msg_lower and 'messages' in error_msg_lower) or ('messages' in error_msg_lower and 'empty' in error_msg_lower):
            user_msg = "messages数组不能为空，请添加消息" if has_chinese else "Messages array cannot be empty. Please add messages."
            return LLMInvalidParameterError(f"Empty messages array: {error_message}", parameter='messages', error_code=error_code or 'InvalidParameter.EmptyMessages'
            , provider='dashscope'), user_msg
        
        # Tool call not supported
        if ('tool call' in error_msg_lower and 'not supported' in error_msg_lower) or ('does not support' in error_msg_lower and 'tools' in error_msg_lower):
            user_msg = "该模型不支持工具调用功能" if has_chinese else "This model does not support tool calling."
            return LLMInvalidParameterError(f"Tool calling not supported: {error_message}", parameter='tools', error_code=error_code or 'InvalidParameter.ToolCallNotSupported'
            , provider='dashscope'), user_msg
        
        # Required parameter missing
        if 'required parameter' in error_msg_lower and ('missing' in error_msg_lower or 'invalid' in error_msg_lower):
            user_msg = f"缺少必需参数: {error_message}" if has_chinese else f"Missing required parameter: {error_message}"
            return LLMInvalidParameterError(f"Missing required parameter: {error_message}", parameter=None, error_code=error_code or 'InvalidParameter.MissingParameter'
            , provider='dashscope'), user_msg
        
        # Model not found
        if 'model not exist' in error_msg_lower or ('model' in error_msg_lower and 'does not exist' in error_msg_lower):
            user_msg = "模型不存在或名称错误，请检查模型名称" if has_chinese else "Model not found. Please check model name."
            return LLMModelNotFoundError(
                f"Model not found: {error_message}",
                provider='dashscope',
                error_code=error_code or 'ModelNotFound'
            ), user_msg
        
        # Messages format errors
        if ('messages' in error_msg_lower and 'must contain' in error_msg_lower) or ('messages' in error_msg_lower and 'required' in error_msg_lower):
            user_msg = "消息格式错误，请检查messages参数" if has_chinese else "Invalid messages format. Please check messages parameter."
            return LLMInvalidParameterError(f"Invalid messages format: {error_message}", parameter='messages', error_code=error_code or 'InvalidParameter.Messages'
            , provider='dashscope'), user_msg
        
        # JSON mode errors
        if 'json mode' in error_msg_lower and 'not supported' in error_msg_lower:
            user_msg = "思考模式不支持JSON结构化输出，请关闭思考模式" if has_chinese else "JSON mode not supported with thinking mode. Disable thinking mode."
            return LLMInvalidParameterError(f"JSON mode conflict: {error_message}", parameter='response_format/enable_thinking', error_code=error_code or 'InvalidParameter.JsonMode'
            , provider='dashscope'), user_msg
        
        # Generic invalid parameter
        if 'invalid' in error_msg_lower and ('parameter' in error_msg_lower or 'value' in error_msg_lower):
            user_msg = f"参数错误: {error_message}" if has_chinese else f"Invalid parameter: {error_message}"
            return LLMInvalidParameterError(f"Invalid parameter: {error_message}", parameter=None, error_code=error_code or 'InvalidParameter'
            , provider='dashscope'), user_msg
    
    # ===== 401 Unauthorized =====
    if status_code == 401:
        if 'invalid api' in error_msg_lower or 'api.*key' in error_msg_lower or error_code in ['InvalidApiKey', 'invalid_api_key']:
            user_msg = "API密钥无效，请检查API密钥配置" if has_chinese else "Invalid API key. Please check API key configuration."
            return LLMAccessDeniedError(
                f"Invalid API key: {error_message}",
                provider='dashscope',
                error_code=error_code or 'InvalidApiKey'
            ), user_msg
        
        if 'not authorized' in error_msg_lower or 'unauthorized' in error_msg_lower:
            user_msg = "未授权访问，请检查权限设置" if has_chinese else "Not authorized. Please check permissions."
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
    
    # ===== 403 Access Denied =====
    if status_code == 403:
        if 'quota' in error_msg_lower or 'allocation' in error_msg_lower or 'arrearage' in error_msg_lower:
            user_msg = "配额已用完或账户欠费，请检查账户状态" if has_chinese else "Quota exhausted or account in arrears. Please check account status."
            return LLMQuotaExhaustedError(
                f"Quota exhausted: {error_message}",
                provider='dashscope',
                error_code=error_code or 'AccessDenied.Quota'
            ), user_msg
        
        if 'access denied' in error_msg_lower or 'model access denied' in error_msg_lower:
            user_msg = "无权访问此模型，请检查模型权限" if has_chinese else "Access denied to model. Please check model permissions."
            return LLMAccessDeniedError(
                f"Model access denied: {error_message}",
                provider='dashscope',
                error_code=error_code or 'AccessDenied.Model'
            ), user_msg
        
        if 'app access denied' in error_msg_lower or 'workspace access denied' in error_msg_lower:
            user_msg = "无权访问应用或工作空间，请检查权限设置" if has_chinese else "Access denied to app or workspace. Please check permissions."
            return LLMAccessDeniedError(
                f"App/Workspace access denied: {error_message}",
                provider='dashscope',
                error_code=error_code or 'AccessDenied.App'
            ), user_msg
        
        if ('not support' in error_msg_lower and 'asynchronous' in error_msg_lower) or ('not support' in error_msg_lower and 'synchronous' in error_msg_lower):
            user_msg = "接口不支持当前调用方式，请检查调用模式" if has_chinese else "Interface does not support current call mode. Please check call mode."
            return LLMInvalidParameterError(f"Call mode not supported: {error_message}", parameter='async/sync', error_code=error_code or 'AccessDenied.CallMode'
            , provider='dashscope'), user_msg
        
        user_msg = "访问被拒绝，请检查权限设置" if has_chinese else "Access denied. Please check permissions."
        return LLMAccessDeniedError(
            f"Access denied: {error_message}",
            provider='dashscope',
            error_code=error_code or 'AccessDenied'
        ), user_msg
    
    # ===== 404 Not Found =====
    if status_code == 404:
        if 'model' in error_msg_lower and ('not' in error_msg_lower and 'found' in error_msg_lower):
            user_msg = "模型不存在，请检查模型名称" if has_chinese else "Model not found. Please check model name."
            return LLMModelNotFoundError(
                f"Model not found: {error_message}",
                provider='dashscope',
                error_code=error_code or 'ModelNotFound'
            ), user_msg
        
        if 'workspace' in error_msg_lower or 'not found' in error_msg_lower:
            user_msg = "资源不存在，请检查资源ID" if has_chinese else "Resource not found. Please check resource ID."
            return LLMProviderError(
                f"Resource not found: {error_message}",
                provider='dashscope',
                error_code=error_code or 'NotFound'
            ), user_msg
    
    # ===== 429 Rate Limit =====
    if status_code == 429:
        if 'rate limit exceeded' in error_msg_lower or 'throttling' in error_msg_lower:
            user_msg = "请求过于频繁，请稍后重试" if has_chinese else "Rate limit exceeded. Please try again later."
            return LLMRateLimitError(f"Rate limit: {error_message}"), user_msg
        
        if 'burst rate' in error_msg_lower or 'rate increased too quickly' in error_msg_lower:
            user_msg = "请求频率增长过快，请平滑请求速率" if has_chinese else "Request rate increased too quickly. Please smooth request rate."
            return LLMRateLimitError(f"Burst rate limit: {error_message}"), user_msg
        
        if 'allocation quota' in error_msg_lower or 'quota exceeded' in error_msg_lower:
            user_msg = "配额已用完，请检查配额设置" if has_chinese else "Quota exceeded. Please check quota settings."
            return LLMQuotaExhaustedError(
                f"Quota exceeded: {error_message}",
                provider='dashscope',
                error_code=error_code or 'Throttling.AllocationQuota'
            ), user_msg
        
        user_msg = "请求过于频繁，请稍后重试" if has_chinese else "Rate limit exceeded. Please try again later."
        return LLMRateLimitError(f"Rate limit: {error_message}"), user_msg
    
    # ===== 500 Internal Error =====
    if status_code == 500:
        if 'timeout' in error_msg_lower or 'timed out' in error_msg_lower:
            user_msg = "请求超时，请稍后重试" if has_chinese else "Request timeout. Please try again later."
            return LLMTimeoutError(f"Timeout: {error_message}"), user_msg
        
        if 'internal error' in error_msg_lower or 'internal server error' in error_msg_lower:
            user_msg = "服务器内部错误，请稍后重试" if has_chinese else "Internal server error. Please try again later."
            return LLMServiceError(f"Internal error: {error_message}"), user_msg
        
        if 'model serving' in error_msg_lower or 'inference error' in error_msg_lower:
            user_msg = "模型服务错误，请稍后重试" if has_chinese else "Model serving error. Please try again later."
            return LLMServiceError(f"Model serving error: {error_message}"), user_msg
        
        user_msg = "服务器内部错误，请稍后重试" if has_chinese else "Internal server error. Please try again later."
        return LLMServiceError(f"Internal error: {error_message}"), user_msg
    
    # ===== Content Filter =====
    if error_code in ['DataInspectionFailed', 'data_inspection_failed', 'DataInspection'] or \
       'inappropriate content' in error_msg_lower or 'content filter' in error_msg_lower or \
       'data inspection' in error_msg_lower:
        user_msg = "内容可能包含不当信息，请修改输入内容" if has_chinese else "Content may contain inappropriate information. Please modify input."
        return LLMContentFilterError(f"Content filter: {error_message}"), user_msg
    
    # IP Infringement
    if 'ip infringement' in error_msg_lower or 'intellectual property' in error_msg_lower:
        user_msg = "输入内容涉嫌知识产权侵权，请检查输入内容" if has_chinese else "Input may involve intellectual property infringement. Please check input."
        return LLMContentFilterError(f"IP infringement: {error_message}"), user_msg
    
    # FAQ Rule Blocked
    if 'faq rule' in error_msg_lower or 'blocked by faq' in error_msg_lower:
        user_msg = "输入或输出数据被FAQ规则拦截" if has_chinese else "Input or output blocked by FAQ rule."
        return LLMContentFilterError(f"FAQ rule blocked: {error_message}"), user_msg
    
    # Custom Role Blocked
    if 'custom rule' in error_msg_lower or 'custom role blocked' in error_msg_lower:
        user_msg = "输入或输出数据未通过自定义策略" if has_chinese else "Input or output failed custom policy check."
        return LLMContentFilterError(f"Custom rule blocked: {error_message}"), user_msg
    
    # ===== Quota Exhausted =====
    if error_code in ['Throttling.AllocationQuota', 'Arrearage', 'insufficient_quota']:
        user_msg = "配额已用完，请检查账户余额或配额设置" if has_chinese else "Quota exhausted. Please check account balance or quota settings."
        return LLMQuotaExhaustedError(
            f"Quota exhausted: {error_message}",
            provider='dashscope',
            error_code=error_code
        ), user_msg
    
    # ===== Default: Generic Provider Error =====
    user_msg = f"API错误: {error_message}" if has_chinese else f"API error: {error_message}"
    return LLMProviderError(
        f"DashScope API error ({status_code}): {error_message}",
        provider='dashscope',
        error_code=error_code or f'HTTP{status_code}'
    ), user_msg


def parse_and_raise_dashscope_error(status_code: int, error_text: str, error_data: Optional[Dict] = None):
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
        f"DashScope API error ({status_code}): {exception.__class__.__name__} - {str(exception)}",
        extra={
            'status_code': status_code,
            'error_code': getattr(exception, 'error_code', None),
            'parameter': getattr(exception, 'parameter', None),
            'user_message': user_message
        }
    )
    
    # Attach user-friendly message to exception
    exception.user_message = user_message
    
    raise exception

