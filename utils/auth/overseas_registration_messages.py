"""
Flag-aware user-visible messages for overseas email registration.

When ``SWOT_ACADEMIC_EMAIL_REQUIRED`` is false (default), keys with an ``_any`` suffix
use generic "email registration" copy instead of education-email wording.
"""

from __future__ import annotations

from typing import Final

from models.domain.messages import Language, Messages
from utils.auth.swot_config import is_swot_academic_required_for_purpose

_OVERSEAS_ACADEMIC_MESSAGE_BASES: Final[frozenset[str]] = frozenset(
    {
        "registration_email_not_available_in_region",
        "registration_geoip_unavailable",
        "registration_email_mainland_china_domain",
        "register_overseas_acknowledgment_required",
    }
)


def overseas_education_email_required() -> bool:
    """True when SWOT academic enforcement applies to overseas registration."""
    return is_swot_academic_required_for_purpose("register")


def overseas_registration_message_key(base_key: str) -> str:
    """Return ``base_key`` or ``{base_key}_any`` depending on the academic-email flag."""
    if overseas_education_email_required():
        return base_key
    if base_key in _OVERSEAS_ACADEMIC_MESSAGE_BASES:
        return f"{base_key}_any"
    return base_key


def overseas_registration_error(base_key: str, lang: Language) -> str:
    """Localized error string for an overseas registration message base key."""
    return Messages.error(overseas_registration_message_key(base_key), lang)
