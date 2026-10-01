"""Saved text for the six quick-access inspiration prompts."""

QUICK_ACCESS_PROMPT_KEYS = frozenset(
    {
        "landing.international.example1",
        "landing.international.example2",
        "landing.international.example3",
        "landing.international.example4",
        "landing.international.example5",
        "landing.international.example6",
    }
)
QUICK_ACCESS_PROMPT_MAX_LENGTH = 10000


def clean_quick_access_prompt_overrides(value: object) -> dict[str, str]:
    """Keep known prompt keys. Blank, unknown, and non-string values are dropped."""
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key, text in value.items():
        if not isinstance(key, str) or key not in QUICK_ACCESS_PROMPT_KEYS:
            continue
        if not isinstance(text, str):
            continue
        stripped = text.strip()[:QUICK_ACCESS_PROMPT_MAX_LENGTH]
        if stripped:
            cleaned[key] = stripped
    return cleaned
