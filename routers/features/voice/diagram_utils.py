"""Diagram helpers for voice command handling."""

from typing import Dict
import re

from routers.features.voice.state import logger


def get_diagram_prefix_map() -> Dict[str, str]:
    """
    Get the node ID prefix map for all supported diagram types.
    This ensures consistent node ID generation across the voice agent.

    Returns:
        Dictionary mapping diagram_type to node ID prefix
    """
    return {
        "circle_map": "context",
        "bubble_map": "attribute",
        "double_bubble_map": "node",
        "tree_map": "item",
        "flow_map": "step",
        "multi_flow_map": "step",  # Uses same prefix as flow_map
        "brace_map": "part",
        "bridge_map": "node",  # Bridge maps use node prefix
        "mindmap": "branch",
        "mind_map": "branch",  # Alias for mindmap
        "concept_map": "concept",
    }


def is_paragraph_text(text: str) -> bool:
    """
    Detect if input text is a paragraph (long text for processing) vs a command.

    Criteria:
    - Contains 30+ words OR contains multiple sentences (2+)
    - Not a simple command structure
    - Valid content (not just whitespace)

    Args:
        text: Input text to check

    Returns:
        True if text appears to be a paragraph for processing
    """
    # Input validation
    if not text:
        return False

    text_stripped = text.strip()

    # Must have minimum meaningful content
    if len(text_stripped) < 10:
        return False

    # Must not be too long (prevent abuse)
    if len(text_stripped) > 5000:
        logger.warning(
            "Text too long (%d chars), treating as paragraph but may be truncated",
            len(text_stripped),
        )
        # Still process, but warn

    # Count words (split by whitespace, filter empty strings)
    words = [w for w in text_stripped.split() if w.strip()]
    word_count = len(words)

    # Count sentences (periods, exclamation marks, question marks)
    sentence_endings = len(re.findall(r"[.!?。！？]", text_stripped))

    # Check word count and sentence count
    # Changed from 100 chars to 30 words - more accurate for paragraph detection
    is_long = word_count >= 30
    has_multiple_sentences = sentence_endings >= 2

    # Check if it looks like a command (short, imperative structure)
    command_prefixes = (
        "请",
        "帮我",
        "请帮我",
        "can you",
        "please",
        "change",
        "update",
        "add",
        "delete",
        "select",
    )
    command_suffixes = ("吗", "?", "？")
    is_command_like = (
        word_count < 10
        and sentence_endings <= 1
        and (text_stripped.startswith(command_prefixes) or text_stripped.endswith(command_suffixes))
    )

    # It's a paragraph if it has 30+ words OR has multiple sentences AND doesn't look like a command
    return (is_long or has_multiple_sentences) and not is_command_like
