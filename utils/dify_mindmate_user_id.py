"""
Dify ``user`` string for MindMate (web) — stable per MindGraph account.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from uuid import UUID

from models.domain.auth import User
from utils.auth import AUTH_MODE


def mindmate_dify_user_id(user: User) -> str:
    """
    Return the Dify API user id for this MindGraph user.

    In Bayi vendor SSO, ``users.phone`` stores the external user UUID; when it
    parses as an RFC-4122 UUID, use that canonical string (matches Dify-facing
    identity to the school IdP). Bayi passkey uses a non-UUID phone and keeps
    the generic ``mg_user_<pk>`` form. All other auth modes use ``mg_user_<pk>``.
    """
    if AUTH_MODE == "bayi" and user.phone:
        stripped = user.phone.strip()
        try:
            return str(UUID(stripped))
        except ValueError:
            pass
    return f"mg_user_{user.id}"
