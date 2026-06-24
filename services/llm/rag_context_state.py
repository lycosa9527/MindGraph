"""Request-scoped RAG suppression state.

When the diagram-generation workflow has already injected package-scoped RAG
context into the agent prompt, the implicit whole-library RAG injection inside
``llm_service.chat`` / ``chat_stream`` must be suppressed to avoid a
double-dip (and to keep retrieval scoped to the diagram's package only).

This uses a ``ContextVar`` so the flag is isolated per asyncio task and never
leaks across concurrent requests.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_suppress_implicit_rag: ContextVar[bool] = ContextVar("suppress_implicit_rag", default=False)


def is_implicit_rag_suppressed() -> bool:
    """True when implicit whole-library RAG injection should be skipped."""
    return _suppress_implicit_rag.get()


@contextmanager
def suppress_implicit_rag() -> Iterator[None]:
    """Suppress implicit whole-library RAG within this context.

    Used around agent generation when the workflow owns RAG (package-scoped),
    so underlying ``llm_service.chat`` calls do not inject the whole library.
    """
    token = _suppress_implicit_rag.set(True)
    try:
        yield
    finally:
        _suppress_implicit_rag.reset(token)
