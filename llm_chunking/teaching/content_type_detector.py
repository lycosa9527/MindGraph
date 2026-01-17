"""
Content type detector for teaching materials.

Re-exports ContentTypeAgent for convenience.
"""

from llm_chunking.agents.content_type_agent import ContentTypeAgent

# Re-export for convenience
ContentTypeDetector = ContentTypeAgent

__all__ = ["ContentTypeDetector", "ContentTypeAgent"]
