"""
Base Thinking Mode Agent (ReAct Pattern)
==========================================

Abstract base class for all diagram-specific ThinkGuide agents.
Implements the ReAct pattern: Reason → Act → Observe cycle.

Each diagram type extends this base to provide unique behavior:
- Circle Map: Socratic refinement of observations and context
- Bubble Map: Attribute-focused descriptive thinking
- Tree Map: Hierarchical categorization
- Mind Map: Branch organization and concept relationships
- Flow Map: Sequential and causal reasoning

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from abc import ABC, abstractmethod
from typing import Dict, AsyncGenerator, Optional, List
from enum import Enum

from config.settings import config
from services.llm_service import llm_service

logger = logging.getLogger(__name__)


class ReActStep(Enum):
    """ReAct pattern steps"""
    REASON = "reason"      # Understand user intent and context
    ACT = "act"            # Execute action (modify diagram or respond)
    OBSERVE = "observe"    # Observe results and continue dialogue


class BaseThinkingAgent(ABC):
    """
    Abstract base class for diagram-specific ThinkGuide agents.
    
    Implements ReAct Pattern:
    1. REASON: Use LLM to understand user intent and diagram context
    2. ACT: Execute diagram modifications or generate responses
    3. OBSERVE: Provide feedback and continue the dialogue
    
    Responsibilities:
    - Session management
    - LLM communication (streaming)
    - ReAct workflow orchestration
    - Language detection
    
    Subclasses MUST implement:
    - Diagram-specific intent detection (_detect_user_intent)
    - Diagram-specific action handlers (_handle_action)
    - Diagram-specific prompts (_get_system_prompt)
    - Diagram-specific node generation (_generate_suggested_nodes)
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
        
        logger.debug(f"[{self.__class__.__name__}] Initialized for diagram type: {diagram_type}")
    
    # ===== SESSION MANAGEMENT =====
    
    def _get_or_create_session(
        self,
        session_id: str,
        diagram_data: Optional[Dict] = None,
        user_id: str = None,
        initial_state: str = 'CONTEXT_GATHERING'
    ) -> Dict:
        """
        Get existing session or create new one.
        
        Args:
            session_id: Unique session identifier
            diagram_data: Initial diagram data
            user_id: User identifier
            initial_state: Starting state for new sessions
            
        Returns:
            Session dictionary
        """
        if session_id not in self.sessions:
            # Detect language from diagram data
            language = 'en'
            if diagram_data:
                # Extract text based on diagram structure
                # Mindmaps, tree maps use 'topic', others use 'center.text' or specific fields
                center_text = (
                    diagram_data.get('topic', '') or  # mindmap, tree_map
                    diagram_data.get('title', '') or  # flow_map
                    diagram_data.get('whole', '') or  # brace_map
                    diagram_data.get('event', '') or  # multi_flow_map
                    diagram_data.get('dimension', '') or  # bridge_map
                    diagram_data.get('left', '') or  # double_bubble_map
                    diagram_data.get('center', {}).get('text', '')  # circle_map, bubble_map
                )
                language = self._detect_language(center_text)
                logger.debug(f"[{self.__class__.__name__}] Language detection from text: '{center_text[:30]}...' → {language}")
            
            self.sessions[session_id] = {
                'session_id': session_id,
                'user_id': user_id,
                'state': initial_state,
                'diagram_data': diagram_data or {},
                'context': {},
                'history': [],
                'language': language,
                'node_count': len(diagram_data.get('children', [])) if diagram_data else 0
            }
            logger.debug(f"[{self.__class__.__name__}] Created session: {session_id} | Language: {language}")
        
        return self.sessions[session_id]
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session by ID (for external access)"""
        return self.sessions.get(session_id)
    
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
    
    # ===== REACT PATTERN: MAIN ENTRY POINT =====
    
    async def process_step(
        self,
        message: str,
        session_id: str,
        diagram_data: Dict,
        current_state: str,
        user_id: str = None,
        organization_id: int = None,  # Added for token tracking
        is_initial_greeting: bool = False,
        language: str = 'en'
    ) -> AsyncGenerator[Dict, None]:
        """
        Main ReAct cycle: Reason → Act → Observe
        
        This is the primary entry point called by the API router.
        
        Args:
            message: User's message
            session_id: Unique session identifier
            diagram_data: Current diagram data
            current_state: Current workflow state
            user_id: User identifier
            
        Yields:
            SSE events (message_chunk, diagram_update, state_transition, etc.)
        """
        # Get or create session
        session = self._get_or_create_session(
            session_id=session_id,
            diagram_data=diagram_data,
            user_id=user_id,
            initial_state=current_state
        )
        
        # Store organization_id in session for token tracking
        if organization_id is not None:
            session['organization_id'] = organization_id
        
        # Update language in session (from UI toggle)
        session['language'] = language
        
        # Update diagram data if provided
        if diagram_data:
            session['diagram_data'] = diagram_data
            session['node_count'] = len(diagram_data.get('children', []))
        
        logger.debug(
            f"[{self.__class__.__name__}] ReAct cycle started | "
            f"State: {current_state} | Message: {message[:50] if message else 'None'}..."
        )
        
        # ReAct Step 1: REASON - Understand user intent
        intent = await self._reason(session, message, current_state, is_initial_greeting)
        
        logger.debug(f"[{self.__class__.__name__}] REASON → Intent: {intent.get('action', 'unknown')}")
        
        # ReAct Step 2: ACT - Execute action based on intent
        async for event in self._act(session, intent, message, current_state):
            yield event
        
        # ReAct Step 3: OBSERVE - Handled within _act through streaming responses
        # The agent observes results and continues dialogue naturally
    
    # ===== REACT STEP 1: REASON =====
    
    async def _reason(
        self,
        session: Dict,
        message: str,
        current_state: str,
        is_initial_greeting: bool = False
    ) -> Dict:
        """
        ReAct Step 1: REASON
        
        Use LLM to understand user intent within diagram context.
        This is diagram-specific because different diagrams have different actions.
        
        Args:
            session: Current session
            message: User's message
            current_state: Current workflow state
            is_initial_greeting: If True, this is a new session requesting initial greeting
            
        Returns:
            Intent dictionary with action and parameters
        """
        # Handle explicit greeting request for new sessions
        if is_initial_greeting:
            # Check if session has history to avoid duplicate greeting
            has_history = len(session.get('history', [])) > 0
            
            if has_history:
                # Session already has conversation - will send welcome back message
                logger.debug(f"[{self.__class__.__name__}] Greeting requested but session has history - will send welcome back message")
                return {'action': 'resume', 'state': current_state}
            else:
                # New session - greet user
                return {'action': 'greet', 'state': current_state}
        
        # No message and no greeting request = just resume
        if not message:
            return {'action': 'resume', 'state': current_state}
        
        # Delegate to diagram-specific intent detection for actual user messages
        return await self._detect_user_intent(session, message, current_state)
    
    # ===== REACT STEP 2: ACT =====
    
    async def _act(
        self,
        session: Dict,
        intent: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """
        ReAct Step 2: ACT
        
        Execute action based on detected intent.
        Delegates to diagram-specific handlers.
        
        Args:
            session: Current session
            intent: Detected intent from REASON step
            message: User's original message
            current_state: Current workflow state
            
        Yields:
            SSE events (message_chunk, diagram_update, etc.)
        """
        action = intent.get('action', 'discuss')
        
        # Route to appropriate handler
        if action == 'greet':
            # Initial greeting for this state
            async for event in self._handle_greeting(session, current_state):
                yield event
        
        elif action == 'resume':
            # Panel reopened - send a friendly welcome back message
            logger.debug(f"[{self.__class__.__name__}] Resuming existing conversation | History: {len(session.get('history', []))} messages")
            
            # Send a friendly "welcome back" message
            language = session.get('language', 'en')
            if language == 'zh':
                welcome_message = "👋 欢迎回来！让我们继续探索吧。有什么我可以帮助你的吗？"
            else:
                welcome_message = "👋 Welcome back! Let's continue exploring. How can I help you?"
            
            # Stream the welcome message
            yield {
                'event': 'message_chunk',
                'content': welcome_message
            }
            
            yield {
                'event': 'message_complete',
                'new_state': current_state
            }
        
        elif action == 'discuss':
            # Pure discussion, no diagram changes
            async for event in self._handle_discussion(session, message, current_state):
                yield event
        
        else:
            # Diagram-specific action (delegated to subclass)
            async for event in self._handle_action(session, intent, message, current_state):
                yield event
    
    # ===== LLM COMMUNICATION HELPERS =====
    
    async def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        session: Dict,
        temperature: float = 0.3
    ) -> str:
        """
        Call LLM for non-streaming responses (e.g., intent detection).
        
        Args:
            system_prompt: System message for LLM
            user_prompt: User prompt for LLM
            session: Current session
            temperature: LLM temperature (lower for more deterministic)
            
        Returns:
            Complete response string
            
        Raises:
            AttributeError: If LLM service is not properly initialized
            Exception: If LLM call fails
        """
        try:
            # Validate LLM service is initialized
            if not hasattr(self, 'llm') or self.llm is None:
                error_msg = f"[{self.__class__.__name__}] LLM service not initialized. Check __init__ method."
                logger.error(error_msg)
                raise AttributeError(error_msg)
            
            # Validate LLM service has chat method
            if not hasattr(self.llm, 'chat'):
                error_msg = f"[{self.__class__.__name__}] LLM service does not have 'chat' method. Type: {type(self.llm)}"
                logger.error(error_msg)
                raise AttributeError(error_msg)
            
            # Validate model is set
            if not hasattr(self, 'model') or not self.model:
                logger.warning(f"[{self.__class__.__name__}] Model not set, using default 'qwen-plus'")
                self.model = 'qwen-plus'
            
            # Get user context from session for token tracking
            user_id = session.get('user_id')
            organization_id = session.get('organization_id')
            
            response = await self.llm.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                temperature=temperature,
                user_id=int(user_id) if user_id and str(user_id).isdigit() else None,
                organization_id=organization_id,
                request_type='thinkguide',
                endpoint_path='/thinking_mode/intent',
                conversation_id=session.get('session_id'),
                diagram_type=self.diagram_type
            )
            
            return response
            
        except AttributeError as e:
            # Re-raise AttributeError with better context
            logger.error(f"[{self.__class__.__name__}] Attribute error in _call_llm: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] LLM call error: {e}", exc_info=True)
            raise
    
    async def _stream_llm_response(
        self,
        prompt: str,
        session: Dict,
        temperature: float = 0.7
    ) -> AsyncGenerator[Dict, None]:
        """
        Stream LLM response as SSE chunks.
        
        Args:
            prompt: User prompt for LLM
            session: Current session
            temperature: LLM temperature
            
        Yields:
            SSE event dictionaries
        """
        try:
            language = session.get('language', 'en')
            system_prompt = self._get_base_system_prompt(language)
            
            # Get user context from session for token tracking
            user_id = session.get('user_id')
            organization_id = session.get('organization_id')
            
            full_content = ""
            
            async for chunk in self.llm.chat_stream(
                prompt=prompt,
                model=self.model,
                system_message=system_prompt,
                temperature=temperature,
                # Token tracking parameters
                user_id=int(user_id) if user_id and str(user_id).isdigit() else None,
                organization_id=organization_id,
                request_type='thinkguide',
                endpoint_path='/thinking_mode/stream',
                conversation_id=session.get('session_id'),
                diagram_type=self.diagram_type
            ):
                full_content += chunk
                yield {
                    'event': 'message_chunk',
                    'content': chunk
                }
            
            # Store in history
            session['history'].append({
                'role': 'assistant',
                'content': full_content,
                'state': session.get('state', 'UNKNOWN')
            })
            
            yield {
                'event': 'message_complete',
                'full_content': full_content
            }
        
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] LLM streaming error: {e}", exc_info=True)
            yield {
                'event': 'error',
                'message': str(e)
            }
    
    def _get_base_system_prompt(self, language: str) -> str:
        """
        Get base system prompt (applies to all diagram types).
        
        Args:
            language: 'zh' or 'en'
            
        Returns:
            System prompt string
        """
        if language == 'zh':
            return """你是一位专业的思维教学专家（Teaching Thinking Professional）。

你的角色：
- 帮助K12教师通过苏格拉底式提问深化思考
- 引导教师发现概念的本质和优先级
- 培养批判性思维和教学设计能力

你的风格：
- 简洁、清晰、专业
- 不使用表情符号
- 直接、有针对性
- 提问而非说教
- 使用自然的段落划分：相关的句子保持在同一段落中，仅在话题转换时换段"""
        else:
            return """You are a Teaching Thinking Professional.

Your role:
- Help K12 teachers deepen thinking through Socratic questioning
- Guide teachers to discover essence and priorities of concepts
- Develop critical thinking and instructional design skills

Your style:
- Concise, clear, professional
- No emojis
- Direct and targeted
- Ask, don't lecture
- Use natural paragraph breaks: keep related sentences together, only break paragraphs when topics shift"""
    
    # ===== DEFAULT ACTION HANDLERS =====
    
    def _get_default_prompt(self, session: Dict, message: str = None) -> str:
        """
        Default prompt fallback for unhandled states.
        
        Args:
            session: Current session
            message: User message (optional)
            
        Returns:
            Generic prompt string
        """
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        
        # Try to get topic from common fields
        topic = (
            diagram_data.get('topic', '') or
            diagram_data.get('center', {}).get('text', '') or
            diagram_data.get('event', '') or
            diagram_data.get('whole', '') or
            diagram_data.get('left', '') or
            diagram_data.get('title', '') or
            diagram_data.get('dimension', '') or
            'your diagram'
        )
        
        if language == 'zh':
            return f"让我们继续完善关于「{topic}」的图表。您有什么想法或问题吗？"
        return f"Let's continue refining your diagram about \"{topic}\". What are your thoughts or questions?"
    
    async def _handle_greeting(
        self,
        session: Dict,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """
        Handle initial greeting for a state.
        Delegates to diagram-specific prompt system.
        """
        prompt = self._get_state_prompt(session, current_state)
        async for event in self._stream_llm_response(prompt, session):
            yield event
    
    async def _handle_discussion(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """
        Handle pure discussion (no diagram modifications).
        Uses LLM to provide thoughtful response within educational context.
        """
        diagram_data = session.get('diagram_data', {})
        center = diagram_data.get('center', {}).get('text', 'this topic')
        nodes = diagram_data.get('children', [])
        context = session.get('context', {})
        
        language = session.get('language', 'en')
        
        if language == 'zh':
            discussion_prompt = f"""教师正在讨论关于「{center}」的{self.diagram_type}。

当前状态：{current_state}
节点数量：{len(nodes)}
教学背景：{context.get('raw_message', '未指定')}

教师说：{message}

请作为思维教练回应：
1. 承认他们的想法
2. 提出1-2个深入的苏格拉底式问题
3. 鼓励进一步思考

保持简洁、专业、无表情符号。"""
        else:
            discussion_prompt = f"""Teacher is discussing a {self.diagram_type} about "{center}".

Current state: {current_state}
Node count: {len(nodes)}
Educational context: {context.get('raw_message', 'Not specified')}

Teacher said: {message}

Respond as a thinking coach:
1. Acknowledge their thoughts
2. Ask 1-2 deeper Socratic questions
3. Encourage further thinking

Keep it concise, professional, no emojis."""
        
        async for event in self._stream_llm_response(discussion_prompt, session):
            yield event
    
    # ===== ABSTRACT METHODS (Subclasses MUST implement) =====
    
    @abstractmethod
    async def _detect_user_intent(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> Dict:
        """
        Detect what the user wants to do (diagram-specific).
        
        This is where diagram types differ significantly:
        - Circle Map: change_center, add_observations, update_context
        - Bubble Map: add_attributes, change_subject, update_adjective
        - Tree Map: add_category, add_item, reorganize
        - Mind Map: add_branch, add_subtopic, reorganize
        
        Args:
            session: Current session
            message: User's message
            current_state: Current workflow state
            
        Returns:
            Intent dictionary with 'action' and relevant parameters
        """
        pass
    
    @abstractmethod
    async def _handle_action(
        self,
        session: Dict,
        intent: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """
        Handle diagram-specific actions.
        
        Args:
            session: Current session
            intent: Detected intent
            message: User's original message
            current_state: Current workflow state
            
        Yields:
            SSE events (acknowledgment, diagram_update, completion)
        """
        pass
    
    @abstractmethod
    def _get_state_prompt(
        self,
        session: Dict,
        state: str
    ) -> str:
        """
        Get diagram-specific prompt for current state.
        
        Args:
            session: Current session
            state: Current workflow state
            
        Returns:
            Prompt string
        """
        pass
    
    @abstractmethod
    async def _generate_suggested_nodes(
        self,
        session: Dict
    ) -> List[Dict]:
        """
        Generate diagram-specific node suggestions.
        
        This is where diagram types differ most:
        - Circle Map: Observation-based suggestions
        - Bubble Map: Adjective/attribute suggestions
        - Mind Map: Branch/subtopic suggestions
        - Tree Map: Category/item suggestions
        
        Args:
            session: Current session with context
            
        Returns:
            List of suggested nodes (format: [{'text': '...', 'position': 'auto'}])
        """
        pass
