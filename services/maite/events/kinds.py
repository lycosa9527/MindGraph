"""
Maite session event kind literals.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Literal

MaiteEventKind = Literal[
    "stage_advanced",
    "stream_chunk",
    "stream_complete",
    "stream_error",
    "diagnosis_progress",
    "remedy_prepared",
    "variant_scored",
    "session_completed",
    "practice_dirty",
    "stop",
]

__all__ = ["MaiteEventKind"]
