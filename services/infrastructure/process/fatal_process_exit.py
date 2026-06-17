"""Process termination helpers for startup/shutdown paths.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import os
from typing import NoReturn


def fatal_startup_exit(code: int = 1) -> NoReturn:
    """
    Exit the process immediately without running ``sys.exit`` handlers.

    Used during multi-worker startup when a fatal configuration error must
    prevent the worker from serving traffic. ``sys.exit`` is unsafe here
    because Uvicorn workers may run shutdown hooks that assume a healthy
    application state.
    """
    os._exit(code)
