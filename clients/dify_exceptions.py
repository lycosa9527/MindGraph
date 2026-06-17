"""
Typed Dify Service API exceptions (shared by client and HTTP error mapping).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional


class DifyAPIError(Exception):
    """Base Dify API error."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_code: Optional[str] = None,
    ) -> None:
        """init  ."""
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        super().__init__(self.message)


class DifyConversationNotFoundError(DifyAPIError):
    """404: Conversation does not exist."""

    def __init__(self, message: str = "Conversation does not exist") -> None:
        """init  ."""
        super().__init__(message, status_code=404, error_code="conversation_not_exists")


class DifyInvalidParamError(DifyAPIError):
    """400: Invalid parameter input."""

    def __init__(self, message: str = "Invalid parameter input") -> None:
        """init  ."""
        super().__init__(message, status_code=400, error_code="invalid_param")


class DifyAppUnavailableError(DifyAPIError):
    """400: App configuration unavailable."""

    def __init__(self, message: str = "App configuration unavailable") -> None:
        """init  ."""
        super().__init__(message, status_code=400, error_code="app_unavailable")


class DifyProviderNotInitializeError(DifyAPIError):
    """400: No available model credential configuration."""

    def __init__(self, message: str = "No available model credential configuration") -> None:
        """init  ."""
        super().__init__(message, status_code=400, error_code="provider_not_initialize")


class DifyQuotaExceededError(DifyAPIError):
    """400: Model invocation quota insufficient."""

    def __init__(self, message: str = "Model invocation quota insufficient") -> None:
        """init  ."""
        super().__init__(message, status_code=400, error_code="provider_quota_exceeded")


class DifyModelNotSupportError(DifyAPIError):
    """400: Current model unavailable."""

    def __init__(self, message: str = "Current model unavailable") -> None:
        """init  ."""
        super().__init__(message, status_code=400, error_code="model_currently_not_support")


class DifyWorkflowNotFoundError(DifyAPIError):
    """400: Specified workflow version not found."""

    def __init__(self, message: str = "Specified workflow version not found") -> None:
        """init  ."""
        super().__init__(message, status_code=400, error_code="workflow_not_found")


class DifyDraftWorkflowError(DifyAPIError):
    """400: Cannot use draft workflow version."""

    def __init__(self, message: str = "Cannot use draft workflow version") -> None:
        """init  ."""
        super().__init__(message, status_code=400, error_code="draft_workflow_error")


class DifyWorkflowIdFormatError(DifyAPIError):
    """400: Invalid workflow_id format, expected UUID format."""

    def __init__(self, message: str = "Invalid workflow_id format, expected UUID format") -> None:
        """init  ."""
        super().__init__(message, status_code=400, error_code="workflow_id_format_error")


class DifyCompletionRequestError(DifyAPIError):
    """400: Text generation failed."""

    def __init__(self, message: str = "Text generation failed") -> None:
        """init  ."""
        super().__init__(message, status_code=400, error_code="completion_request_error")


class DifyFileAccessDeniedError(DifyAPIError):
    """403: File access denied or file does not belong to current application."""

    def __init__(
        self,
        message: str = "File access denied or file does not belong to current application",
    ) -> None:
        """init  ."""
        super().__init__(message, status_code=403, error_code="file_access_denied")


class DifyFileNotFoundError(DifyAPIError):
    """404: File not found or has been deleted."""

    def __init__(self, message: str = "File not found or has been deleted") -> None:
        """init  ."""
        super().__init__(message, status_code=404, error_code="file_not_found")


class DifyFileTooLargeError(DifyAPIError):
    """413: File exceeds size limit."""

    def __init__(self, message: str = "File too large") -> None:
        """init  ."""
        super().__init__(message, status_code=413, error_code="file_too_large")


class DifyUnsupportedFileTypeError(DifyAPIError):
    """415: Unsupported file extension for upload."""

    def __init__(self, message: str = "Unsupported file type") -> None:
        """init  ."""
        super().__init__(message, status_code=415, error_code="unsupported_file_type")


class DifyS3StorageError(DifyAPIError):
    """503: S3 / object storage errors (upload pipeline)."""

    def __init__(self, message: str, *, error_code: str = "s3_connection_failed") -> None:
        """init  ."""
        super().__init__(message, status_code=503, error_code=error_code)
