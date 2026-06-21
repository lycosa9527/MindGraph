"""Shared error record payload for collection and alerting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ErrorRecord:
    """Input payload for a captured error."""

    source: str
    component: str
    message: str
    severity: str = "error"
    exception_type: str = ""
    stacktrace: str | None = None
    tags: dict[str, Any] | None = None
    request_id: str | None = None
    user_id: int | None = None
    http_path: str | None = None
    http_status: int | None = None
    fingerprint: str | None = None
