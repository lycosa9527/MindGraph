"""
Assign diagram UUIDs for new saves (quota check + id generation).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import uuid

from utils.auth.school_tier_defs import (
    format_diagram_save_limit_error,
    is_unlimited_diagram_limit,
)


def assign_id_for_new_diagram(diagram_cap: int, current_count: int) -> tuple[str | None, str | None]:
    """
    Enforce trial quota, then assign a UUID for every allowed new diagram.

    Returns:
        (diagram_id, error_message) — diagram_id is set when save may proceed.
    """
    if not is_unlimited_diagram_limit(diagram_cap):
        if current_count >= diagram_cap:
            return None, format_diagram_save_limit_error(diagram_cap)
    return str(uuid.uuid4()), None
