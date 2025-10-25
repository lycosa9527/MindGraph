"""
Qwen LangChain Wrapper

Custom LangChain LLM implementation that uses existing QwenClient.

@author lycosa9527
@made_by MindSpring Team
"""

from typing import Any, List, Optional
from langchain_core.language_models.llms import LLM
from langchain_core.callbacks.manager import CallbackManagerForLLMRun
import logging

from agents.main_agent import QwenLLM as QwenLLMBase

logger = logging.getLogger(__name__)


class QwenLLM(LLM):
    """
    Custom LangChain LLM that wraps QwenLLM from main_agent.
    
    This allows us to use our existing Qwen setup with LangChain agents.
    """
    
    qwen_llm: QwenLLMBase = None
    model_type: str = 'generation'
    
    def __init__(self, model_type: str = 'generation', **kwargs):
        """
        Initialize Qwen LangChain wrapper.
        
        Args:
            model_type: 'classification' or 'generation'
        """
        super().__init__(**kwargs)
        self.qwen_llm = QwenLLMBase(model_type=model_type)
        self.model_type = model_type
        logger.info(f"[QWEN-LC] QwenLLM initialized | Model: {model_type}")
    
    @property
    def _llm_type(self) -> str:
        """Return identifier for this LLM."""
        return "qwen"
    
    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        """
        Call Qwen LLM with the given prompt.
        
        Args:
            prompt: The prompt to send to the LLM
            stop: List of stop sequences (not used by Qwen currently)
            run_manager: LangChain callback manager
            **kwargs: Additional arguments
        
        Returns:
            Generated text from Qwen
        """
        try:
            # Call wrapped QwenLLM
            response = self.qwen_llm._call(prompt)
            
            return response
            
        except Exception as e:
            logger.error(f"[QWEN-LC] Error calling Qwen: {str(e)}", exc_info=True)
            raise
    
    @property
    def _identifying_params(self) -> dict:
        """Get the identifying parameters."""
        return {
            "model": "qwen",
            "model_type": self.model_type
        }

