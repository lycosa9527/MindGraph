"""
Request Models

Pydantic request models for API endpoints.
"""

from .requests_diagram import (
    GenerateRequest,
    EnhanceRequest,
    ExportPNGRequest,
    GeneratePNGRequest,
    GenerateDingTalkRequest,
    RecalculateLayoutRequest,
    DiagramCreateRequest,
    DiagramUpdateRequest,
)
from .requests_assistant import (
    AIAssistantRequest,
    FrontendLogRequest,
    FrontendLogBatchRequest,
    FeedbackRequest,
)
from .requests_auth import (
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
)
from .requests_knowledge_space import (
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
)
from .requests_thinking import (
    TabExpandRequest,
    TabSuggestionRequest,
)

__all__ = [
    # Diagram Requests
    "GenerateRequest",
    "EnhanceRequest",
    "ExportPNGRequest",
    "GeneratePNGRequest",
    "GenerateDingTalkRequest",
    "RecalculateLayoutRequest",
    "DiagramCreateRequest",
    "DiagramUpdateRequest",
    # Assistant Requests
    "AIAssistantRequest",
    "FrontendLogRequest",
    "FrontendLogBatchRequest",
    "FeedbackRequest",
    # Auth Requests
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
    # Knowledge Space Requests
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
    # Thinking Requests
    "TabExpandRequest",
    "TabSuggestionRequest",
]
