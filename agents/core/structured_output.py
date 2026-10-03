"""Optional JSON Schema scope for one LLM call chain.

Unset means the existing JSON Object format. Auto-complete sets a schema
around requirements extraction and around the diagram agent.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator

_FORMAT: ContextVar[dict[str, Any] | None] = ContextVar("structured_response_format", default=None)


def current_structured_response_format() -> dict[str, Any] | None:
    """Response format for the in-flight call, if a schema scope is active."""
    value = _FORMAT.get()
    if not value:
        return None
    return value


@contextmanager
def structured_output_scope(response_format: dict[str, Any] | None) -> Iterator[None]:
    """Force native JSON Schema for the duration of one auto-complete task."""
    if not response_format:
        yield
        return
    token = _FORMAT.set(response_format)
    try:
        yield
    finally:
        _FORMAT.reset(token)
