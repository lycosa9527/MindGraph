"""
Supported MindGraph UI (interface) locale codes.

Keep in sync with enabled entries in frontend/src/i18n/locales.ts (SUPPORTED_UI_LOCALES).
"""

UI_LANGUAGE_CODES = frozenset({'zh', 'en', 'az'})


def is_ui_language(value: str) -> bool:
    """Return True if value is a supported interface locale code."""
    return value in UI_LANGUAGE_CODES
