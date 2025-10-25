"""
Centralized Bilingual Message System for MindGraph
===================================================

Provides all user-facing messages (errors, success, warnings) in both Chinese and English.
Used by API endpoints to return localized error messages.

@author lycosa9527
@made_by MindSpring Team
"""

from typing import Dict, Literal

Language = Literal["zh", "en"]


class Messages:
    """Centralized bilingual message system"""
    
    # API Error Messages
    ERRORS = {
        "message_required": {
            "zh": "消息不能为空",
            "en": "Message is required"
        },
        "ai_not_configured": {
            "zh": "AI助手未配置",
            "en": "AI assistant not configured"
        },
        "invalid_prompt": {
            "zh": "提示词无效或为空",
            "en": "Invalid or empty prompt"
        },
        "diagram_data_required": {
            "zh": "需要图示数据",
            "en": "Diagram data is required"
        },
        "generation_failed": {
            "zh": "生成图示失败：{}",
            "en": "Failed to generate graph: {}"
        },
        "export_failed": {
            "zh": "导出PNG失败：{}",
            "en": "PNG export failed: {}"
        },
        "internal_error": {
            "zh": "服务器内部错误",
            "en": "Internal server error"
        },
        "invalid_request": {
            "zh": "请求无效",
            "en": "Invalid request"
        },
        "learning_session_start_failed": {
            "zh": "创建学习会话失败",
            "en": "Failed to start learning session"
        },
        "learning_session_not_found": {
            "zh": "学习会话未找到或已过期",
            "en": "Learning session not found or expired"
        },
        "learning_node_not_found": {
            "zh": "节点未在图示中找到",
            "en": "Node not found in diagram"
        },
        "learning_validation_failed": {
            "zh": "答案验证失败",
            "en": "Answer validation failed"
        },
        "learning_hint_failed": {
            "zh": "提示生成失败",
            "en": "Hint generation failed"
        },
        "learning_verification_failed": {
            "zh": "理解验证失败",
            "en": "Understanding verification failed"
        }
    }
    
    # Success Messages
    SUCCESS = {
        "diagram_generated": {
            "zh": "图示生成成功",
            "en": "Diagram generated successfully"
        },
        "diagram_exported": {
            "zh": "图示已导出",
            "en": "Diagram exported"
        },
        "request_processed": {
            "zh": "请求已处理",
            "en": "Request processed"
        }
    }
    
    # Warning Messages
    WARNINGS = {
        "slow_request": {
            "zh": "请求处理较慢",
            "en": "Slow request processing"
        },
        "deprecated_endpoint": {
            "zh": "此端点已废弃",
            "en": "This endpoint is deprecated"
        }
    }
    
    @classmethod
    def get(cls, category: str, key: str, lang: Language = "en", *args) -> str:
        """
        Get a message in the specified language.
        
        Args:
            category: Message category ('ERRORS', 'SUCCESS', 'WARNINGS')
            key: Message key
            lang: Language ('zh' or 'en')
            *args: Format arguments for messages with placeholders
            
        Returns:
            Localized message string
        """
        messages = getattr(cls, category, {})
        message_dict = messages.get(key, {})
        message = message_dict.get(lang, message_dict.get("en", key))
        
        # Format message if arguments provided
        if args:
            try:
                return message.format(*args)
            except (IndexError, KeyError):
                return message
        
        return message
    
    @classmethod
    def error(cls, key: str, lang: Language = "en", *args) -> str:
        """Get an error message"""
        return cls.get("ERRORS", key, lang, *args)
    
    @classmethod
    def success(cls, key: str, lang: Language = "en", *args) -> str:
        """Get a success message"""
        return cls.get("SUCCESS", key, lang, *args)
    
    @classmethod
    def warning(cls, key: str, lang: Language = "en", *args) -> str:
        """Get a warning message"""
        return cls.get("WARNINGS", key, lang, *args)


# Convenience function for getting language from request
def get_request_language(language_header: str = None, accept_language: str = None) -> Language:
    """
    Determine language from request headers.
    
    Args:
        language_header: Custom X-Language header
        accept_language: Accept-Language header
        
    Returns:
        'zh' or 'en'
    """
    # Priority 1: Custom X-Language header
    if language_header:
        lang = language_header.lower()
        if lang in ["zh", "zh-cn", "zh-tw", "chinese"]:
            return "zh"
        return "en"
    
    # Priority 2: Accept-Language header
    if accept_language:
        lang = accept_language.lower()
        if any(x in lang for x in ["zh", "chinese"]):
            return "zh"
    
    # Default: English
    return "en"

