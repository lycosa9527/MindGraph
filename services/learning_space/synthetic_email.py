"""Learning Space placeholder emails. No third-party imports.

Auth GeoIP and other always-on startup paths use this module so a missing
``pypinyin`` (only needed for Chinese-name initial passwords) cannot take
the process down.
"""

from __future__ import annotations

STUDENT_SYNTHETIC_EMAIL_SUFFIX = "@student.learning.local"


def student_synthetic_email(class_id: int, user_id: int) -> str:
    """Stable unique email satisfying users.phone_or_email check."""
    return f"s{int(class_id)}.{int(user_id)}@student.learning.local"


def is_learning_space_synthetic_email(email: str | None) -> bool:
    """True for Learning Space placeholder emails (not real email-login accounts)."""
    if not email or not isinstance(email, str):
        return False
    return email.strip().lower().endswith(STUDENT_SYNTHETIC_EMAIL_SUFFIX)
