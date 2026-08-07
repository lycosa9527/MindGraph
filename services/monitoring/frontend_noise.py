"""Detect benign browser / WeChat / stale-asset noise from frontend error reports.

Scoped to ``source=frontend`` ingress only — never mute application/llm/mindbot
failures that share similar substrings.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re

_RESIZE_OBSERVER_NOISE = re.compile(
    r"ResizeObserver loop (limit exceeded|completed with undelivered notifications)",
    re.IGNORECASE,
)
_SCRIPT_ERROR_NOISE = re.compile(r"Script error\.?", re.IGNORECASE)
_WECHAT_BRIDGE_NOISE = re.compile(
    r"weixinPostMessageHandlers|weixinDispatchMessage|WeixinJSBridge",
    re.IGNORECASE,
)
# Keep in sync with frontend/src/utils/staleChunkReload.ts
_STALE_CHUNK_NOISE = re.compile(
    r"Failed to fetch dynamically imported module|"
    r"error loading dynamically imported module|"
    r"Unable to preload CSS for|"
    r"Importing a module script failed|"
    r"Loading chunk [\w-]+ failed",
    re.IGNORECASE,
)


def is_benign_frontend_noise(message: str) -> bool:
    """Return True when a frontend-reported message should not enter error collection."""
    text = (message or "").strip()
    if not text:
        return False
    if _RESIZE_OBSERVER_NOISE.search(text):
        return True
    if _SCRIPT_ERROR_NOISE.search(text):
        return True
    if _WECHAT_BRIDGE_NOISE.search(text):
        return True
    if _STALE_CHUNK_NOISE.search(text):
        return True
    return False
