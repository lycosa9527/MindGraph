"""
Multi Flow Map Thinking Mode Agent (ReAct Pattern)
===================================================

Guides K12 teachers through cause-effect thinking for Multi Flow Maps.

Multi Flow Map Purpose: Analyze causes and effects of an event

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from enum import Enum
from typing import Dict, AsyncGenerator

from agents.thinking_modes.base_thinking_agent import BaseThinkingAgent

logger = logging.getLogger(__name__)


class MultiFlowMapState(Enum):
    """State machine for Multi Flow Map thinking workflow"""
    CONTEXT_GATHERING = "CONTEXT_GATHERING"
    CAUSE_EFFECT_ANALYSIS = "CAUSE_EFFECT_ANALYSIS"
    REFINEMENT_1 = "REFINEMENT_1"
    REFINEMENT_2 = "REFINEMENT_2"
    FINAL_REFINEMENT = "FINAL_REFINEMENT"
    COMPLETE = "COMPLETE"


class MultiFlowMapThinkingAgent(BaseThinkingAgent):
    """
    ThinkGuide agent for Multi Flow Maps.
    
    Multi Flow Map-specific workflow:
    1. Context Gathering: Understand teaching context
    2. Cause-Effect Analysis: Analyze causes and effects
    3. Refinement: Improve cause-effect relationships
    
    Focus: Cause-effect reasoning and analysis
    """
    
    def __init__(self):
        """Initialize Multi Flow Map agent"""
        super().__init__(diagram_type='multi_flow_map')
    
    async def _detect_user_intent(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> Dict:
        """Detect user intent for Multi Flow Map operations"""
        if not message:
            return {'action': 'discuss'}
        
        language = session.get('language', 'en')
        
        if language == 'zh':
            system_prompt = """你是意图识别专家。分析用户想对复流程图做什么操作。

返回JSON：
{
  "action": "change_event" | "update_cause" | "update_effect" | "delete_node" | "add_causes" | "add_effects" | "open_node_palette" | "discuss",
  "target": "目标文本",
  "node_type": "cause" | "effect"
}"""
        else:
            system_prompt = """You are an intent recognition expert for Multi Flow Maps.

Return JSON:
{
  "action": "change_event" | "update_cause" | "update_effect" | "delete_node" | "add_causes" | "add_effects" | "open_node_palette" | "discuss",
  "target": "target text",
  "node_type": "cause" | "effect"
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
        """Generate initial greeting for Multi Flow Map"""
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        event = diagram_data.get('event', '')
        causes = diagram_data.get('causes', [])
        effects = diagram_data.get('effects', [])
        cause_count = len(causes)
        effect_count = len(effects)
        
        if language == 'zh':
            if event:
                greeting = f"""👋 你好！我是 ThinkGuide，帮助你优化【复流程图】的因果思维。

我看到你正在分析【{event}】这个事件，目前有 **{cause_count} 个原因** 和 **{effect_count} 个结果**。

复流程图的核心是：**因果关系**
- 分析事件的多个原因
- 探讨事件的多种结果
- 理解复杂的因果网络

让我们一起完善你的因果分析！请告诉我：
1. 这是什么教学情境？（年级、学科）
2.【{event}】还有哪些重要的原因和结果需要考虑？"""
            else:
                greeting = """👋 你好！我是 ThinkGuide，帮助你优化【复流程图】的因果思维。

复流程图的核心是：**因果关系**
- 分析事件的多个原因
- 探讨事件的多种结果
- 理解复杂的因果网络

让我们一起完善你的因果分析！请告诉我：
1. 这是什么教学情境？
2. 你要分析的事件是什么？"""
        else:
            if event:
                greeting = f"""👋 Hello! I'm ThinkGuide, here to help you refine your 【Multi Flow Map】cause-effect thinking.

I see you're analyzing the event 【{event}】with **{cause_count} causes** and **{effect_count} effects**.

Multi Flow Maps focus on: **Cause and Effect**
- Analyze multiple causes of an event
- Explore various effects of an event
- Understand complex causal networks

Let's refine your cause-effect analysis! Please tell me:
1. What is your teaching context? (grade level, subject)
2. What other important causes and effects of 【{event}】should we consider?"""
            else:
                greeting = """👋 Hello! I'm ThinkGuide, here to help you refine your 【Multi Flow Map】cause-effect thinking.

Multi Flow Maps focus on: **Cause and Effect**
- Analyze multiple causes of an event
- Explore various effects of an event
- Understand complex causal networks

Let's refine your cause-effect analysis! Please tell me:
1. What is your teaching context?
2. What event are you analyzing?"""
        
        yield {'event': 'message_chunk', 'content': greeting}
        yield {'event': 'message_complete', 'new_state': 'CONTEXT_GATHERING'}
    
    async def _generate_response(
        self,
        session: Dict,
        message: str,
        intent: Dict
    ) -> AsyncGenerator[Dict, None]:
        """Generate Socratic response for Multi Flow Map"""
        language = session.get('language', 'en')
        current_state = session.get('current_state', 'CONTEXT_GATHERING')
        
        if language == 'zh':
            system_prompt = f"""你是一位苏格拉底式的K12教育助手，专注于复流程图的因果思维训练。

当前阶段：{current_state}

复流程图教学要点：
1. 引导学生区分直接原因和间接原因
2. 分析短期影响和长期影响
3. 探讨因果关系的复杂性
4. 适合的数量：3-5个原因，3-5个结果

请用温和、启发式的方式引导教师。"""
        else:
            system_prompt = f"""You are a Socratic K12 education assistant focused on Multi Flow Map cause-effect thinking.

Current stage: {current_state}

Multi Flow Map teaching points:
1. Guide students to distinguish direct and indirect causes
2. Analyze short-term and long-term effects
3. Explore complexity of causal relationships
4. Appropriate number: 3-5 causes, 3-5 effects

Guide teachers gently using Socratic questions."""
        
        user_prompt = f"User intent: {intent}\nMessage: {message}"
        
        async for chunk in self._stream_llm_response(system_prompt, user_prompt, session):
            yield chunk
    
    async def _handle_discussion(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """Handle pure discussion for Multi Flow Map (overrides base implementation)."""
        diagram_data = session.get('diagram_data', {})
        event = diagram_data.get('event', 'this event')
        causes = diagram_data.get('causes', [])
        effects = diagram_data.get('effects', [])
        context = session.get('context', {})
        language = session.get('language', 'en')
        
        if language == 'zh':
            discussion_prompt = f"""教师正在讨论复流程图：「{event}」。

当前状态：{current_state}
原因数：{len(causes)}
结果数：{len(effects)}
教学背景：{context.get('raw_message', '未指定')}

教师说：{message}

请作为思维教练回应：
1. 承认他们的想法
2. 提出1-2个深入的苏格拉底式问题
3. 鼓励进一步思考

保持简洁、专业、无表情符号。"""
        else:
            discussion_prompt = f"""Teacher is discussing a Multi Flow Map about "{event}".

Current state: {current_state}
Causes: {len(causes)}
Effects: {len(effects)}
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
        """Handle Multi Flow Map-specific actions"""
        action = intent.get('action')
        
        if action == 'open_node_palette':
            async for event in self._handle_open_node_palette(session):
                yield event
        else:
            async for event in self._handle_discussion(session, message, current_state):
                yield event
    
    async def _handle_open_node_palette(self, session: Dict) -> AsyncGenerator[Dict, None]:
        """Handle opening Node Palette for Multi Flow Map"""
        diagram_data = session['diagram_data']
        language = session.get('language', 'en')
        # Multi Flow Map: main topic is in "event" field
        center_topic = diagram_data.get('event', 'Unknown Event')
        current_causes = len(diagram_data.get('causes', []))
        current_effects = len(diagram_data.get('effects', []))
        
        # Acknowledge request
        if language == 'zh':
            ack_prompt = f"用户想要打开节点选择板，为「{center_topic}」头脑风暴更多原因和结果。目前有{current_causes}个原因和{current_effects}个结果。用1-2句话说你将使用多个AI模型生成创意因果想法。"
        else:
            ack_prompt = f"User wants to open Node Palette to brainstorm more causes and effects for \"{center_topic}\". Currently {current_causes} causes and {current_effects} effects. Say in 1-2 sentences you'll generate creative cause-effect ideas using multiple AI models."
        
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
                'current_node_count': current_causes + current_effects,
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
        Get Multi Flow Map-specific prompt for current state.
        
        Focuses on cause-effect relationships.
        """
        current_state = session.get('state', 'CONTEXT_GATHERING')
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        
        event = diagram_data.get('event', '')
        causes = diagram_data.get('causes', [])
        effects = diagram_data.get('effects', [])
        cause_count = len(causes)
        effect_count = len(effects)
        
        if current_state == 'CONTEXT_GATHERING':
            if language == 'zh':
                return f"""你好！我来帮你优化"{event}"的复流程图。

复流程图用于分析事件的因果关系，展示多个原因和多个结果。

请简单说说：
- 你的教学背景（年级、学科）
- 你想让学生理解{event}的哪些因果关系？
- 或者直接告诉我你想怎么调整这个图

目前有{cause_count}个原因，{effect_count}个结果。"""
            else:
                return f"""Hi! I'll help you refine your Multi Flow Map on "{event}".

Multi Flow Maps analyze cause-effect relationships, showing multiple causes and effects.

Please briefly share:
- Your teaching context (grade level, subject)
- What cause-effect relationships of {event} should students understand?
- Or tell me directly how you'd like to adjust the diagram

Currently {cause_count} causes and {effect_count} effects."""
        
        # Add more states as needed
        return self._get_default_prompt(session, message)
    
    async def _generate_suggested_nodes(self, session: Dict) -> list:
        """Generate suggested nodes for Multi Flow Map"""
        return []

