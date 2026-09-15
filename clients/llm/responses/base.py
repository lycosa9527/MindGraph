"""Provider-neutral Responses API client contract."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Protocol

from clients.llm.responses.types import ResponsesRequest


class BaseResponsesClient(Protocol):
    """Stream provider-neutral events from a Responses-style API."""

    def stream(self, request: ResponsesRequest) -> AsyncGenerator[Dict[str, Any], None]:
        """Yield normalized events for one request."""
        raise NotImplementedError
