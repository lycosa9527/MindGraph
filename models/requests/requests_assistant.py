"""AI Assistant and Frontend Logging Request Models.

Pydantic models for validating AI assistant, frontend logging, and feedback API requests.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field, field_validator


class AIAssistantFile(BaseModel):
    """File object for AI assistant requests (Dify API compatible)"""
    type: str = Field(
        ..., description="File type: document, image, audio, video, custom"
    )
    transfer_method: str = Field(
        ..., description="Transfer method: remote_url or local_file"
    )
    url: Optional[str] = Field(
        None, description="File URL (for remote_url transfer method)"
    )
    upload_file_id: Optional[str] = Field(
        None, description="Uploaded file ID (for local_file transfer method)"
    )

    class Config:
        """Configuration for AIAssistantFile model."""

        json_schema_extra = {
            "example": {
                "type": "image",
                "transfer_method": "remote_url",
                "url": "https://example.com/image.png"
            }
        }


class AIAssistantRequest(BaseModel):
    """Request model for /api/ai_assistant/stream endpoint (SSE)

    Supports Dify Chatflow API with file uploads for Vision/document processing.
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description=(
            "User message to AI assistant "
            "(use 'start' to trigger Dify conversation opener)"
        )
    )
    user_id: str = Field(
        ..., min_length=1, max_length=100,
        description="Unique user identifier"
    )
    conversation_id: Optional[str] = Field(
        None, max_length=100,
        description="Conversation ID for context (null for new conversation)"
    )
    files: Optional[List[AIAssistantFile]] = Field(
        None, description="Files for Vision/document processing"
    )
    inputs: Optional[Dict[str, Any]] = Field(
        None, description="App-defined variable values"
    )
    auto_generate_name: bool = Field(
        True, description="Auto-generate conversation title"
    )
    workflow_id: Optional[str] = Field(
        None, description="Specific workflow version ID"
    )
    trace_id: Optional[str] = Field(
        None, description="Trace ID for distributed tracing"
    )

    class Config:
        """Configuration for AIAssistantRequest model."""

        json_schema_extra = {
            "example": {
                "message": "帮我解释一下概念图的作用",
                "user_id": "user_123",
                "conversation_id": "conv_456",
                "files": [
                    {
                        "type": "image",
                        "transfer_method": "remote_url",
                        "url": "https://example.com/diagram.png"
                    }
                ]
            }
        }


class FrontendLogRequest(BaseModel):
    """Request model for /api/frontend_log endpoint"""
    level: str = Field(..., description="Log level (debug, info, warn, error)")
    message: str = Field(..., max_length=5000, description="Log message")
    source: Optional[str] = Field(None, description="Source component")
    timestamp: Optional[str] = Field(
        None, description="Client timestamp (ISO format)"
    )

    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        """Validate log level is one of the allowed values."""
        valid_levels = ['debug', 'info', 'warn', 'error']
        if v.lower() not in valid_levels:
            raise ValueError(f"Level must be one of {valid_levels}")
        return v.lower()


class FrontendLogBatchRequest(BaseModel):
    """Request model for /api/frontend_log_batch endpoint (batched logs)"""
    logs: List[FrontendLogRequest] = Field(
        ..., min_items=1, max_items=50,
        description="Batch of log entries"
    )
    batch_size: int = Field(
        ..., description="Number of logs in this batch"
    )

    class Config:
        """Configuration for FrontendLogBatchRequest model."""

        json_schema_extra = {
            "example": {
                "logs": [
                    {
                        "level": "info",
                        "message": "[ToolbarManager] Auto-complete started",
                        "source": "ToolbarManager",
                        "timestamp": "2025-10-11T12:34:56.789Z"
                    },
                    {
                        "level": "debug",
                        "message": "[Editor] Rendering diagram",
                        "source": "Editor",
                        "timestamp": "2025-10-11T12:34:57.123Z"
                    }
                ],
                "batch_size": 2
            }
        }


class FeedbackRequest(BaseModel):
    """Request model for /api/feedback endpoint"""
    message: str = Field(
        ..., min_length=1, max_length=5000,
        description="Feedback message content"
    )
    captcha_id: str = Field(
        ...,
        description="Captcha session ID from /api/auth/captcha/generate"
    )
    captcha: str = Field(
        ..., min_length=4, max_length=4,
        description="User-entered captcha code"
    )
    user_id: Optional[str] = Field(
        None, description="User ID if available"
    )
    user_name: Optional[str] = Field(
        None, description="User name if available"
    )

    class Config:
        """Configuration for FeedbackRequest model."""

        json_schema_extra = {
            "example": {
                "message": "The diagram export feature is not working properly.",
                "captcha_id": "uuid-here",
                "captcha": "ABCD",
                "user_id": "user123",
                "user_name": "John Doe"
            }
        }
