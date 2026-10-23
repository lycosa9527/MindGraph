"""
Dify ``user`` string for MindMate (web) — stable per MindGraph account.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import re
from uuid import UUID

from models.domain.auth import User
from utils.auth import AUTH_MODE

logger = logging.getLogger(__name__)

_PREFIX_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
_PREFIX_MAX_LEN = 32
_TEMPLATE_PREFIX = "dev_yourname"
_PREFIX_ERROR = (
    "Set MINDMATE_DIFY_USER_PREFIX in .env. "
    "Each developer uses their own dev_<name>, such as dev_roy. "
    "A school install uses a stable name, such as bayi. "
    "Use 1-32 lowercase letters, digits, or single underscores."
)
_TEMPLATE_PREFIX_ERROR = (
    _PREFIX_ERROR + " The value dev_yourname is only the env.example sample. Replace it with your own name."
)


class MindmateDifyUserPrefixError(RuntimeError):
    """``MINDMATE_DIFY_USER_PREFIX`` is missing or not a usable install name."""


def describe_mindmate_dify_user_prefix_error() -> str | None:
    """Return why ``MINDMATE_DIFY_USER_PREFIX`` cannot be used, or None when it is valid."""
    raw = (os.getenv("MINDMATE_DIFY_USER_PREFIX") or "").strip().lower()
    if raw == _TEMPLATE_PREFIX:
        return _TEMPLATE_PREFIX_ERROR
    if raw and len(raw) <= _PREFIX_MAX_LEN and _PREFIX_RE.fullmatch(raw):
        return None
    return _PREFIX_ERROR


def mindmate_dify_user_prefix() -> str:
    """Required deployment prefix from ``MINDMATE_DIFY_USER_PREFIX``."""
    error = describe_mindmate_dify_user_prefix_error()
    if error is None:
        return (os.getenv("MINDMATE_DIFY_USER_PREFIX") or "").strip().lower()
    logger.error(error)
    raise MindmateDifyUserPrefixError(error)


def _bayi_dify_user_id(user: User) -> str:
    """Bayi vendor UUID stored in ``users.phone``, or empty when this account is not one."""
    if AUTH_MODE == "bayi" and user.phone:
        stripped = user.phone.strip()
        try:
            return str(UUID(stripped))
        except ValueError:
            return ""
    return ""


def _legacy_mg_user_id(user: User) -> str:
    return f"mg_user_{user.id}"


def mindmate_dify_user_id(user: User) -> str:
    """
    Return the Dify API user id for this MindGraph user.

    In Bayi vendor SSO, ``users.phone`` stores the external user UUID; when it
    parses as an RFC-4122 UUID, use that canonical string (matches Dify-facing
    identity to the school IdP). Every other account uses
    ``{prefix}_mg_user_<pk>``. ``MINDMATE_DIFY_USER_PREFIX`` is required.
    """
    bayi = _bayi_dify_user_id(user)
    if bayi:
        return bayi
    return f"{mindmate_dify_user_prefix()}_{_legacy_mg_user_id(user)}"


def mindmate_dify_user_aliases(user: User) -> list[str]:
    """Ids that may own this account's web MindMate threads. Canonical id is first."""
    canonical = mindmate_dify_user_id(user)
    if _bayi_dify_user_id(user):
        return [canonical]
    legacy = _legacy_mg_user_id(user)
    if canonical == legacy:
        return [canonical]
    return [canonical, legacy]
