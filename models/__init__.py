"""
MindGraph Pydantic Models
=========================

Request and response models for FastAPI type safety and validation.

Author: lycosa9527
Made by: MindSpring Team
"""

from .requests import (
    GenerateRequest,
    EnhanceRequest,
    ExportPNGRequest,
    AIAssistantRequest,
    LearningStartSessionRequest,
    LearningValidateAnswerRequest,
    LearningHintRequest,
    LearningVerifyUnderstandingRequest,
    FrontendLogRequest,
)

from .responses import (
    GenerateResponse,
    ErrorResponse,
    HealthResponse,
    StatusResponse,
)

from .common import DiagramType, LLMModel, Language
from .messages import Messages, get_request_language

__all__ = [
    # Requests
    "GenerateRequest",
    "EnhanceRequest",
    "ExportPNGRequest",
    "AIAssistantRequest",
    "LearningStartSessionRequest",
    "LearningValidateAnswerRequest",
    "LearningHintRequest",
    "LearningVerifyUnderstandingRequest",
    "FrontendLogRequest",
    # Responses
    "GenerateResponse",
    "ErrorResponse",
    "HealthResponse",
    "StatusResponse",
    # Common
    "DiagramType",
    "LLMModel",
    "Language",
    # Bilingual Messages
    "Messages",
    "get_request_language",
]

