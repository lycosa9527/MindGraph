"""
User-visible messages for overseas email registration.

Uses generic email-registration copy (any valid non-mainland-China address).
"""

from __future__ import annotations

from typing import Final

from models.domain.messages import Language, Messages

_OVERSEAS_MESSAGE_BASES: Final[frozenset[str]] = frozenset(
    {
        "registration_email_not_available_in_region",
        "registration_geoip_unavailable",
        "registration_email_mainland_china_domain",
        "register_overseas_acknowledgment_required",
    }
)


def overseas_registration_message_key(base_key: str) -> str:
    """Return ``{base_key}_any`` for overseas registration bases, else ``base_key``."""
    if base_key in _OVERSEAS_MESSAGE_BASES:
        return f"{base_key}_any"
    return base_key


def overseas_registration_error(base_key: str, lang: Language) -> str:
    """Localized error string for an overseas registration message base key."""
    return Messages.error(overseas_registration_message_key(base_key), lang)
