"""
Append mind-map 专业程度 instructions onto an existing prompt.

Does not rewrite diagram-type templates. Callers pass the audience block
from the request (generation_instructions / audience_instructions).
"""


def append_audience_instructions(prompt: str, audience_block: str | None) -> str:
    """Return prompt with a trailing audience block when one is provided."""
    base = (prompt or "").rstrip()
    block = (audience_block or "").strip()
    if not base:
        return block
    if not block:
        return base
    return f"{base}\n\n{block}"
