"""
Voice Intent Service
Classifies user voice intent using Qwen Turbo via LLM Middleware

@author lycosa9527
@made_by MindSpring Team
"""

import logging
from typing import Dict, Any, Optional
from services.llm_service import llm_service  # Use LLM Middleware

# Configure logger with module name 'INTENT'
logger = logging.getLogger('INTENT')


class VoiceIntentService:
    """Classify user voice intent using LLM Middleware"""
    
    def __init__(self):
        self.routing_map = {
            'ask_question': 'thinkguide',
            'add_node': 'node_palette',
            'select_node': 'selection',
            'explain_concept': 'thinkguide',
            'help_select_nodes': 'node_palette',
            'general_help': 'thinkguide'
        }
    
    async def classify_intent(
        self,
        user_message: str,
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Classify user intent from voice input.
        Uses LLM Middleware for consistent error handling, rate limiting, and timeout.
        
        Args:
            user_message: Transcribed user speech
            context: Full context (diagram, nodes, history, etc.)
        
        Returns:
            {'intent': str, 'target': str, 'confidence': float}
        """
        try:
            logger.debug(f"Classifying intent for message: {user_message[:50]}...")
            
            prompt = self._build_prompt(user_message, context)
            
            logger.debug("Classifying intent via LLM middleware")
            
            # Use LLMService (middleware) for classification
            # Benefits: rate limiting, error handling, timeout, retry logic
            response = await llm_service.chat(
                prompt=prompt,
                model='qwen',  # Qwen Turbo for intent classification
                temperature=0.1,  # Low temperature for classification
                max_tokens=50,  # Short response
                timeout=5.0  # Quick classification
            )
            
            # Parse response
            intent_data = self._parse_response(response)
            
            logger.info(f"Intent classified: {intent_data['intent']} -> {intent_data['target']} (confidence: {intent_data['confidence']:.2f})")
            return intent_data
        
        except Exception as e:
            logger.error(f"Classification error: {e}", exc_info=True)
            logger.warning("Fallback to general_help intent")
            return {
                'intent': 'general_help',
                'target': 'thinkguide',
                'confidence': 0.5
            }
    
    def _build_prompt(self, user_message: str, context: Dict[str, Any]) -> str:
        """Build classification prompt"""
        return f"""You are a voice intent classifier for an educational diagram editor.

User said: "{user_message}"

Context:
- Active panel: {context.get('active_panel', 'unknown')}
- Diagram type: {context.get('diagram_type', 'unknown')}
- Node palette open: {context.get('node_palette_open', False)}
- Selected nodes: {len(context.get('selected_nodes', []))}
- Recent conversation: {context.get('conversation_history', [])[-3:] if context.get('conversation_history') else []}

Classify the intent:
- ask_question: User asking about concepts/topics
- add_node: User wants to add nodes to diagram
- select_node: User wants to select/highlight specific nodes
- explain_concept: User wants explanation of diagram content
- help_select_nodes: User asks which nodes to use
- general_help: General help request

Respond with ONLY: intent|target|confidence
Example: ask_question|thinkguide|0.95"""
    
    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response"""
        try:
            parts = response.strip().split('|')
            intent = parts[0].strip()
            target = parts[1].strip() if len(parts) > 1 else self.routing_map.get(intent, 'thinkguide')
            confidence = float(parts[2].strip()) if len(parts) > 2 else 0.8
            
            return {
                'intent': intent,
                'target': target,
                'confidence': confidence
            }
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return {
                'intent': 'general_help',
                'target': 'thinkguide',
                'confidence': 0.5
            }

