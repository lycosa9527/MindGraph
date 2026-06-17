"""
Mask secrets for safe admin API display.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""


def mask_secret(secret: str, head: int = 4, tail: int = 4) -> str:
    """Show start/end of a stored secret; mask the middle for admin display only."""
    text = (secret or "").strip()
    if not text:
        return ""
    length = len(text)
    if length <= head + tail:
        if length <= 1:
            return "•"
        if length == 2:
            return text[0] + "•"
        return text[0] + "•" * (length - 2) + text[-1]
    mid = min(length - head - tail, 12)
    return text[:head] + "•" * mid + text[-tail:]
