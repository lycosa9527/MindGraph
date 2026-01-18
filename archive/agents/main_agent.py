"""
Main Agent Module for MindGraph.

This module contains the core agent functionality for generating custom graph content
using the Qwen LLM. It supports 10+ diagram types including bubble maps, flow maps,
tree maps, concept maps, mind maps, and more through intelligent LLM-based classification.

Features:
- Semantic diagram type detection using LLM classification
- Support for 10+ thinking map and concept map types
- Thread-safe statistics tracking
- Centralized error handling and validation
- Modular agent architecture with specialized diagram generators

The agent uses LLM-based prompt analysis to classify the user's intent and
generates the appropriate JSON specification for D3.js rendering.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import asyncio
import logging

from agents.core.topic_extraction import (
    extract_central_topic_llm
)
from agents.core.utils import (
    create_error_response
)

# Use standard logging like other modules
logger = logging.getLogger(__name__)


# Late imports to avoid circular dependencies
def _get_concept_map_agent():
    """Lazy import to avoid circular dependencies."""
    from agents.concept_maps.concept_map_agent import ConceptMapAgent
    return ConceptMapAgent


# ============================================================================
# MAIN AGENT CLASS (for architectural consistency)
# ============================================================================

class MainAgent:
    """
    Main Agent class that provides the BaseAgent interface for the entry point module.

    This class wraps the functional approach used in this module to provide
    architectural consistency with other agents while maintaining the existing
    API that the application depends on.
    """

    def __init__(self):
        """Initialize the main agent."""
        self.language = 'zh'  # Default language
        self.logger = logger

    def generate_graph(self, user_prompt: str, language: str = "zh") -> dict:
        """
        Generate a graph specification from user prompt.

        This method implements the BaseAgent interface by delegating to the
        existing functional API in this module.

        Args:
            user_prompt: User's input prompt
            language: Language for processing ('zh' or 'en')

        Returns:
            dict: Graph specification with styling and metadata
        """
        try:
            # Use LLM-based topic extraction instead of hardcoded string manipulation
            central_topic = extract_central_topic_llm(user_prompt, language)

            if not central_topic.strip():
                return create_error_response("Failed to extract topic from prompt", "extraction")

            # Generate the graph specification using the simplified workflow
            ConceptMapAgent = _get_concept_map_agent()
            agent = ConceptMapAgent()
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            result = loop.run_until_complete(agent.generate_graph(user_prompt, language))
            if isinstance(result, dict) and 'spec' in result:
                return result['spec']
            return create_error_response("Failed to generate concept map", "generation")

        except Exception as e:  # pylint: disable=broad-except
            logger.error("MainAgent: Generation error: %s", e)
            return create_error_response(
                f"MainAgent generation failed: {str(e)}", "main_agent"
            )

    def set_language(self, language: str) -> None:
        """Set the language for this agent."""
        self.language = language

    def get_language(self) -> str:
        """Get the current language setting."""
        return self.language
