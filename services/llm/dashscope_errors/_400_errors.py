"""
400 Bad Request Error Parsers
==============================

Handles all 400 status code errors including parameter validation,
file errors, audio/video errors, and other bad request scenarios.
"""
from typing import Optional, Tuple
import re

from services.infrastructure.http.error_handler import (
    LLMInvalidParameterError,
    LLMProviderError,
    LLMModelNotFoundError
)


def _parse_400_bad_request_errors(
    error_message: str,
    error_msg_lower: str,
    error_code: str,
    has_chinese: bool
) -> Optional[Tuple[Exception, str]]:
    """
    Parse 400 Bad Request - Invalid Parameter Errors.

    This helper function handles all 400 status code parameter validation errors
    to reduce complexity in the main parse function.

    Returns:
        Tuple of (exception, user_message) if error matches, None otherwise
    """
    # Enable thinking errors
    if ('enable_thinking' in error_msg_lower and
        ('must be set to false' in error_msg_lower or
         'only support stream' in error_msg_lower)):
        if has_chinese:
            user_msg = "思考模式仅支持流式输出，请使用流式调用方式"
        else:
            user_msg = "Thinking mode only supports streaming. Please use streaming calls."
        return LLMInvalidParameterError(
            f"Invalid enable_thinking parameter: {error_message}",
            parameter='enable_thinking',
            error_code=error_code or 'InvalidParameter.EnableThinking',
            provider='dashscope'
        ), user_msg

    # Thinking budget errors
    if ('thinking_budget' in error_msg_lower and
        'must be a positive integer' in error_msg_lower):
        if has_chinese:
            user_msg = "思维链长度参数超出范围，请参考模型列表设置正确的值"
        else:
            user_msg = "Thinking budget parameter out of range. Please check model limits."
        return LLMInvalidParameterError(
            f"Invalid thinking_budget: {error_message}",
            parameter='thinking_budget',
            error_code=error_code or 'InvalidParameter.ThinkingBudget',
            provider='dashscope'
        ), user_msg

    # Stream mode required errors
    if ('only support stream mode' in error_msg_lower or
        'stream=true' in error_msg_lower):
        if has_chinese:
            user_msg = "该模型仅支持流式输出，请启用流式输出"
        else:
            user_msg = "This model only supports streaming. Please enable streaming."
        return LLMInvalidParameterError(
            f"Stream mode required: {error_message}",
            parameter='stream',
            error_code=error_code or 'InvalidParameter.StreamRequired',
            provider='dashscope'
        ), user_msg

    # Enable search errors
    if 'does not support enable_search' in error_msg_lower:
        if has_chinese:
            user_msg = "当前模型不支持联网搜索功能"
        else:
            user_msg = "This model does not support web search."
        return LLMInvalidParameterError(
            f"enable_search not supported: {error_message}",
            parameter='enable_search',
            error_code=error_code or 'InvalidParameter.EnableSearch',
            provider='dashscope'
        ), user_msg

    # Language not supported
    if ('暂时不支持当前设置的语种' in error_message or
        ('language' in error_msg_lower and 'not supported' in error_msg_lower)):
        if has_chinese:
            user_msg = "不支持当前设置的语种，请使用正确的语种编码"
        else:
            user_msg = "Language not supported. Please use correct language code."
        return LLMInvalidParameterError(
            f"Unsupported language: {error_message}",
            parameter='source_lang/target_lang',
            error_code=error_code or 'InvalidParameter.Language',
            provider='dashscope'
        ), user_msg

    # Incremental output errors
    if 'incremental_output' in error_msg_lower:
        if has_chinese:
            user_msg = "思考模式需要启用增量输出，请将incremental_output设置为true"
        else:
            user_msg = (
                "Thinking mode requires incremental output. "
                "Set incremental_output to true."
            )
        return LLMInvalidParameterError(
            f"Invalid incremental_output: {error_message}",
            parameter='incremental_output',
            error_code=error_code or 'InvalidParameter.IncrementalOutput',
            provider='dashscope'
        ), user_msg

    # Input length errors
    if ('range of input length' in error_msg_lower or
        'input length should be' in error_msg_lower):
        if has_chinese:
            user_msg = "输入内容过长，超过了模型限制。请缩短输入内容或开启新对话"
        else:
            user_msg = "Input too long. Please shorten input or start new conversation."
        return LLMInvalidParameterError(
            f"Input length exceeded: {error_message}",
            parameter='messages',
            error_code=error_code or 'InvalidParameter.InputLength',
            provider='dashscope'
        ), user_msg

    # Max tokens errors
    if ('range of max_tokens' in error_msg_lower or
        'max_tokens should be' in error_msg_lower):
        if has_chinese:
            user_msg = "max_tokens参数超出范围，请参考模型最大输出Token数设置"
        else:
            user_msg = "max_tokens out of range. Please check model limits."
        return LLMInvalidParameterError(
            f"Invalid max_tokens: {error_message}",
            parameter='max_tokens',
            error_code=error_code or 'InvalidParameter.MaxTokens',
            provider='dashscope'
        ), user_msg

    # Temperature errors
    if ('temperature should be' in error_msg_lower or
        ('temperature' in error_msg_lower and 'must be float' in error_msg_lower)):
        if has_chinese:
            user_msg = "temperature参数应在[0.0, 2.0)范围内"
        else:
            user_msg = "Temperature must be in [0.0, 2.0) range."
        return LLMInvalidParameterError(
            f"Invalid temperature: {error_message}",
            parameter='temperature',
            error_code=error_code or 'InvalidParameter.Temperature',
            provider='dashscope'
        ), user_msg

    # Top_p errors
    if ('range of top_p' in error_msg_lower or
        ('top_p' in error_msg_lower and 'must be float' in error_msg_lower)):
        if has_chinese:
            user_msg = "top_p参数应在(0.0, 1.0]范围内"
        else:
            user_msg = "top_p must be in (0.0, 1.0] range."
        return LLMInvalidParameterError(
            f"Invalid top_p: {error_message}",
            parameter='top_p',
            error_code=error_code or 'InvalidParameter.TopP',
            provider='dashscope'
        ), user_msg

    # Top_k errors
    if ('top_k' in error_msg_lower and
        'greater than or equal to 0' in error_msg_lower):
        if has_chinese:
            user_msg = "top_k参数应大于等于0"
        else:
            user_msg = "top_k must be >= 0."
        return LLMInvalidParameterError(
            f"Invalid top_k: {error_message}",
            parameter='top_k',
            error_code=error_code or 'InvalidParameter.TopK',
            provider='dashscope'
        ), user_msg

    # Repetition penalty errors
    if ('repetition_penalty' in error_msg_lower and
        'greater than 0.0' in error_msg_lower):
        if has_chinese:
            user_msg = "repetition_penalty参数应大于0"
        else:
            user_msg = "repetition_penalty must be > 0."
        return LLMInvalidParameterError(
            f"Invalid repetition_penalty: {error_message}",
            parameter='repetition_penalty',
            error_code=error_code or 'InvalidParameter.RepetitionPenalty',
            provider='dashscope'
        ), user_msg

    # Presence penalty errors
    if ('presence_penalty' in error_msg_lower and
        'in [-2.0, 2.0]' in error_msg_lower):
        if has_chinese:
            user_msg = "presence_penalty参数应在[-2.0, 2.0]范围内"
        else:
            user_msg = "presence_penalty must be in [-2.0, 2.0] range."
        return LLMInvalidParameterError(
            f"Invalid presence_penalty: {error_message}",
            parameter='presence_penalty',
            error_code=error_code or 'InvalidParameter.PresencePenalty',
            provider='dashscope'
        ), user_msg

    # Parameter n errors
    if ('range of n should be' in error_msg_lower or
        ('range of n' in error_msg_lower and '[1, 4]' in error_msg_lower)):
        if has_chinese:
            user_msg = "参数n应在[1, 4]范围内"
        else:
            user_msg = "Parameter n must be in [1, 4] range."
        return LLMInvalidParameterError(
            f"Invalid n parameter: {error_message}",
            parameter='n',
            error_code=error_code or 'InvalidParameter.N',
            provider='dashscope'
        ), user_msg

    # Seed errors
    if ('range of seed' in error_msg_lower or
        ('seed' in error_msg_lower and 'must be integer' in error_msg_lower)):
        if has_chinese:
            user_msg = "seed参数超出范围，应在[0, 9223372036854775807]范围内"
        else:
            user_msg = (
                "Seed parameter out of range. "
                "Must be in [0, 9223372036854775807]."
            )
        return LLMInvalidParameterError(
            f"Invalid seed: {error_message}",
            parameter='seed',
            error_code=error_code or 'InvalidParameter.Seed',
            provider='dashscope'
        ), user_msg

    # Stop parameter errors
    if (('stop' in error_msg_lower and 'parameter must be' in error_msg_lower) or
        ('stop' in error_msg_lower and 'must be of type' in error_msg_lower)):
        if has_chinese:
            user_msg = "stop参数格式错误，应为字符串或字符串数组"
        else:
            user_msg = (
                "Invalid stop parameter format. "
                "Must be string or string array."
            )
        return LLMInvalidParameterError(
            f"Invalid stop parameter: {error_message}",
            parameter='stop',
            error_code=error_code or 'InvalidParameter.Stop',
            provider='dashscope'
        ), user_msg

    # Tool choice errors
    if (('tool_choice' in error_msg_lower and 'should be' in error_msg_lower) or
        ('tool_choice' in error_msg_lower and 'one of' in error_msg_lower)):
        if has_chinese:
            user_msg = "tool_choice参数错误，应为'auto'或'none'"
        else:
            user_msg = "tool_choice must be 'auto' or 'none'."
        return LLMInvalidParameterError(
            f"Invalid tool_choice: {error_message}",
            parameter='tool_choice',
            error_code=error_code or 'InvalidParameter.ToolChoice',
            provider='dashscope'
        ), user_msg

    # Result format errors
    if ('result_format' in error_msg_lower and 'must be' in error_msg_lower and
        'message' in error_msg_lower):
        if has_chinese:
            user_msg = "思考模式需要将result_format设置为'message'"
        else:
            user_msg = "Thinking mode requires result_format to be 'message'."
        return LLMInvalidParameterError(
            f"Invalid result_format: {error_message}",
            parameter='result_format',
            error_code=error_code or 'InvalidParameter.ResultFormat',
            provider='dashscope'
        ), user_msg

    # Request method errors
    if ('request method' in error_msg_lower and
        'not supported' in error_msg_lower):
        if has_chinese:
            user_msg = "请求方法不支持，请使用POST方法"
        else:
            user_msg = "Request method not supported. Please use POST method."
        return LLMInvalidParameterError(
            f"Invalid request method: {error_message}",
            parameter='method',
            error_code=error_code or 'InvalidParameter.RequestMethod',
            provider='dashscope'
        ), user_msg

    # Messages with tool role errors
    if ('messages with role "tool"' in error_msg_lower or
        ('tool' in error_msg_lower and 'must be a response' in error_msg_lower)):
        if has_chinese:
            user_msg = "工具调用消息格式错误，请先添加Assistant消息"
        else:
            user_msg = "Invalid tool message format. Add Assistant message first."
        return LLMInvalidParameterError(
            f"Invalid tool message format: {error_message}",
            parameter='messages',
            error_code=error_code or 'InvalidParameter.ToolMessage',
            provider='dashscope'
        ), user_msg

    return None


def parse_400_errors(
    error_message: str,
    error_msg_lower: str,
    error_code: str,
    has_chinese: bool
) -> Optional[Tuple[Exception, str]]:
    """
    Parse 400 Bad Request errors.

    Returns:
        Tuple of (exception, user_message) if error matches, None otherwise
    """
    # Try helper function first to reduce complexity
    result = _parse_400_bad_request_errors(
        error_message, error_msg_lower, error_code, has_chinese
    )
    if result is not None:
        return result

    # Try extended 400 errors
    result = _parse_400_extended_errors(
        error_message, error_msg_lower, error_code, has_chinese
    )
    if result is not None:
        return result

    return None


def _parse_400_extended_errors(
    error_message: str,
    error_msg_lower: str,
    error_code: str,
    has_chinese: bool
) -> Optional[Tuple[Exception, str]]:
    """
    Parse extended 400 Bad Request errors not covered by _parse_400_bad_request_errors.

    Returns:
        Tuple of (exception, user_message) if error matches, None otherwise
    """
    # Required body errors
    if ('required body invalid' in error_msg_lower or
        'request body format' in error_msg_lower):
        if has_chinese:
            user_msg = "请求体格式错误，请检查JSON格式"
        else:
            user_msg = "Invalid request body format. Please check JSON format."
        return LLMInvalidParameterError(
            f"Invalid request body: {error_message}",
            parameter='body',
            error_code=error_code or 'InvalidParameter.RequestBody',
            provider='dashscope'
        ), user_msg

    # Content field errors
    if ('content field is a required field' in error_msg_lower or
        ('content' in error_msg_lower and 'must be a string' in error_msg_lower)):
        if has_chinese:
            user_msg = "content字段是必需的，且必须为字符串类型"
        else:
            user_msg = "Content field is required and must be a string."
        return LLMInvalidParameterError(
            f"Invalid content field: {error_message}",
            parameter='content',
            error_code=error_code or 'InvalidParameter.Content',
            provider='dashscope'
        ), user_msg

    # Prompt or messages required
    if (('prompt' in error_msg_lower and 'messages' in error_msg_lower and
         'must exist' in error_msg_lower) or
        ('either' in error_msg_lower and 'prompt' in error_msg_lower and
         'messages' in error_msg_lower)):
        if has_chinese:
            user_msg = "必须提供prompt或messages参数"
        else:
            user_msg = "Either 'prompt' or 'messages' must be provided."
        return LLMInvalidParameterError(
            f"Missing prompt or messages: {error_message}",
            parameter='prompt/messages',
            error_code=error_code or 'InvalidParameter.PromptOrMessages',
            provider='dashscope'
        ), user_msg

    # JSON mode response format errors
    if ('messages' in error_msg_lower and 'must contain' in error_msg_lower and
        'json' in error_msg_lower and 'response_format' in error_msg_lower):
        if has_chinese:
            user_msg = "使用JSON模式时，提示词中需包含'json'关键词"
        else:
            user_msg = "When using JSON mode, prompt must contain 'json' keyword."
        return LLMInvalidParameterError(
            f"JSON mode requires 'json' in prompt: {error_message}",
            parameter='messages/response_format',
            error_code=error_code or 'InvalidParameter.JsonModePrompt',
            provider='dashscope'
        ), user_msg

    # Tool names errors
    if ('tool names' in error_msg_lower and 'not allowed' in error_msg_lower and
        'search' in error_msg_lower):
        if has_chinese:
            user_msg = "工具名称不能设置为'search'"
        else:
            user_msg = "Tool name cannot be 'search'."
        return LLMInvalidParameterError(
            f"Invalid tool name: {error_message}",
            parameter='tools',
            error_code=error_code or 'InvalidParameter.ToolName',
            provider='dashscope'
        ), user_msg

    # Response format errors
    if ('unknown format of response_format' in error_msg_lower or
        ('response_format' in error_msg_lower and
         'should be a dict' in error_msg_lower)):
        if has_chinese:
            user_msg = "response_format格式错误，应为{'type': 'json_object'}"
        else:
            user_msg = "Invalid response_format. Should be {'type': 'json_object'}."
        return LLMInvalidParameterError(
            f"Invalid response_format: {error_message}",
            parameter='response_format',
            error_code=error_code or 'InvalidParameter.ResponseFormat',
            provider='dashscope'
        ), user_msg

    # Enable thinking restricted errors
    if (('enable_thinking' in error_msg_lower and
         'restricted to true' in error_msg_lower) or
        ('enable_thinking' in error_msg_lower and
         'must be true' in error_msg_lower)):
        if has_chinese:
            user_msg = "该模型必须启用思考模式，请将enable_thinking设置为true"
        else:
            user_msg = "This model requires thinking mode. Set enable_thinking to true."
        return LLMInvalidParameterError(
            f"enable_thinking must be true: {error_message}",
            parameter='enable_thinking',
            error_code=error_code or 'InvalidParameter.EnableThinkingRequired',
            provider='dashscope'
        ), user_msg

    # Audio output stream errors
    if ('audio' in error_msg_lower and 'output only support' in error_msg_lower and
        'stream' in error_msg_lower):
        if has_chinese:
            user_msg = "音频输出仅支持流式输出，请设置stream=true"
        else:
            user_msg = "Audio output only supports streaming. Set stream=true."
        return LLMInvalidParameterError(
            f"Audio output requires streaming: {error_message}",
            parameter='stream',
            error_code=error_code or 'InvalidParameter.AudioStream',
            provider='dashscope'
        ), user_msg

    # Empty messages array
    if (('is too short' in error_msg_lower and 'messages' in error_msg_lower) or
        ('messages' in error_msg_lower and 'empty' in error_msg_lower)):
        if has_chinese:
            user_msg = "messages数组不能为空，请添加消息"
        else:
            user_msg = "Messages array cannot be empty. Please add messages."
        return LLMInvalidParameterError(
            f"Empty messages array: {error_message}",
            parameter='messages',
            error_code=error_code or 'InvalidParameter.EmptyMessages',
            provider='dashscope'
        ), user_msg

    # Tool call not supported
    if (('tool call' in error_msg_lower and 'not supported' in error_msg_lower) or
        ('does not support' in error_msg_lower and 'tools' in error_msg_lower)):
        if has_chinese:
            user_msg = "该模型不支持工具调用功能"
        else:
            user_msg = "This model does not support tool calling."
        return LLMInvalidParameterError(
            f"Tool calling not supported: {error_message}",
            parameter='tools',
            error_code=error_code or 'InvalidParameter.ToolCallNotSupported',
            provider='dashscope'
        ), user_msg

    # Required parameter missing
    if ('required parameter' in error_msg_lower and
        ('missing' in error_msg_lower or 'invalid' in error_msg_lower)):
        if has_chinese:
            user_msg = f"缺少必需参数: {error_message}"
        else:
            user_msg = f"Missing required parameter: {error_message}"
        return LLMInvalidParameterError(
            f"Missing required parameter: {error_message}",
            parameter=None,
            error_code=error_code or 'InvalidParameter.MissingParameter',
            provider='dashscope'
        ), user_msg

    # Model not found
    if ('model not exist' in error_msg_lower or
        ('model' in error_msg_lower and 'does not exist' in error_msg_lower)):
        if has_chinese:
            user_msg = "模型不存在或名称错误，请检查模型名称"
        else:
            user_msg = "Model not found. Please check model name."
        return LLMModelNotFoundError(
            f"Model not found: {error_message}",
            provider='dashscope',
            error_code=error_code or 'ModelNotFound'
        ), user_msg

    # Messages format errors
    if (('messages' in error_msg_lower and 'must contain' in error_msg_lower) or
        ('messages' in error_msg_lower and 'required' in error_msg_lower)):
        if has_chinese:
            user_msg = "消息格式错误，请检查messages参数"
        else:
            user_msg = "Invalid messages format. Please check messages parameter."
        return LLMInvalidParameterError(
            f"Invalid messages format: {error_message}",
            parameter='messages',
            error_code=error_code or 'InvalidParameter.Messages',
            provider='dashscope'
        ), user_msg

    # JSON mode errors
    if ('json mode' in error_msg_lower and
        'not supported' in error_msg_lower):
        if has_chinese:
            user_msg = "思考模式不支持JSON结构化输出，请关闭思考模式"
        else:
            user_msg = (
                "JSON mode not supported with thinking mode. "
                "Disable thinking mode."
            )
        return LLMInvalidParameterError(
            f"JSON mode conflict: {error_message}",
            parameter='response_format/enable_thinking',
            error_code=error_code or 'InvalidParameter.JsonMode',
            provider='dashscope'
        ), user_msg

    # File-related errors (400-InvalidFile.*)
    if (error_code.startswith('InvalidFile.') or
        'invalid file' in error_msg_lower):
        # File download errors
        if ('download' in error_msg_lower and
            ('failed' in error_msg_lower or 'timeout' in error_msg_lower)):
            if has_chinese:
                user_msg = "文件下载失败或超时，请检查文件URL是否可访问"
            else:
                user_msg = (
                    "File download failed or timeout. "
                    "Please check if file URL is accessible."
                )
            return LLMProviderError(
                f"File download error: {error_message}",
                provider='dashscope',
                error_code=error_code or 'InvalidFile.DownloadFailed'
            ), user_msg

        # File format errors
        if ('format' in error_msg_lower and
            ('not supported' in error_msg_lower or 'illegal' in error_msg_lower)):
            if has_chinese:
                user_msg = "文件格式不支持，请检查文件格式"
            else:
                user_msg = "File format not supported. Please check file format."
            return LLMInvalidParameterError(
                f"Invalid file format: {error_message}",
                parameter='file',
                error_code=error_code or 'InvalidFile.Format',
                provider='dashscope'
            ), user_msg

        # File size errors
        if ('size' in error_msg_lower and
            ('exceed' in error_msg_lower or 'too large' in error_msg_lower)):
            if has_chinese:
                user_msg = "文件大小超出限制，请压缩文件"
            else:
                user_msg = "File size exceeds limit. Please compress file."
            return LLMInvalidParameterError(
                f"File too large: {error_message}",
                parameter='file',
                error_code=error_code or 'InvalidFile.Size',
                provider='dashscope'
            ), user_msg

        # File duration errors
        if ('duration' in error_msg_lower and
            ('exceed' in error_msg_lower or 'too long' in error_msg_lower)):
            if has_chinese:
                user_msg = "文件时长超出限制，请缩短文件时长"
            else:
                user_msg = "File duration exceeds limit. Please shorten file duration."
            return LLMInvalidParameterError(
                f"File duration too long: {error_message}",
                parameter='file',
                error_code=error_code or 'InvalidFile.Duration',
                provider='dashscope'
            ), user_msg

        # Audio length errors
        if ('audio length' in error_msg_lower or
            ('audio' in error_msg_lower and 'between' in error_msg_lower and
             's' in error_msg_lower)):
            if has_chinese:
                user_msg = "音频时长不符合要求，请确保音频时长在指定范围内"
            else:
                user_msg = (
                    "Audio duration not in required range. "
                    "Please ensure audio duration is within limits."
                )
            return LLMInvalidParameterError(
                f"Invalid audio length: {error_message}",
                parameter='audio',
                error_code=error_code or 'InvalidFile.AudioLengthError',
                provider='dashscope'
            ), user_msg

        # Image resolution errors
        if ('resolution' in error_msg_lower or
            ('image' in error_msg_lower and
             ('size' in error_msg_lower or 'dimension' in error_msg_lower))):
            if has_chinese:
                user_msg = "图像分辨率不符合要求，请调整图像尺寸"
            else:
                user_msg = (
                    "Image resolution not in required range. "
                    "Please adjust image size."
                )
            return LLMInvalidParameterError(
                f"Invalid image resolution: {error_message}",
                parameter='image',
                error_code=error_code or 'InvalidFile.Resolution',
                provider='dashscope'
            ), user_msg

        # Video FPS errors
        if 'fps' in error_msg_lower and 'must be' in error_msg_lower:
            if has_chinese:
                user_msg = "视频帧率不符合要求，应在15-60fps之间"
            else:
                user_msg = "Video FPS not in required range (15-60fps)."
            return LLMInvalidParameterError(
                f"Invalid video FPS: {error_message}",
                parameter='video',
                error_code=error_code or 'InvalidFile.FPS',
                provider='dashscope'
            ), user_msg

        # Human body detection errors
        if ('no human' in error_msg_lower or
            'human body' in error_msg_lower):
            if has_chinese:
                user_msg = "图片中未检测到人体，请上传包含人体的图片"
            else:
                user_msg = (
                    "No human body detected. "
                    "Please upload image with human body."
                )
            return LLMInvalidParameterError(
                f"No human body detected: {error_message}",
                parameter='image',
                error_code=error_code or 'InvalidFile.NoHuman',
                provider='dashscope'
            ), user_msg

        # Face detection errors
        if ('face' in error_msg_lower and
            ('not detected' in error_msg_lower or 'invalid' in error_msg_lower)):
            if has_chinese:
                user_msg = "未检测到人脸或人脸不符合要求，请上传包含清晰人脸的图片"
            else:
                user_msg = (
                    "Face not detected or invalid. "
                    "Please upload image with clear face."
                )
            return LLMInvalidParameterError(
                f"Face detection error: {error_message}",
                parameter='image',
                error_code=error_code or 'InvalidFile.Face',
                provider='dashscope'
            ), user_msg

        # File parsing errors
        if ('parsing' in error_msg_lower or
            ('parse' in error_msg_lower and 'failed' in error_msg_lower)):
            if has_chinese:
                user_msg = "文件解析失败，请检查文件是否损坏"
            else:
                user_msg = "File parsing failed. Please check if file is corrupted."
            return LLMProviderError(
                f"File parsing error: {error_message}",
                provider='dashscope',
                error_code=error_code or 'InvalidFile.ParseFailed'
            ), user_msg

        # File not found
        if ('cannot be found' in error_msg_lower or
            'not found' in error_msg_lower):
            if has_chinese:
                user_msg = "文件不存在，请检查文件ID或URL"
            else:
                user_msg = "File not found. Please check file ID or URL."
            return LLMProviderError(
                f"File not found: {error_message}",
                provider='dashscope',
                error_code=error_code or 'InvalidFile.NotFound'
            ), user_msg

        # File content blank
        if ('content blank' in error_msg_lower or
            'content is empty' in error_msg_lower):
            if has_chinese:
                user_msg = "文件内容为空，请确保文件内容不为空"
            else:
                user_msg = "File content is empty. Please ensure file has content."
            return LLMInvalidParameterError(
                f"File content blank: {error_message}",
                parameter='file',
                error_code=error_code or 'InvalidFile.Content',
                provider='dashscope'
            ), user_msg

    # Audio-related errors (400-Audio.*)
    if (error_code.startswith('Audio.') or
        ('audio' in error_msg_lower and
         ('error' in error_msg_lower or 'failed' in error_msg_lower))):
        # Audio decoder errors
        if 'decoder' in error_msg_lower or 'decode' in error_msg_lower:
            if has_chinese:
                user_msg = "音频解码失败，请检查音频文件格式和编码"
            else:
                user_msg = (
                    "Audio decode failed. Please check audio file format "
                    "and encoding."
                )
            return LLMProviderError(
                f"Audio decode error: {error_message}",
                provider='dashscope',
                error_code=error_code or 'Audio.DecoderError'
            ), user_msg

        # Audio sample rate errors
        if ('sample rate' in error_msg_lower or
            'rate unsupported' in error_msg_lower):
            if has_chinese:
                user_msg = "音频采样率不支持，采样率需大于等于24000 Hz"
            else:
                user_msg = (
                    "Audio sample rate unsupported. "
                    "Sample rate must be >= 24000 Hz."
                )
            return LLMInvalidParameterError(
                f"Invalid audio sample rate: {error_message}",
                parameter='audio',
                error_code=error_code or 'Audio.AudioRateError',
                provider='dashscope'
            ), user_msg

        # Audio duration limit errors
        if ('duration exceeds' in error_msg_lower or
            'duration limit' in error_msg_lower):
            if has_chinese:
                user_msg = "音频时长超出限制，请缩短音频时长"
            else:
                user_msg = "Audio duration exceeds limit. Please shorten audio duration."
            return LLMInvalidParameterError(
                f"Audio duration limit exceeded: {error_message}",
                parameter='audio',
                error_code=error_code or 'Audio.DurationLimitError',
                provider='dashscope'
            ), user_msg

        # Audio silent errors
        if ('silent' in error_msg_lower or
            'no valid audio' in error_msg_lower):
            if has_chinese:
                user_msg = "音频为静音或无效，请确保音频包含有效语音"
            else:
                user_msg = (
                    "Audio is silent or invalid. "
                    "Please ensure audio contains valid speech."
                )
            return LLMInvalidParameterError(
                f"Silent audio error: {error_message}",
                parameter='audio',
                error_code=error_code or 'Audio.AudioSilentError',
                provider='dashscope'
            ), user_msg

        # Audio too short
        if 'too short' in error_msg_lower and 'audio' in error_msg_lower:
            if has_chinese:
                user_msg = "音频时长过短，请确保音频时长在10-15秒之间"
            else:
                user_msg = (
                    "Audio too short. Please ensure audio duration is "
                    "10-15 seconds."
                )
            return LLMInvalidParameterError(
                f"Audio too short: {error_message}",
                parameter='audio',
                error_code=error_code or 'Audio.AudioShortError',
                provider='dashscope'
            ), user_msg

        # Audio preprocess errors
        if 'preprocess' in error_msg_lower:
            if has_chinese:
                user_msg = "音频预处理失败，请检查音频质量和格式"
            else:
                user_msg = (
                    "Audio preprocessing failed. "
                    "Please check audio quality and format."
                )
            return LLMProviderError(
                f"Audio preprocess error: {error_message}",
                provider='dashscope',
                error_code=error_code or 'Audio.PreprocessError'
            ), user_msg

    # Image-related errors (400-InvalidImage.*)
    if (error_code.startswith('InvalidImage.') or
        ('image' in error_msg_lower and 'invalid' in error_msg_lower)):
        # Image size errors
        if ('image size' in error_msg_lower or
            ('size' in error_msg_lower and 'beyond limit' in error_msg_lower)):
            if has_chinese:
                user_msg = "图片大小超出限制，请调整图片尺寸"
            else:
                user_msg = "Image size exceeds limit. Please adjust image size."
            return LLMInvalidParameterError(
                f"Image size error: {error_message}",
                parameter='image',
                error_code=error_code or 'InvalidImage.ImageSize',
                provider='dashscope'
            ), user_msg

        # Image format errors
        if ('format' in error_msg_lower and
            'invalid' in error_msg_lower):
            if has_chinese:
                user_msg = "图片格式无效，请使用支持的格式（JPEG, PNG, BMP, WEBP等）"
            else:
                user_msg = (
                    "Invalid image format. Please use supported formats "
                    "(JPEG, PNG, BMP, WEBP, etc.)."
                )
            return LLMInvalidParameterError(
                f"Invalid image format: {error_message}",
                parameter='image',
                error_code=error_code or 'InvalidImage.Format',
                provider='dashscope'
            ), user_msg

        # Image resolution errors
        if ('resolution' in error_msg_lower and
            ('too large' in error_msg_lower or 'too small' in error_msg_lower)):
            if has_chinese:
                user_msg = "图片分辨率过大或过小，请调整图片分辨率"
            else:
                user_msg = (
                    "Image resolution too large or too small. "
                    "Please adjust image resolution."
                )
            return LLMInvalidParameterError(
                f"Invalid image resolution: {error_message}",
                parameter='image',
                error_code=error_code or 'InvalidImage.Resolution',
                provider='dashscope'
            ), user_msg

        # No human face errors
        if ('no human face' in error_msg_lower or
            'face not detected' in error_msg_lower):
            if has_chinese:
                user_msg = "未检测到人脸，请上传包含清晰人脸的图片"
            else:
                user_msg = "No human face detected. Please upload image with clear face."
            return LLMInvalidParameterError(
                f"No human face detected: {error_message}",
                parameter='image',
                error_code=error_code or 'InvalidImage.NoHumanFace',
                provider='dashscope'
            ), user_msg

    # URL-related errors (400-InvalidURL.*)
    if (error_code.startswith('InvalidURL.') or
        ('url' in error_msg_lower and 'invalid' in error_msg_lower)):
        # URL connection refused
        if 'connection refused' in error_msg_lower:
            if has_chinese:
                user_msg = "URL连接被拒绝，请提供可用的URL"
            else:
                user_msg = "URL connection refused. Please provide available URL."
            return LLMProviderError(
                f"URL connection refused: {error_message}",
                provider='dashscope',
                error_code=error_code or 'InvalidURL.ConnectionRefused'
            ), user_msg

        # URL timeout
        if 'timeout' in error_msg_lower and 'url' in error_msg_lower:
            if has_chinese:
                user_msg = "URL下载超时，请检查网络连接"
            else:
                user_msg = "URL download timeout. Please check network connection."
            return LLMProviderError(
                f"URL timeout: {error_message}",
                provider='dashscope',
                error_code=error_code or 'InvalidURL.Timeout'
            ), user_msg

        # Invalid URL format
        if ('does not appear to be valid' in error_msg_lower or
            'url format' in error_msg_lower):
            if has_chinese:
                user_msg = "URL格式无效，请确保URL格式正确（http://、https://或data:开头）"
            else:
                user_msg = (
                    "Invalid URL format. Ensure URL starts with http://, "
                    "https://, or data:."
                )
            return LLMInvalidParameterError(
                f"Invalid URL format: {error_message}",
                parameter='url',
                error_code=error_code or 'InvalidURL',
                provider='dashscope'
            ), user_msg

    # BadRequest errors (400-BadRequest.*)
    if (error_code.startswith('BadRequest.') or
        'bad request' in error_msg_lower):
        # Empty input
        if ('empty input' in error_msg_lower or
            'required input parameter missing' in error_msg_lower):
            if has_chinese:
                user_msg = "缺少必需的input参数，请在请求中添加input参数"
            else:
                user_msg = (
                    "Missing required input parameter. "
                    "Please add input parameter to request."
                )
            return LLMInvalidParameterError(
                f"Empty input: {error_message}",
                parameter='input',
                error_code=error_code or 'BadRequest.EmptyInput',
                provider='dashscope'
            ), user_msg

        # Empty parameters
        if ('empty parameters' in error_msg_lower or
            'required parameter "parameters" missing' in error_msg_lower):
            if has_chinese:
                user_msg = "缺少必需的parameters参数，请在请求中添加parameters参数"
            else:
                user_msg = (
                    "Missing required parameters. "
                    "Please add parameters to request."
                )
            return LLMInvalidParameterError(
                f"Empty parameters: {error_message}",
                parameter='parameters',
                error_code=error_code or 'BadRequest.EmptyParameters',
                provider='dashscope'
            ), user_msg

        # Empty model
        if ('empty model' in error_msg_lower or
            'required parameter "model" missing' in error_msg_lower):
            if has_chinese:
                user_msg = "缺少必需的model参数，请在请求中添加model参数"
            else:
                user_msg = (
                    "Missing required model parameter. "
                    "Please add model parameter to request."
                )
            return LLMInvalidParameterError(
                f"Empty model: {error_message}",
                parameter='model',
                error_code=error_code or 'BadRequest.EmptyModel',
                provider='dashscope'
            ), user_msg

        # Illegal input
        if ('illegal input' in error_msg_lower or
            'input parameter requires json format' in error_msg_lower):
            if has_chinese:
                user_msg = "输入参数格式错误，需要JSON格式"
            else:
                user_msg = "Input parameter format error. Requires JSON format."
            return LLMInvalidParameterError(
                f"Illegal input: {error_message}",
                parameter='input',
                error_code=error_code or 'BadRequest.IllegalInput',
                provider='dashscope'
            ), user_msg

        # Input download failed
        if ('input download failed' in error_msg_lower or
            'failed to download the input file' in error_msg_lower):
            if has_chinese:
                user_msg = "输入文件下载失败，请检查文件URL"
            else:
                user_msg = "Input file download failed. Please check file URL."
            return LLMProviderError(
                f"Input download failed: {error_message}",
                provider='dashscope',
                error_code=error_code or 'BadRequest.InputDownloadFailed'
            ), user_msg

        # Unsupported file format
        if ('unsupported file format' in error_msg_lower or
            'file format unsupported' in error_msg_lower):
            if has_chinese:
                user_msg = "文件格式不支持，请使用支持的文件格式"
            else:
                user_msg = "File format not supported. Please use supported file format."
            return LLMInvalidParameterError(
                f"Unsupported file format: {error_message}",
                parameter='file',
                error_code=error_code or 'BadRequest.UnsupportedFileFormat',
                provider='dashscope'
            ), user_msg

        # Too large
        if 'too large' in error_msg_lower and 'payload' in error_msg_lower:
            if has_chinese:
                user_msg = "文件大小超出限制，请压缩文件"
            else:
                user_msg = "File too large. Please compress file."
            return LLMInvalidParameterError(
                f"Payload too large: {error_message}",
                parameter='file',
                error_code=error_code or 'BadRequest.TooLarge',
                provider='dashscope'
            ), user_msg

        # Resource not exist
        if ('resource not exist' in error_msg_lower or
            'required resource not exist' in error_msg_lower):
            if has_chinese:
                user_msg = "资源不存在，请检查资源ID"
            else:
                user_msg = "Resource not exist. Please check resource ID."
            return LLMProviderError(
                f"Resource not exist: {error_message}",
                provider='dashscope',
                error_code=error_code or 'BadRequest.ResourceNotExist'
            ), user_msg

        # Voice not found
        if ('voice' in error_msg_lower and
            'not found' in error_msg_lower):
            if has_chinese:
                user_msg = "音色不存在，请检查音色ID"
            else:
                user_msg = "Voice not found. Please check voice ID."
            return LLMProviderError(
                f"Voice not found: {error_message}",
                provider='dashscope',
                error_code=error_code or 'BadRequest.VoiceNotFound'
            ), user_msg

    # Video-related errors
    if 'video' in error_msg_lower:
        # Video modality errors
        if ('video modality' in error_msg_lower and
            'does not meet' in error_msg_lower):
            if has_chinese:
                user_msg = "视频输入不符合要求，请检查视频格式和参数"
            else:
                user_msg = (
                    "Video input does not meet requirements. "
                    "Please check video format and parameters."
                )
            return LLMInvalidParameterError(
                f"Invalid video modality: {error_message}",
                parameter='video',
                error_code=error_code or 'InvalidParameter.VideoModality',
                provider='dashscope'
            ), user_msg

        # Video too long
        if 'video' in error_msg_lower and 'too long' in error_msg_lower:
            if has_chinese:
                user_msg = "视频时长过长，请缩短视频时长"
            else:
                user_msg = "Video too long. Please shorten video duration."
            return LLMInvalidParameterError(
                f"Video too long: {error_message}",
                parameter='video',
                error_code=error_code or 'InvalidParameter.VideoDuration',
                provider='dashscope'
            ), user_msg

        # Invalid video file
        if 'invalid video file' in error_msg_lower:
            if has_chinese:
                user_msg = "视频文件无效，请检查视频文件是否损坏"
            else:
                user_msg = "Invalid video file. Please check if video file is corrupted."
            return LLMInvalidParameterError(
                f"Invalid video file: {error_message}",
                parameter='video',
                error_code=error_code or 'InvalidParameter.VideoFile',
                provider='dashscope'
            ), user_msg

    # Multimodal content errors
    if ('multimodal' in error_msg_lower or
        ('content' in error_msg_lower and
         ('modal' in error_msg_lower or 'image_url' in error_msg_lower))):
        # Content must be string for text models
        if ('content must be a string' in error_msg_lower or
            'input content must be a string' in error_msg_lower):
            if has_chinese:
                user_msg = "纯文本模型不支持多模态内容，请将content设置为字符串"
            else:
                user_msg = (
                    "Text-only models do not support multimodal content. "
                    "Set content to string."
                )
            return LLMInvalidParameterError(
                f"Content must be string: {error_message}",
                parameter='content',
                error_code=error_code or 'InvalidParameter.ContentType',
                provider='dashscope'
            ), user_msg

        # Missing image or text
        if 'lack of image or text' in error_msg_lower:
            if has_chinese:
                user_msg = "缺少image或text字段，请添加image或text字段"
            else:
                user_msg = "Missing image or text field. Please add image or text field."
            return LLMInvalidParameterError(
                f"Missing image or text: {error_message}",
                parameter='content',
                error_code=error_code or 'InvalidParameter.MissingContent',
                provider='dashscope'
            ), user_msg

    # File upload errors
    if ('file upload' in error_msg_lower or
        ('upload' in error_msg_lower and
         ('failed' in error_msg_lower or 'error' in error_msg_lower))):
        if has_chinese:
            user_msg = "文件上传失败，请检查文件大小和格式"
        else:
            user_msg = "File upload failed. Please check file size and format."
        return LLMProviderError(
            f"File upload error: {error_message}",
            provider='dashscope',
            error_code=error_code or 'InternalError.FileUpload'
        ), user_msg

    # Batch-related errors
    if 'batch' in error_msg_lower:
        # Model not supported for batch
        if 'not supported by the batch api' in error_msg_lower:
            if has_chinese:
                user_msg = "当前模型不支持Batch调用，请使用其他调用方式"
            else:
                user_msg = (
                    "Model not supported for Batch API. "
                    "Please use other call methods."
                )
            return LLMInvalidParameterError(
                f"Batch not supported: {error_message}",
                parameter='model',
                error_code=error_code or 'ModelNotFound.Batch',
                provider='dashscope'
            ), user_msg

        # Mismatched model in batch
        if ('mismatched_model' in error_msg_lower or
            'does not match the rest of the batch' in error_msg_lower):
            if has_chinese:
                user_msg = "Batch中所有请求必须使用同一模型"
            else:
                user_msg = "All requests in batch must use the same model."
            return LLMInvalidParameterError(
                f"Mismatched model in batch: {error_message}",
                parameter='model',
                error_code=error_code or 'InvalidParameter.BatchModel',
                provider='dashscope'
            ), user_msg

        # Duplicate custom_id in batch
        if 'duplicate_custom_id' in error_msg_lower:
            if has_chinese:
                user_msg = "Batch中请求ID重复，请确保每个请求ID唯一"
            else:
                user_msg = (
                    "Duplicate custom_id in batch. "
                    "Ensure each request ID is unique."
                )
            return LLMInvalidParameterError(
                f"Duplicate custom_id: {error_message}",
                parameter='custom_id',
                error_code=error_code or 'InvalidParameter.DuplicateId',
                provider='dashscope'
            ), user_msg

    # Embedding errors
    if ('embedding' in error_msg_lower or
        'batch size' in error_msg_lower):
        # Batch size invalid
        if 'batch size is invalid' in error_msg_lower:
            if has_chinese:
                user_msg = "文本数量超过模型上限，请减少文本数量"
            else:
                user_msg = (
                    "Text count exceeds model limit. "
                    "Please reduce text count."
                )
            return LLMInvalidParameterError(
                f"Invalid batch size: {error_message}",
                parameter='input',
                error_code=error_code or 'InvalidParameter.BatchSize',
                provider='dashscope'
            ), user_msg

        # Contents format error
        if 'contents is neither str nor list' in error_msg_lower:
            if has_chinese:
                user_msg = "输入格式错误，应为字符串或字符串列表"
            else:
                user_msg = (
                    "Invalid input format. "
                    "Should be string or list of strings."
                )
            return LLMInvalidParameterError(
                f"Invalid contents format: {error_message}",
                parameter='input',
                error_code=error_code or 'InvalidParameter.Contents',
                provider='dashscope'
            ), user_msg

    # Total message token length errors
    if ('total message token length exceed' in error_msg_lower or
        'token length exceed' in error_msg_lower):
        if has_chinese:
            user_msg = "输入总长度超过10,000,000 Token限制，请缩短输入内容"
        else:
            user_msg = (
                "Total message token length exceeds 10,000,000 limit. "
                "Please shorten input."
            )
        return LLMInvalidParameterError(
            f"Token length exceeded: {error_message}",
            parameter='messages',
            error_code=error_code or 'InvalidParameter.TokenLength',
            provider='dashscope'
        ), user_msg

    # Parameter validation errors
    # Field required errors
    if 'field required' in error_msg_lower or 'required parameter' in error_msg_lower:
        # Extract field name if possible
        field_match = re.search(r'required.*?[:\s]+([a-z_]+)', error_msg_lower)
        field_name = field_match.group(1) if field_match else None
        if has_chinese:
            user_msg = f"缺少必需参数: {field_name or 'unknown'}"
        else:
            user_msg = f"Missing required parameter: {field_name or 'unknown'}"
        return LLMInvalidParameterError(
            f"Missing required parameter: {error_message}",
            parameter=field_name,
            error_code=error_code or 'InvalidParameter.MissingParameter',
            provider='dashscope'
        ), user_msg

    # Parameter type errors
    if ('must be' in error_msg_lower and
        ('type' in error_msg_lower or 'integer' in error_msg_lower or
         'float' in error_msg_lower)):
        if has_chinese:
            user_msg = f"参数类型错误: {error_message}"
        else:
            user_msg = f"Invalid parameter type: {error_message}"
        return LLMInvalidParameterError(
            f"Invalid parameter type: {error_message}",
            parameter=None,
            error_code=error_code or 'InvalidParameter.Type',
            provider='dashscope'
        ), user_msg

    # Parameter value out of range
    if 'out of definition' in error_msg_lower or 'out of range' in error_msg_lower or 'not in' in error_msg_lower:
        user_msg = f"参数值超出范围: {error_message}" if has_chinese else f"Parameter value out of range: {error_message}"
        return LLMInvalidParameterError(
            f"Parameter value out of range: {error_message}",
            parameter=None,
            error_code=error_code or 'InvalidParameter.Value',
            provider='dashscope'
        ), user_msg

    # Request parameter invalid
    if ('request parameter is invalid' in error_msg_lower or
        ('request parameter' in error_msg_lower and 'invalid' in error_msg_lower)):
        if has_chinese:
            user_msg = f"请求参数无效: {error_message}"
        else:
            user_msg = f"Invalid request parameter: {error_message}"
        return LLMInvalidParameterError(
            f"Invalid request parameter: {error_message}",
            parameter=None,
            error_code=error_code or 'InvalidParameter',
            provider='dashscope'
        ), user_msg

    # Input validation errors
    if 'input' in error_msg_lower and ('invalid' in error_msg_lower or 'error' in error_msg_lower):
        user_msg = f"输入数据无效: {error_message}" if has_chinese else f"Invalid input: {error_message}"
        return LLMInvalidParameterError(
            f"Invalid input: {error_message}",
            parameter='input',
            error_code=error_code or 'InvalidParameter.Input',
            provider='dashscope'
        ), user_msg

    # JSON format errors
    if ('json' in error_msg_lower and
        ('error' in error_msg_lower or 'invalid' in error_msg_lower or
         'format' in error_msg_lower)):
        if has_chinese:
            user_msg = "JSON格式错误，请检查JSON格式"
        else:
            user_msg = "Invalid JSON format. Please check JSON format."
        return LLMInvalidParameterError(
            f"Invalid JSON format: {error_message}",
            parameter='body',
            error_code=error_code or 'InvalidParameter.JSON',
            provider='dashscope'
        ), user_msg

    # Messages validation errors
    if 'messages' in error_msg_lower:
        # Messages must contain user role
        if 'must contain' in error_msg_lower and 'user' in error_msg_lower:
            user_msg = "messages数组必须包含user角色的消息" if has_chinese else "Messages array must contain user role message."
            return LLMInvalidParameterError(
                f"Messages must contain user role: {error_message}",
                parameter='messages',
                error_code=error_code or 'InvalidParameter.Messages',
                provider='dashscope'
            ), user_msg

        # Messages length errors
        if ('length only support' in error_msg_lower or
            'messages length' in error_msg_lower):
            if has_chinese:
                user_msg = f"messages数组长度不符合要求: {error_message}"
            else:
                user_msg = f"Messages array length not supported: {error_message}"
            return LLMInvalidParameterError(
                f"Invalid messages length: {error_message}",
                parameter='messages',
                error_code=error_code or 'InvalidParameter.MessagesLength',
                provider='dashscope'
            ), user_msg

        # Content length errors
        if 'content length only support' in error_msg_lower:
            if has_chinese:
                user_msg = f"content数组长度不符合要求: {error_message}"
            else:
                user_msg = f"Content array length not supported: {error_message}"
            return LLMInvalidParameterError(
                f"Invalid content length: {error_message}",
                parameter='content',
                error_code=error_code or 'InvalidParameter.ContentLength',
                provider='dashscope'
            ), user_msg

        # Last message must be user
        if ('last' in error_msg_lower and 'user' in error_msg_lower and
            'message' in error_msg_lower):
            if has_chinese:
                user_msg = "messages数组最后一位需为User Message"
            else:
                user_msg = "Last message in messages array must be User Message."
            return LLMInvalidParameterError(
                f"Last message must be user: {error_message}",
                parameter='messages',
                error_code=error_code or 'InvalidParameter.MessagesOrder',
                provider='dashscope'
            ), user_msg

    # Role validation errors
    if 'role' in error_msg_lower and ('must be' in error_msg_lower or 'should be' in error_msg_lower):
        user_msg = f"role参数错误: {error_message}" if has_chinese else f"Invalid role parameter: {error_message}"
        return LLMInvalidParameterError(
            f"Invalid role: {error_message}",
            parameter='role',
            error_code=error_code or 'InvalidParameter.Role',
            provider='dashscope'
        ), user_msg

    # Content length validation
    if 'content length' in error_msg_lower and 'must be greater than 0' in error_msg_lower:
        user_msg = "输入内容长度必须大于0" if has_chinese else "Content length must be greater than 0."
        return LLMInvalidParameterError(
            f"Content length must be > 0: {error_message}",
            parameter='content',
            error_code=error_code or 'InvalidParameter.ContentLength',
            provider='dashscope'
        ), user_msg

    # Generic invalid parameter
    if ('invalid' in error_msg_lower and
        ('parameter' in error_msg_lower or 'value' in error_msg_lower)):
        if has_chinese:
            user_msg = f"参数错误: {error_message}"
        else:
            user_msg = f"Invalid parameter: {error_message}"
        return LLMInvalidParameterError(
            f"Invalid parameter: {error_message}",
            parameter=None,
            error_code=error_code or 'InvalidParameter',
            provider='dashscope'
        ), user_msg

    return None
