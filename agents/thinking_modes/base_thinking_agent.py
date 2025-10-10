"""
Base Thinking Mode Agent
=========================

Abstract base class for all diagram-specific ThinkGuide agents.
Provides common workflow, session management, and LLM communication.

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from abc import ABC, abstractmethod
from typing import Dict, AsyncGenerator, Optional

from config.settings import config
from services.llm_service import llm_service

logger = logging.getLogger(__name__)


class BaseThinkingAgent(ABC):
    """
    Abstract base class for diagram-specific ThinkGuide agents.
    
    Responsibilities:
    - Session management
    - LLM communication
    - Common workflow patterns
    - Language detection
    
    Subclasses must implement:
    - Diagram-specific intent detection
    - Diagram-specific prompts
    - Diagram-specific action handlers
    """
    
    def __init__(self, diagram_type: str):
        """
        Initialize base agent.
        
        Args:
            diagram_type: Type of diagram this agent handles (e.g., 'circle_map')
        """
        self.diagram_type = diagram_type
        
        # Use centralized LLM Service
        self.llm = llm_service
        self.model = 'qwen-plus'  # Better reasoning than qwen-turbo
        
        # Session storage (in-memory for MVP)
        self.sessions: Dict[str, Dict] = {}
        
        logger.info(f"[{self.__class__.__name__}] Initialized for diagram type: {diagram_type}")
    
    # ===== SESSION MANAGEMENT =====
    
    def _get_or_create_session(
        self,
        session_id: str,
        diagram_data: Optional[Dict] = None,
        initial_state: str = 'CONTEXT_GATHERING'
    ) -> Dict:
        """
        Get existing session or create new one.
        
        Args:
            session_id: Unique session identifier
            diagram_data: Initial diagram data
            initial_state: Starting state for new sessions
            
        Returns:
            Session dictionary
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = {
                'session_id': session_id,
                'state': initial_state,
                'diagram_data': diagram_data or {},
                'context': {},
                'history': [],
                'language': 'en'
            }
            logger.info(f"[{self.__class__.__name__}] Created new session: {session_id}")
        
        return self.sessions[session_id]
    
    # ===== LANGUAGE DETECTION =====
    
    def _detect_language(self, text: str) -> str:
        """
        Detect if text is primarily Chinese or English.
        
        Args:
            text: Input text to analyze
            
        Returns:
            'zh' for Chinese, 'en' for English
        """
        if not text:
            return 'en'
        chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
        return 'zh' if chinese_chars > len(text) * 0.3 else 'en'
    
    # ===== LLM COMMUNICATION =====
    
    async def _stream_llm_response(
        self,
        system_prompt: str,
        user_prompt: str,
        session: Dict
    ) -> AsyncGenerator[str, None]:
        """
        Stream LLM response with proper SSE formatting.
        
        Args:
            system_prompt: System message for LLM
            user_prompt: User message for LLM
            session: Current session data
            
        Yields:
            SSE-formatted text chunks
        """
        try:
            logger.info(f"[{self.__class__.__name__}] Streaming LLM response")
            
            # Use centralized LLM service for streaming
            async for chunk in self.llm.chat_stream(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                temperature=0.7
            ):
                # SSE format: data: {json}\n\n
                yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
            
            # End marker
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] LLM streaming error: {e}")
            error_msg = "I encountered an error. Please try again."
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
    
    # ===== ABSTRACT METHODS (Subclasses MUST implement) =====
    
    @abstractmethod
    async def chat(
        self,
        session_id: str,
        message: str,
        diagram_data: Optional[Dict] = None
    ) -> AsyncGenerator[str, None]:
        """
        Main chat interface - handle user message and stream response.
        
        Args:
            session_id: Unique session identifier
            message: User's message
            diagram_data: Current diagram data
            
        Yields:
            SSE-formatted response chunks
        """
        pass
    
    @abstractmethod
    async def _detect_user_intent(
        self,
        message: str,
        diagram_data: Dict,
        session: Dict
    ) -> Dict:
        """
        Detect what the user wants to do with the diagram.
        
        This is diagram-specific because different diagrams have different actions.
        For example:
        - Circle Map: change_center, add_context, update_context
        - Mind Map: add_branch, add_subtopic, reorganize
        - Tree Map: add_category, add_item, move_item
        
        Args:
            message: User's message
            diagram_data: Current diagram data
            session: Current session
            
        Returns:
            Intent dictionary with action and parameters
        """
        pass
    
    @abstractmethod
    def _get_system_prompt(self, state: str, language: str) -> str:
        """
        Get diagram-specific system prompt for current state.
        
        Args:
            state: Current workflow state
            language: 'zh' or 'en'
            
        Returns:
            System prompt string
        """
        pass
    
    @abstractmethod
    async def _generate_suggested_nodes(self, session: Dict) -> list:
        """
        Generate diagram-specific node suggestions.
        
        This is where diagram types differ most:
        - Circle Map: Observation-based suggestions
        - Bubble Map: Adjective suggestions
        - Mind Map: Branch/subtopic suggestions
        - Tree Map: Category/item suggestions
        
        Args:
            session: Current session with context
            
        Returns:
            List of suggested node texts
        """
        pass
    
    # ===== HELPER METHODS (Optional to override) =====
    
    def _validate_diagram_action(self, action: str, diagram_data: Dict) -> bool:
        """
        Validate if an action is valid for current diagram state.
        
        Subclasses can override for diagram-specific validation.
        
        Args:
            action: Action type (e.g., 'change_center', 'add_nodes')
            diagram_data: Current diagram data
            
        Returns:
            True if action is valid, False otherwise
        """
        return True  # Default: allow all actions

