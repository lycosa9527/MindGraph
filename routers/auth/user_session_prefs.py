"""Shared user preference fields for login / register /me JSON payloads."""

from typing import Any

from models.domain.auth import User


def _bool_pref(user: User, name: str, default: bool) -> bool:
    """Read a boolean user column, applying the column default when unset."""
    value = getattr(user, name, default)
    if value is None:
        return default
    return bool(value)


def user_preference_fields(user: User) -> dict[str, Any]:
    """Return persisted personalization fields for an authenticated session user."""
    return {
        "ui_language": getattr(user, "ui_language", None),
        "prompt_language": getattr(user, "prompt_language", None),
        "ui_version": getattr(user, "ui_version", None),
        "match_prompt_to_ui": _bool_pref(user, "match_prompt_to_ui", True),
        "allows_simplified_chinese": _bool_pref(user, "allows_simplified_chinese", True),
        "education_stage": getattr(user, "education_stage", None),
        "ai_content_level": getattr(user, "ai_content_level", None),
    }


def language_preference_patch_fields(user: User) -> dict[str, Any]:
    """PATCH /language-preferences response body."""
    prefs = user_preference_fields(user)
    return {
        "ui_language": prefs["ui_language"],
        "prompt_language": prefs["prompt_language"],
        "ui_version": prefs["ui_version"],
        "match_prompt_to_ui": prefs["match_prompt_to_ui"],
    }
