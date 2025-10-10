"""
Base Agent Class for MindGraph

This module provides the abstract base class that all specialized
agents inherit from, ensuring consistent interface and behavior.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
import logging
import os
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
    def generate_graph(self, user_prompt: str, language: str = 'zh') -> Dict[str, Any]:
        """
        Generate a graph specification from user prompt.
        
        Args:
            user_prompt: User's input prompt
            language: Language for processing ('zh' or 'en')
            
        Returns:
            dict: Graph specification with styling and metadata
        """
        pass
    
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
    
    def set_language(self, language: str):
        """Set the language for this agent."""
        self.language = language
    
    def get_language(self) -> str:
        """Get the current language setting."""
        return self.language
