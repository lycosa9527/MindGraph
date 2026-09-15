"""Logical provider key → Responses client."""

from __future__ import annotations

from typing import Dict

from clients.llm.responses.base import BaseResponsesClient
from clients.llm.responses.dashscope import DashScopeResponsesClient


class _RegistryHolder:
    """Holds the singleton registry."""

    instance: "ResponsesClientRegistry | None" = None


class ResponsesClientRegistry:
    """Map logical model keys to Responses adapters."""

    def __init__(self) -> None:
        self._clients: Dict[str, BaseResponsesClient] = {
            "qwen": DashScopeResponsesClient(),
        }

    def get_client(self, provider: str) -> BaseResponsesClient:
        """Return the adapter for ``provider`` (default DashScope / qwen)."""
        key = (provider or "qwen").strip().lower() or "qwen"
        client = self._clients.get(key)
        if client is None:
            return self._clients["qwen"]
        return client


def get_responses_registry() -> ResponsesClientRegistry:
    """Return the shared registry."""
    if _RegistryHolder.instance is None:
        _RegistryHolder.instance = ResponsesClientRegistry()
    return _RegistryHolder.instance
