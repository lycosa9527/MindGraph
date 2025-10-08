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
)

from .responses import (
    GenerateResponse,
    ErrorResponse,
    HealthResponse,
    StatusResponse,
)

from .common import DiagramType, LLMModel

__all__ = [
    # Requests
    "GenerateRequest",
    "EnhanceRequest",
    "ExportPNGRequest",
    "AIAssistantRequest",
    "LearningStartSessionRequest",
    "LearningValidateAnswerRequest",
    "LearningHintRequest",
    # Responses
    "GenerateResponse",
    "ErrorResponse",
    "HealthResponse",
    "StatusResponse",
    # Common
    "DiagramType",
    "LLMModel",
]

