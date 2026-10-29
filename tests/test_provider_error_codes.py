"""Official DashScope and Volcengine codes must keep their exception type."""

from __future__ import annotations

import pytest

from services.infrastructure.http.error_handler import (
    LLMAccessDeniedError,
    LLMContentFilterError,
    LLMInvalidParameterError,
    LLMModelNotFoundError,
    LLMQuotaExhaustedError,
    LLMRateLimitError,
    LLMServiceError,
    LLMTimeoutError,
)
from services.llm.error_parsers.dashscope_error_parser import parse_dashscope_error
from services.llm.error_parsers.doubao_error_parser import parse_doubao_error

_DOUBAO_CASES = [
    ("ContentSecurityDetectionError", 400, LLMServiceError),
    ("InvalidSubscription", 400, LLMAccessDeniedError),
    ("QuotaExceeded.DoubaoSearchFreeQuotaExceeded", 403, LLMQuotaExhaustedError),
    ("ModelNotOpen", 404, LLMModelNotFoundError),
    ("UnsupportedModel", 404, LLMModelNotFoundError),
    ("RequestTimeout", 408, LLMTimeoutError),
    ("ModelAccountTpdRateLimitExceeded", 429, LLMQuotaExhaustedError),
    ("AccountOverdueError", 403, LLMQuotaExhaustedError),
    ("OperationDenied.ServiceOverdue", 403, LLMQuotaExhaustedError),
    ("ServiceConnectionRefused", 503, LLMServiceError),
    ("NoAvailableService", 503, LLMServiceError),
    ("RequestBurstTooFast", 429, LLMRateLimitError),
    ("RateLimitExceeded.EndpointFlexTPMExceeded", 429, LLMRateLimitError),
    ("RateLimitExceeded.EndpointTPMExceeded", 429, LLMRateLimitError),
    ("SensitiveContentDetected", 400, LLMContentFilterError),
    ("InputTextRiskDetection", 400, LLMContentFilterError),
    ("AuthenticationError", 401, LLMAccessDeniedError),
    ("InvalidEndpointOrModel.NotFound", 404, LLMModelNotFoundError),
    ("InternalServiceError", 500, LLMServiceError),
    ("AccountQuotaExceeded", 429, LLMQuotaExhaustedError),
    ("OperationDenied.FileQuotaExceeded", 403, LLMQuotaExhaustedError),
    ("OperationDenied.ServiceNotOpen", 403, LLMModelNotFoundError),
    ("InvalidAccountStatus", 401, LLMAccessDeniedError),
    ("InvalidAction", 404, LLMInvalidParameterError),
    ("PathNotFound", 404, LLMInvalidParameterError),
]

_DASHSCOPE_CASES = [
    (400, "invalid_request_error", "Invalid request.", LLMInvalidParameterError),
    (400, "invalid_value", "The requested voice is not supported.", LLMInvalidParameterError),
    (400, "invalid_value", "Access denied, account is not in good standing.", LLMQuotaExhaustedError),
    (400, "FlowNotPublished", "Flow has not published yet.", LLMInvalidParameterError),
    (400, "InvalidInputLength", "The image resolution is invalid.", LLMInvalidParameterError),
    (400, "ServiceUnavailableError", "Input suspected of IP infringement.", LLMContentFilterError),
    (400, "invalid_parameter_error", "The product is not activated.", LLMAccessDeniedError),
    (400, "InvalidFile.FrontBody", "front body required", LLMInvalidParameterError),
    (400, "InvalidFile.FaceNotMatch", "face does not match", LLMInvalidParameterError),
    (400, "InvalidFile.FullBody", "full body required", LLMInvalidParameterError),
    (400, "InvalidFile.BodyPose", "body pose is invalid", LLMInvalidParameterError),
    (400, "InvalidPerson", "invalid person", LLMInvalidParameterError),
    (400, "InvalidGarment", "invalid garment", LLMInvalidParameterError),
    (430, "Audio.AudioSilentError", "audio is silent", LLMInvalidParameterError),
    (504, "GatewayTimeout.InputDownload", "input download timed out", LLMTimeoutError),
    (200, "BailianGateway.Workspace.NotAuthorised", "workspace not authorised", LLMAccessDeniedError),
    (200, "BailianGateway.Team.NotAuthorised", "team not authorised", LLMAccessDeniedError),
    (429, "insufficient_quota", "You exceeded your current quota", LLMQuotaExhaustedError),
    (400, "DataInspectionFailed", "Input data may contain inappropriate content.", LLMContentFilterError),
    (401, "invalid_api_key", "Invalid API-key provided.", LLMAccessDeniedError),
    (429, "Throttling.RateQuota", "Request rate limit exceeded.", LLMRateLimitError),
    (400, "Arrearage", "Access denied, please make sure your account is in good standing.", LLMQuotaExhaustedError),
    (500, "InternalError.Timeout", "Request timed out.", LLMTimeoutError),
    (503, "ServiceUnavailable", "Service is unavailable.", LLMServiceError),
]


@pytest.mark.parametrize(("code", "status", "expected"), _DOUBAO_CASES)
def test_volcengine_official_code(code: str, status: int, expected: type[Exception]) -> None:
    """Volcengine inference codes keep retry vs safety vs quota vs timeout."""
    exc, _user_msg = parse_doubao_error(code, f"official {code}", status)
    assert exc.__class__ is expected


@pytest.mark.parametrize(("status", "code", "message", "expected"), _DASHSCOPE_CASES)
def test_dashscope_official_code(status: int, code: str, message: str, expected: type[Exception]) -> None:
    """DashScope codes that miss the status parsers still get a typed exception."""
    exc, _user_msg = parse_dashscope_error(status, message, {"code": code, "message": message})
    assert exc.__class__ is expected


def test_flex_tpm_is_not_labeled_as_plain_endpoint_tpm() -> None:
    """Flex TPM contains the plain EndpointTPMExceeded substring and must stay distinct."""
    flex, _flex_msg = parse_doubao_error("RateLimitExceeded.EndpointFlexTPMExceeded", "flex", 429)
    plain, _plain_msg = parse_doubao_error("RateLimitExceeded.EndpointTPMExceeded", "plain", 429)
    assert "Flex TPM" in str(flex)
    assert "Endpoint TPM" in str(plain)
