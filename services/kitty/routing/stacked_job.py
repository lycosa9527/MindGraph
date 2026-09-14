"""Detect stacked one-sentence jobs (rename + fill, then/and).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re

# Fast path is a skip-LLM gate only. Stacked jobs go to qwen3.8-flash.
# Do not treat a leading 再加一个… as stacked — that is one add.
JOB_JOIN_RE = re.compile(
    r"并且|，并|并自动|and then|, then|，再|，然后|"
    r"(?:改成|换成|改为|变成|设为).{1,40}再"
)
FILL_JOB_RE = re.compile(r"补全|补完|完善|填充|自动完成|完成这")
STACKED_JOB_RE = re.compile(rf"(?:{JOB_JOIN_RE.pattern})|(?:{FILL_JOB_RE.pattern})")


def utterance_has_stacked_job(text: str) -> bool:
    """True when the utterance stacks more than one canvas job."""
    return bool(text and STACKED_JOB_RE.search(text))


def utterance_has_fill_follow_up(text: str) -> bool:
    """True when the utterance also asks to auto-complete the diagram."""
    return bool(text and FILL_JOB_RE.search(text))
