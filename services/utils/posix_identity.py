"""
POSIX process identity helpers (root check without Windows pylint noise).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os


def is_posix_root() -> bool:
    """True when the current process is UID 0 on a POSIX system."""
    if os.name != "posix":
        return False
    geteuid = getattr(os, "geteuid", None)
    if geteuid is None:
        return False
    try:
        return geteuid() == 0
    except OSError:
        return False
