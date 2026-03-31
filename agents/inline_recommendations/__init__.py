"""
Inline Recommendations - Diagram auto-completion for mindmap, flow_map, tree_map, brace_map.

When user has defined the topic, double-clicking on branch/step/substep nodes triggers
context-aware AI recommendations displayed in an inline picker.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from agents.inline_recommendations.cleanup import start_inline_rec_cleanup_scheduler
from agents.inline_recommendations.generator import (
    get_inline_recommendations_generator,
    InlineRecommendationsGenerator,
)

__all__ = [
    "get_inline_recommendations_generator",
    "InlineRecommendationsGenerator",
    "start_inline_rec_cleanup_scheduler",
]
