"""Optional second-language scope for diagram generation prompts.

Unset means the existing single-language footer. Set only around the diagram
agent call so classification and requirements prompts stay single-language.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_SECONDARY: ContextVar[str | None] = ContextVar("diagram_bilingual_secondary", default=None)


# Room for the primary spec plus a same-shaped second-language object.
# 1000 and 4000 both cut ``secondary`` off the end of larger diagrams.
_BILINGUAL_MAX_TOKENS = 8192


def bilingual_max_tokens(base: int) -> int:
    """Give a bilingual diagram call enough room for the second-language object.

    Mono calls keep ``base``. A bilingual call uses at least 8192 tokens so the
    mirror at the end of the JSON is not truncated.
    """
    if current_bilingual_secondary() is None:
        return base
    if base > _BILINGUAL_MAX_TOKENS:
        return base
    return _BILINGUAL_MAX_TOKENS


def current_bilingual_secondary() -> str | None:
    """Presenter language for the in-flight diagram agent call, if any."""
    value = _SECONDARY.get()
    if not value:
        return None
    return value


@contextmanager
def bilingual_prompt_scope(secondary_language: str | None) -> Iterator[None]:
    """Apply a second output language for the duration of one agent call."""
    cleaned = (secondary_language or "").strip()
    if not cleaned:
        yield
        return
    token = _SECONDARY.set(cleaned)
    try:
        yield
    finally:
        _SECONDARY.reset(token)
