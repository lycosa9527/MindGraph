"""Footer that asks one diagram prompt to emit both languages.

The diagram template is unchanged. This replaces the single-language footer
from ``output_language_instruction`` for that one call.
"""

from __future__ import annotations

from utils.prompt_output_languages import OUTPUT_LANGUAGE_ENGLISH_NAMES, is_prompt_output_language

_SKIP_DIAGRAM_TYPES = frozenset(
    {
        "classification",
        "topic_extraction",
        "prompt_requirements",
    }
)
_SKIP_PROMPT_TYPES = frozenset({"classification", "extraction"})


def bilingual_footer_applies(diagram_type: str, prompt_type: str) -> bool:
    """True for diagram body prompts, not classification or requirements."""
    if diagram_type in _SKIP_DIAGRAM_TYPES:
        return False
    if prompt_type in _SKIP_PROMPT_TYPES:
        return False
    return True


def _language_label(code: str) -> str:
    normalized = (code or "en").lower().strip()
    if normalized == "zh":
        return "Simplified Chinese"
    if normalized in ("zh-hant", "zh-tw", "zh-hk", "zh-mo"):
        return "Traditional Chinese"
    if not is_prompt_output_language(normalized):
        normalized = "en"
    return OUTPUT_LANGUAGE_ENGLISH_NAMES.get(normalized, "English")


def bilingual_output_footer(primary_language: str, secondary_language: str) -> str:
    """Tell the model where each language goes in the JSON."""
    primary = _language_label(primary_language)
    secondary = _language_label(secondary_language)
    return (
        "\n\n---\n"
        f"Output languages: write every user-visible string in the normal JSON fields "
        f"in **{primary}** only.\n"
        'Also include a sibling object "secondary" with the same keys, the same nesting, '
        'and the same array lengths. Every string in "secondary" is the '
        f"**{secondary}** translation of the matching primary string. "
        "The secondary object is required even when the template shows a fixed JSON shape. "
        "Do not copy the primary text into secondary. "
        "Do not mix two languages inside one string. "
        "Do not add keys that are not in the primary object."
    )
