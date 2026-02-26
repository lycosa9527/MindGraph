"""
base agent module.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple
import logging

from dotenv import load_dotenv



# Load environment variables for logging configuration
load_dotenv()

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """
    Abstract base class for all MindGraph agents.

    This class defines the common interface and behavior that all
    specialized agents must implement.
    """

    def __init__(self, model='qwen'):
        """
        Initialize the base agent.

        Args:
            model (str): LLM model to use ('qwen', 'deepseek', 'kimi'). Defaults to 'qwen'.
        """
        self.language = 'zh'
        self.model = model  # Store model for this agent instance
        self.logger = logger

    @abstractmethod
    async def generate_graph(
        self,
        user_prompt: str,
        language: str = 'zh',
        dimension_preference: str | None = None,
        fixed_dimension: str | None = None,
        dimension_only_mode: bool | None = None,
        **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Generate a graph specification from user prompt.

        Args:
            user_prompt: User's input prompt
            language: Language for processing ('zh' or 'en')
            dimension_preference: Preferred dimension for tree/brace maps
            fixed_dimension: Fixed dimension that should not change
            dimension_only_mode: Generate topic from dimension only
            **kwargs: Additional parameters for specific agent types
                - user_id: User ID for token tracking
                - organization_id: Organization ID for token tracking
                - request_type: Request type for token tracking
                - endpoint_path: Endpoint path for token tracking

        Returns:
            dict: Graph specification with styling and metadata
        """

    def validate_output(self, output: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate the generated output.

        Args:
            output: Generated graph specification

        Returns:
            tuple: (is_valid, error_message)
        """
        if not output:
            return False, "Empty output"

        if isinstance(output, dict) and output.get('error'):
            return False, output.get('error', 'Unknown error')

        return True, ""

    def set_language(self, language: str) -> None:
        """Set the language for this agent."""
        self.language = language

    def get_language(self) -> str:
        """Get the current language setting."""
        return self.language
