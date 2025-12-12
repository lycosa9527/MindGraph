"""
Bridge Map Thinking Mode Agent (ReAct Pattern)
===============================================

Guides K12 teachers through analogical thinking for Bridge Maps.

Bridge Map Purpose: Identify and apply analogies

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from enum import Enum
from typing import Dict, AsyncGenerator

from agents.thinking_modes.base_thinking_agent import BaseThinkingAgent

logger = logging.getLogger(__name__)


class BridgeMapState(Enum):
    """State machine for Bridge Map thinking workflow"""
    CONTEXT_GATHERING = "CONTEXT_GATHERING"
    ANALOGY_ANALYSIS = "ANALOGY_ANALYSIS"
    REFINEMENT_1 = "REFINEMENT_1"
    REFINEMENT_2 = "REFINEMENT_2"
    FINAL_REFINEMENT = "FINAL_REFINEMENT"
    COMPLETE = "COMPLETE"


class BridgeMapThinkingAgent(BaseThinkingAgent):
    """
    ThinkGuide agent for Bridge Maps.
    
    Bridge Map-specific workflow:
    1. Context Gathering: Understand teaching context
    2. Analogy Analysis: Analyze analogical relationships
    3. Refinement: Improve analogy clarity
    
    Focus: Analogical reasoning and relationship patterns
    """
    
    def __init__(self):
        """Initialize Bridge Map agent"""
        super().__init__(diagram_type='bridge_map')
    
    async def _detect_user_intent(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> Dict:
        """Detect user intent for Bridge Map operations"""
        if not message:
            return {'action': 'discuss'}
        
        language = session.get('language', 'en')
        
        if language == 'zh':
            system_prompt = """你是意图识别专家。分析用户想对桥型图做什么操作。

返回JSON：
{
  "action": "change_relationship" | "update_analogy" | "delete_analogy" | "add_analogies" | "open_node_palette" | "discuss",
  "target": "目标文本",
  "side": "left" | "right"
}"""
        else:
            system_prompt = """You are an intent recognition expert for Bridge Maps.

Return JSON:
{
  "action": "change_relationship" | "update_analogy" | "delete_analogy" | "add_analogies" | "open_node_palette" | "discuss",
  "target": "target text",
  "side": "left" | "right"
}"""
        
        user_prompt = f"User message: {message}"
        
        try:
            result = await self._call_llm(system_prompt, user_prompt, session)
            intent = json.loads(result)
            return intent
        except Exception as e:
            logger.error(f"Intent detection failed: {e}")
            return {'action': 'discuss'}
    
    async def _generate_greeting(self, session: Dict) -> AsyncGenerator[Dict, None]:
        """Generate initial greeting for Bridge Map"""
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        dimension = diagram_data.get('dimension', '')
        analogies = diagram_data.get('analogies', [])
        analogy_count = len(analogies)
        
        if language == 'zh':
            if dimension:
                greeting = f"""👋 你好！我是 ThinkGuide，帮助你优化【桥型图】的类比思维。

我看到你正在探索【{dimension}】的类比关系，目前有 **{analogy_count} 组类比**。

桥型图的核心是：**类比推理**
- 识别相似的关系模式
- 建立对应关系
- 理解深层结构相似性

让我们一起完善你的类比分析！请告诉我：
1. 这是什么教学情境？（年级、学科）
2. 在【{dimension}】这个关系维度上，还有哪些相似的类比？"""
            else:
                greeting = """👋 你好！我是 ThinkGuide，帮助你优化【桥型图】的类比思维。

桥型图的核心是：**类比推理**
- 识别相似的关系模式
- 建立对应关系
- 理解深层结构相似性

让我们一起完善你的类比分析！请告诉我：
1. 这是什么教学情境？
2. 你要建立什么类比关系？"""
        else:
            if dimension:
                greeting = f"""👋 Hello! I'm ThinkGuide, here to help you refine your 【Bridge Map】analogical thinking.

I see you're exploring analogical relationships for 【{dimension}】with **{analogy_count} analogies**.

Bridge Maps focus on: **Analogical Reasoning**
- Identify similar relationship patterns
- Establish corresponding relationships
- Understand deep structural similarities

Let's refine your analogy analysis! Please tell me:
1. What is your teaching context? (grade level, subject)
2. What other similar analogies can we find for the 【{dimension}】relationship?"""
            else:
                greeting = """👋 Hello! I'm ThinkGuide, here to help you refine your 【Bridge Map】analogical thinking.

Bridge Maps focus on: **Analogical Reasoning**
- Identify similar relationship patterns
- Establish corresponding relationships
- Understand deep structural similarities

Let's refine your analogy analysis! Please tell me:
1. What is your teaching context?
2. What analogical relationship are you establishing?"""
        
        yield {'event': 'message_chunk', 'content': greeting}
        yield {'event': 'message_complete', 'new_state': 'CONTEXT_GATHERING'}
    
    async def _handle_discussion(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """Handle pure discussion for Bridge Map (overrides base implementation)."""
        diagram_data = session.get('diagram_data', {})
        dimension = diagram_data.get('dimension', 'this relationship')
        analogies = diagram_data.get('analogies', [])
        context = session.get('context', {})
        language = session.get('language', 'en')
        
        # Extract first analogy pair as main topic example
        first_analogy = ""
        if analogies and len(analogies) > 0:
            first = analogies[0]
            left = first.get('left', '')
            right = first.get('right', '')
            if left and right:
                first_analogy = f"{left} | {right}"
        
        if language == 'zh':
            # Build relationship description with both dimension and first analogy
            relationship_desc = f"「{dimension}」关系"
            if first_analogy:
                relationship_desc += f"（例如：{first_analogy}）"
            
            discussion_prompt = f"""教师正在讨论桥型图：{relationship_desc}。

当前状态：{current_state}
类比数：{len(analogies)}
教学背景：{context.get('raw_message', '未指定')}

教师说：{message}

请作为思维教练回应：
1. 承认他们的想法
2. 提出1-2个深入的苏格拉底式问题
3. 鼓励进一步思考

保持简洁、专业、无表情符号。"""
        else:
            # Build relationship description with both dimension and first analogy
            relationship_desc = f'"{dimension}" relationship'
            if first_analogy:
                relationship_desc += f' (e.g., {first_analogy})'
            
            discussion_prompt = f"""Teacher is discussing a Bridge Map about {relationship_desc}.

Current state: {current_state}
Analogies: {len(analogies)}
Educational context: {context.get('raw_message', 'Not specified')}

Teacher said: {message}

Respond as a thinking coach:
1. Acknowledge their thoughts
2. Ask 1-2 deeper Socratic questions
3. Encourage further thinking

Keep it concise, professional, no emojis."""
        
        async for event in self._stream_llm_response(discussion_prompt, session):
            yield event
    
    async def _handle_action(
        self,
        session: Dict,
        intent: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """Handle Bridge Map-specific actions"""
        action = intent.get('action')
        
        if action == 'open_node_palette':
            async for event in self._handle_open_node_palette(session):
                yield event
        else:
            async for event in self._handle_discussion(session, message, current_state):
                yield event
    
    async def _handle_open_node_palette(self, session: Dict) -> AsyncGenerator[Dict, None]:
        """Handle opening Node Palette for Bridge Map"""
        diagram_data = session['diagram_data']
        language = session.get('language', 'en')
        # Bridge Map: main topic is in "dimension" field (the relationship being explored)
        center_topic = diagram_data.get('dimension', 'Unknown Relationship')
        current_node_count = len(diagram_data.get('analogies', []))
        
        # Acknowledge request
        if language == 'zh':
            ack_prompt = f"用户想要打开节点选择板，为「{center_topic}」关系头脑风暴更多类比对。目前有{current_node_count}个类比。用1-2句话说你将使用多个AI模型生成创意类比想法。"
        else:
            ack_prompt = f"User wants to open Node Palette to brainstorm more analogies for \"{center_topic}\" relationship. Currently {current_node_count} analogies. Say in 1-2 sentences you'll generate creative analogy ideas using multiple AI models."
        
        async for chunk in self._stream_llm_response(ack_prompt, session):
            yield chunk
        
        # Extract educational context
        context = session.get('context', {})
        educational_context = {
            'grade_level': context.get('grade_level', '5th grade'),
            'subject': context.get('subject', 'General'),
            'objective': context.get('objective', ''),
            'raw_message': context.get('raw_message', ''),
            'language': language  # Pass UI language to Node Palette
        }
        
        # Yield action event
        yield {
            'event': 'action',
            'action': 'open_node_palette',
            'data': {
                'center_topic': center_topic,
                'current_node_count': current_node_count,
                'diagram_data': diagram_data,
                'session_id': session['session_id'],
                'educational_context': educational_context
            }
        }
    
    def _get_state_prompt(
        self,
        session: Dict,
        message: str = None,
        intent: Dict = None
    ) -> str:
        """
        Get Bridge Map-specific prompt for current state.
        
        Focuses on analogical reasoning.
        """
        current_state = session.get('state', 'CONTEXT_GATHERING')
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        
        dimension = diagram_data.get('dimension', '')
        analogies = diagram_data.get('analogies', [])
        analogy_count = len(analogies)
        
        # Extract first analogy pair as main topic example
        first_analogy = ""
        if analogies and len(analogies) > 0:
            first = analogies[0]
            left = first.get('left', '')
            right = first.get('right', '')
            if left and right:
                first_analogy = f"{left} | {right}"
        
        if current_state == 'CONTEXT_GATHERING':
            if language == 'zh':
                # Build relationship description with both dimension and first analogy
                relationship_desc = f"「{dimension}」关系"
                if first_analogy:
                    relationship_desc += f"（例如：{first_analogy}）"
                
                return f"""你好！我来帮你优化{relationship_desc}的桥型图。

桥型图用于类比推理，通过相似的关系帮助理解新概念。

请简单说说：
- 你的教学背景（年级、学科）
- 你想让学生理解哪些类比关系来掌握{dimension}？
- 或者直接告诉我你想怎么调整这个图

目前有{analogy_count}组类比。"""
            else:
                # Build relationship description with both dimension and first analogy
                relationship_desc = f'"{dimension}" relationship'
                if first_analogy:
                    relationship_desc += f' (e.g., {first_analogy})'
                
                return f"""Hi! I'll help you refine your Bridge Map on {relationship_desc}.

Bridge Maps use analogical reasoning, helping understand new concepts through similar relationships.

Please briefly share:
- Your teaching context (grade level, subject)
- What analogies should students understand to grasp {dimension}?
- Or tell me directly how you'd like to adjust the diagram

Currently {analogy_count} analogies."""
        
        # Add more states as needed
        return self._get_default_prompt(session, message)
    
    async def _generate_suggested_nodes(self, session: Dict) -> list:
        """Generate suggested nodes for Bridge Map"""
        return []

