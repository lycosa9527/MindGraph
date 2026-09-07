"""
Append mind-map 专业程度 instructions onto an existing prompt.

Does not rewrite diagram-type templates. Callers pass the audience block
from the request (generation_instructions / audience_instructions).
"""


def generation_requirements_marker(language: str) -> str:
    """Locale marker used when generation_instructions are merged into a prompt."""
    if (language or "").startswith("zh"):
        return "【用户要求】"
    return "User requirements:"


def merge_generation_instructions(prompt: str, instructions: str, language: str) -> str:
    """Join a topic prompt with generation_instructions using the locale marker."""
    base = (prompt or "").strip()
    block = (instructions or "").strip()
    if not block:
        return base
    if not base:
        return block
    marker = generation_requirements_marker(language)
    return f"{base}\n\n{marker}\n{block}"


def extract_appended_generation_instructions(prompt: str, language: str) -> str | None:
    """Return the generation_instructions suffix appended by merge_generation_instructions."""
    text = prompt or ""
    marker = generation_requirements_marker(language)
    needle = f"\n\n{marker}\n"
    idx = text.find(needle)
    if idx < 0:
        return None
    block = text[idx + len(needle) :].strip()
    return block or None


def append_audience_instructions(prompt: str, audience_block: str | None) -> str:
    """Return prompt with a trailing audience block when one is provided."""
    base = (prompt or "").rstrip()
    block = (audience_block or "").strip()
    if not base:
        return block
    if not block:
        return base
    return f"{base}\n\n{block}"
