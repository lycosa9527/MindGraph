"""
Maite prompt registry exports.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from services.maite.prompts.registry import (
    PromptRegistry,
    PromptTemplate,
    RenderedPrompt,
    get_prompt_registry,
)

__all__ = [
    "PromptRegistry",
    "PromptTemplate",
    "RenderedPrompt",
    "get_prompt_registry",
]
