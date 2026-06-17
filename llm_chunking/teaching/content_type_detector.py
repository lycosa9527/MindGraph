"""
Content type detector for teaching materials.

Re-exports ContentTypeAgent for convenience.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from llm_chunking.agents.content_type_agent import ContentTypeAgent

# Re-export for convenience
ContentTypeDetector = ContentTypeAgent

__all__ = ["ContentTypeDetector", "ContentTypeAgent"]
