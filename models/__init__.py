"""
MindGraph Pydantic Models
=========================

Request and response models for FastAPI type safety and validation.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

# Import from new locations
from .requests.requests_diagram import (
    GenerateRequest,
    EnhanceRequest,
    ExportPNGRequest,
    GeneratePNGRequest,
    GenerateDingTalkRequest,
    RecalculateLayoutRequest,
    DiagramCreateRequest,
    DiagramUpdateRequest,
)
from .requests.requests_assistant import (
    AIAssistantRequest,
    FrontendLogRequest,
    FrontendLogBatchRequest,
    FeedbackRequest,
)

from .responses import (
    GenerateResponse,
    ErrorResponse,
    HealthResponse,
    LLMHealthResponse,
    DatabaseHealthResponse,
    ModelHealthStatus,
    StatusResponse,
    DiagramResponse,
    DiagramListItem,
    DiagramListResponse,
)

from .common import DiagramType, LLMModel, Language
from .domain.messages import Messages, get_request_language

# Backward compatibility: Re-export domain models
from .domain import (
    Base,
    Organization,
    User,
    APIKey,
    Diagram,
    KnowledgeSpace,
    KnowledgeDocument,
    DocumentChunk,
    DocumentBatch,
    DocumentVersion,
    KnowledgeQuery,
    QueryTemplate,
    QueryFeedback,
    ChunkTestDocument,
    ChunkTestDocumentChunk,
    ChunkTestResult,
    EvaluationDataset,
    EvaluationResult,
    DocumentRelationship,
    Embedding,
    TokenUsage,
    DashboardActivity,
    DebateSession,
    DebateMessage,
    DebateParticipant,
    SharedDiagram,
    SharedDiagramLike,
    SharedDiagramComment,
    PinnedConversation,
    EnvSetting,
)

# Backward compatibility: Re-export request models
from .requests import (
    LoginRequest,
    LoginWithSMSRequest,
    RegisterRequest,
    RegisterWithSMSRequest,
    ChangePasswordRequest,
    ResetPasswordWithSMSRequest,
    SendSMSCodeRequest,
    SendSMSCodeSimpleRequest,
    VerifySMSCodeRequest,
    SendChangePhoneSMSRequest,
    ChangePhoneRequest,
    DemoPasskeyRequest,
    ProcessSelectedRequest,
    RetrievalTestRequest,
    QueryFeedbackRequest,
    QueryTemplateRequest,
    ManualEvaluationRequest,
    EvaluationDatasetRequest,
    EvaluationRunRequest,
    RelationshipRequest,
    MetadataUpdateRequest,
    RollbackRequest,
    TabExpandRequest,
    TabSuggestionRequest,
)

__all__ = [
    # Requests
    "GenerateRequest",
    "EnhanceRequest",
    "ExportPNGRequest",
    "GeneratePNGRequest",
    "GenerateDingTalkRequest",
    "AIAssistantRequest",
    "FrontendLogRequest",
    "FrontendLogBatchRequest",
    "RecalculateLayoutRequest",
    "FeedbackRequest",
    "DiagramCreateRequest",
    "DiagramUpdateRequest",
    # Responses
    "GenerateResponse",
    "ErrorResponse",
    "HealthResponse",
    "StatusResponse",
    "LLMHealthResponse",
    "DatabaseHealthResponse",
    "ModelHealthStatus",
    "DiagramResponse",
    "DiagramListItem",
    "DiagramListResponse",
    # Common
    "DiagramType",
    "LLMModel",
    "Language",
    # Bilingual Messages
    "Messages",
    "get_request_language",
    # Domain models (backward compatibility)
    "Base",
    "Organization",
    "User",
    "APIKey",
    "Diagram",
    "KnowledgeSpace",
    "KnowledgeDocument",
    "DocumentChunk",
    "DocumentBatch",
    "DocumentVersion",
    "KnowledgeQuery",
    "QueryTemplate",
    "QueryFeedback",
    "ChunkTestDocument",
    "ChunkTestDocumentChunk",
    "ChunkTestResult",
    "EvaluationDataset",
    "EvaluationResult",
    "DocumentRelationship",
    "Embedding",
    "TokenUsage",
    "DashboardActivity",
    "DebateSession",
    "DebateMessage",
    "DebateParticipant",
    "SharedDiagram",
    "SharedDiagramLike",
    "SharedDiagramComment",
    "PinnedConversation",
    "EnvSetting",
    # Request models (backward compatibility)
    "LoginRequest",
    "LoginWithSMSRequest",
    "RegisterRequest",
    "RegisterWithSMSRequest",
    "ChangePasswordRequest",
    "ResetPasswordWithSMSRequest",
    "SendSMSCodeRequest",
    "SendSMSCodeSimpleRequest",
    "VerifySMSCodeRequest",
    "SendChangePhoneSMSRequest",
    "ChangePhoneRequest",
    "DemoPasskeyRequest",
    "ProcessSelectedRequest",
    "RetrievalTestRequest",
    "QueryFeedbackRequest",
    "QueryTemplateRequest",
    "ManualEvaluationRequest",
    "EvaluationDatasetRequest",
    "EvaluationRunRequest",
    "RelationshipRequest",
    "MetadataUpdateRequest",
    "RollbackRequest",
    "TabExpandRequest",
    "TabSuggestionRequest",
]
