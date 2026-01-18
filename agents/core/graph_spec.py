"""
Graph specification generation.

This module provides functions for generating graph specifications and
validating agent setup.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
import json
import logging
import threading
import yaml
from langchain_core.prompts import PromptTemplate

from config.settings import config
from prompts import get_prompt

from agents.core.llm_clients import llm_generation, llm_classification
from agents.core.utils import create_error_response, extract_yaml_from_code_block, _salvage_json_string

logger = logging.getLogger(__name__)


def generate_graph_spec(user_prompt: str, graph_type: str, language: str = 'zh') -> dict:
    """
    Use the LLM to generate a JSON spec for the given graph type.

    Args:
        user_prompt: The user's input prompt
        graph_type: Type of graph to generate ('double_bubble_map', 'bubble_map', etc.)
        language: Language for processing ('zh' or 'en')

    Returns:
        dict: JSON serializable graph specification
    """
    # Use centralized prompt registry
    try:
        # Get the appropriate prompt template
        prompt_text = get_prompt(graph_type, language, 'generation')

        if not prompt_text:
            logger.error("No prompt found for graph type: %s", graph_type)
            return create_error_response(
                f"No prompt template found for {graph_type}",
                "template",
                {"graph_type": graph_type}
            )

        # Sanitize template to ensure only {user_prompt} is a variable; all other braces become literal
        def _sanitize_prompt_template_for_langchain(template: str) -> str:
            placeholder = "<<USER_PROMPT_PLACEHOLDER>>"
            temp = template.replace("{user_prompt}", placeholder)
            temp = temp.replace("{", "{{").replace("}", "}}")
            return temp.replace(placeholder, "{user_prompt}")

        safe_template = _sanitize_prompt_template_for_langchain(prompt_text)
        prompt = PromptTemplate(
            input_variables=["user_prompt"],
            template=safe_template
        )
        # Use generation model for graph specification generation (high quality)
        formatted_prompt = prompt.format(user_prompt=user_prompt)
        yaml_text = llm_generation.invoke(formatted_prompt)
        # Some LLM clients return dict-like objects; ensure string
        try:
            raw_text = yaml_text if isinstance(yaml_text, str) else str(yaml_text)
        except Exception:  # pylint: disable=broad-except
            raw_text = f"{yaml_text}"
        yaml_text_clean = extract_yaml_from_code_block(raw_text)

        # Debug logging
        logger.debug("Raw LLM response for %s: %s", graph_type, yaml_text)
        logger.debug("Cleaned response: %s", yaml_text_clean)

        try:
            # Try JSON first, then YAML; if that fails, attempt to salvage JSON by stripping trailing backticks
            if not yaml_text_clean:
                raise ValueError("Empty cleaned text")
            try:
                spec = json.loads(yaml_text_clean)
            except json.JSONDecodeError:
                # Try to remove accidental trailing fences in the cleaned text
                cleaned = yaml_text_clean.strip().rstrip('`').strip()
                try:
                    spec = json.loads(cleaned)
                except Exception:  # pylint: disable=broad-except
                    # Attempt to salvage a JSON object from messy output
                    salvaged = _salvage_json_string(raw_text)
                    if salvaged:
                        try:
                            spec = json.loads(salvaged)
                        except Exception:  # pylint: disable=broad-except
                            spec = yaml.safe_load(yaml_text_clean)
                    else:
                        spec = yaml.safe_load(yaml_text_clean)

            if not spec:
                raise ValueError("JSON/YAML parse failed")

            # Note: Agent validation is now handled by specialized agents, not here

            logger.info("%s specification generated successfully", graph_type)
            if not isinstance(spec, dict):
                return create_error_response(
                    f"Invalid spec type: {type(spec)}",
                    "generation",
                    {"graph_type": graph_type}
                )
            return spec

        except Exception as e:  # pylint: disable=broad-except
            logger.error("%s JSON generation failed: %s", graph_type, e)
            return create_error_response(
                f"Failed to generate valid {graph_type} JSON",
                "generation",
                {"graph_type": graph_type}
            )

    except ImportError:
        logger.error("Failed to import centralized prompt registry")
        return create_error_response(
            "Prompt registry not available", "import", {"graph_type": graph_type}
        )
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Unexpected error in generate_graph_spec: %s", e)
        return create_error_response(
            f"Unexpected error generating {graph_type}",
            "unexpected",
            {"graph_type": graph_type}
        )


def get_agent_config() -> dict:
    """
    Get current agent configuration

    Returns:
        dict: Agent configuration
    """
    return {
        "llm_model": config.QWEN_MODEL,
        "llm_url": config.QWEN_API_URL,
        "temperature": config.QWEN_TEMPERATURE,
        "max_tokens": config.QWEN_MAX_TOKENS,
        "default_language": config.GRAPH_LANGUAGE
    }


def validate_agent_setup() -> bool:
    """
    Validate that the agent is properly configured with cross-platform timeout

    Returns:
        bool: True if agent is ready, False otherwise
    """
    def timeout_handler():
        raise TimeoutError("LLM validation timed out")

    timer = threading.Timer(config.QWEN_TIMEOUT, timeout_handler)
    timer.start()

    try:
        # Test LLM connection using classification model (fast/cheap)
        test_prompt = "Test"
        llm_classification.invoke(test_prompt)
        logger.info("LLM connection validation completed successfully")
        return True
    except TimeoutError:
        logger.error("LLM validation timed out")
        return False
    except Exception as e:  # pylint: disable=broad-except
        logger.error("LLM connection failed: %s", e)
        return False
    finally:
        timer.cancel()
