"""
Agent utilities module - backward compatibility wrapper.

This module re-exports functions from specialized modules to maintain
backward compatibility with existing code.

For new code, prefer importing directly from:
- agents.core.json_parser for JSON parsing
- agents.core.characteristics for characteristics generation
- agents.core.topic_extraction_utils for topic extraction

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
# JSON parsing functions
from .json_parser import (
    extract_json_from_response,
)

# Characteristics generation functions
from .characteristics import (
    generate_characteristics_with_agent,
    parse_characteristics_result,
    generate_characteristics_fallback,
)

# Topic extraction functions
from .topic_extraction_utils import (
    extract_topics_with_agent,
    parse_topic_extraction_result,
    extract_topics_from_prompt,
)

# Note: The following functions are deprecated/unused and not re-exported:
# - detect_language() - Not used externally, exists in other modules
# - validate_agent_output() - Not used externally

__all__ = [
    # JSON parsing
    'extract_json_from_response',
    # Characteristics generation
    'generate_characteristics_with_agent',
    'parse_characteristics_result',
    'generate_characteristics_fallback',
    # Topic extraction
    'extract_topics_with_agent',
    'parse_topic_extraction_result',
    'extract_topics_from_prompt',
]
