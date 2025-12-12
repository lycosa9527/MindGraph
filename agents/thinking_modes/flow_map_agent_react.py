"""
Flow Map Thinking Mode Agent (ReAct Pattern)
=============================================

Guides K12 teachers through sequential thinking for Flow Maps.

Flow Map Purpose: Analyze processes and sequential steps

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from enum import Enum
from typing import Dict, AsyncGenerator

from agents.thinking_modes.base_thinking_agent import BaseThinkingAgent

logger = logging.getLogger(__name__)


class FlowMapState(Enum):
    """State machine for Flow Map thinking workflow"""
    CONTEXT_GATHERING = "CONTEXT_GATHERING"
    SEQUENCE_ANALYSIS = "SEQUENCE_ANALYSIS"
    REFINEMENT_1 = "REFINEMENT_1"
    REFINEMENT_2 = "REFINEMENT_2"
    FINAL_REFINEMENT = "FINAL_REFINEMENT"
    COMPLETE = "COMPLETE"


class FlowMapThinkingAgent(BaseThinkingAgent):
    """
    ThinkGuide agent for Flow Maps.
    
    Flow Map-specific workflow:
    1. Context Gathering: Understand teaching context
    2. Sequence Analysis: Analyze process flow
    3. Refinement: Improve logical sequence
    
    Focus: Sequential thinking and process analysis
    """
    
    def __init__(self):
        """Initialize Flow Map agent"""
        super().__init__(diagram_type='flow_map')
    
    async def _detect_user_intent(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> Dict:
        """Detect user intent for Flow Map operations"""
        if not message:
            return {'action': 'discuss'}
        
        language = session.get('language', 'en')
        
        if language == 'zh':
            system_prompt = """你是意图识别专家。分析用户想对流程图做什么操作。

返回JSON：
{
  "action": "change_event" | "update_step" | "delete_step" | "add_steps" | "reorder_steps" | "open_node_palette" | "discuss",
  "target": "目标文本",
  "step_index": 步骤序号
}"""
        else:
            system_prompt = """You are an intent recognition expert for Flow Maps.

Return JSON:
{
  "action": "change_event" | "update_step" | "delete_step" | "add_steps" | "reorder_steps" | "open_node_palette" | "discuss",
  "target": "target text",
  "step_index": step number
}"""
        
        user_prompt = f"User message: {message}"
        
        try:
            # Get user context from session for token tracking
            user_id = session.get('user_id')
            organization_id = session.get('organization_id')
            
            result_text = await self.llm.chat(
                prompt=user_prompt,
                model=self.model,
                system_message=system_prompt,
                temperature=0.1,
                max_tokens=500,
                user_id=int(user_id) if user_id and str(user_id).isdigit() else None,
                organization_id=organization_id,
                request_type='thinkguide',
                endpoint_path='/thinking_mode/stream',
                conversation_id=session.get('session_id'),
                diagram_type=self.diagram_type
            )
            
            # Extract JSON from response
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
            
            intent = json.loads(result_text)
            logger.debug(f"[FlowMapThinkingAgent] Detected intent: {intent}")
            return intent
        except Exception as e:
            logger.error(f"[FlowMapThinkingAgent] Intent detection failed: {e}")
            return {'action': 'discuss'}
    
    async def _generate_greeting(self, session: Dict) -> AsyncGenerator[Dict, None]:
        """Generate initial greeting for Flow Map"""
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        title = diagram_data.get('title', '')
        steps = diagram_data.get('steps', [])
        step_count = len(steps)
        
        if language == 'zh':
            if title:
                greeting = f"""👋 你好！我是 ThinkGuide，帮助你优化【流程图】的顺序思维。

我看到你正在分析【{title}】的过程，目前有 **{step_count} 个步骤**。

流程图的核心是：**顺序和过程**
- 清晰的步骤顺序
- 合理的因果关系
- 完整的过程展现

让我们一起完善你的流程分析！请告诉我：
1. 这是什么教学情境？（年级、学科）
2.【{title}】的步骤顺序是否合理？还缺少哪些关键步骤？"""
            else:
                greeting = """👋 你好！我是 ThinkGuide，帮助你优化【流程图】的顺序思维。

流程图的核心是：**顺序和过程**
- 清晰的步骤顺序
- 合理的因果关系
- 完整的过程展现

让我们一起完善你的流程分析！请告诉我：
1. 这是什么教学情境？
2. 你要分析的过程是什么？"""
        else:
            if title:
                greeting = f"""👋 Hello! I'm ThinkGuide, here to help you refine your 【Flow Map】sequential thinking.

I see you're analyzing the process of 【{title}】with **{step_count} steps**.

Flow Maps focus on: **Sequence and Process**
- Clear step order
- Logical cause-effect relationships
- Complete process representation

Let's refine your process analysis! Please tell me:
1. What is your teaching context? (grade level, subject)
2. Is the sequence of steps in 【{title}】logical? Are there any missing key steps?"""
            else:
                greeting = """👋 Hello! I'm ThinkGuide, here to help you refine your 【Flow Map】sequential thinking.

Flow Maps focus on: **Sequence and Process**
- Clear step order
- Logical cause-effect relationships
- Complete process representation

Let's refine your process analysis! Please tell me:
1. What is your teaching context?
2. What process are you analyzing?"""
        
        yield {'event': 'message_chunk', 'content': greeting}
        yield {'event': 'message_complete', 'new_state': 'CONTEXT_GATHERING'}
    
    async def _handle_discussion(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """Handle pure discussion for Flow Map (overrides base implementation)."""
        diagram_data = session.get('diagram_data', {})
        title = diagram_data.get('title', 'this process')
        steps = diagram_data.get('steps', [])
        context = session.get('context', {})
        language = session.get('language', 'en')
        
        if language == 'zh':
            discussion_prompt = f"""教师正在讨论流程图：「{title}」。

当前状态：{current_state}
步骤数：{len(steps)}
教学背景：{context.get('raw_message', '未指定')}

教师说：{message}

请作为思维教练回应：
1. 承认他们的想法
2. 提出1-2个深入的苏格拉底式问题
3. 鼓励进一步思考

保持简洁、专业、无表情符号。"""
        else:
            discussion_prompt = f"""Teacher is discussing a Flow Map about "{title}".

Current state: {current_state}
Steps: {len(steps)}
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
        """Handle Flow Map-specific actions"""
        action = intent.get('action')
        
        if action == 'open_node_palette':
            async for event in self._handle_open_node_palette(session):
                yield event
        else:
            async for event in self._handle_discussion(session, message, current_state):
                yield event
    
    async def _handle_open_node_palette(self, session: Dict) -> AsyncGenerator[Dict, None]:
        """Handle opening Node Palette for Flow Map with step ordering guidance"""
        diagram_data = session['diagram_data']
        language = session.get('language', 'en')
        # Flow Map: main topic is in "title" field
        center_topic = diagram_data.get('title', 'Unknown Event')
        steps = diagram_data.get('steps', [])
        step_count = len(steps)
        
        # Acknowledge request with step ordering emphasis
        if language == 'zh':
            ack_prompt = f"好的！节点调色板即将打开。\n\n让我们为流程「{center_topic}」生成更多步骤。目前有{step_count}个步骤。\n\n**重要提示**：流程图的步骤需要按照时间顺序排列。系统将生成有序的步骤，每个步骤都会显示序号。你可以查看序号来确保步骤的逻辑顺序。\n\n系统将使用4个AI模型同时生成创意步骤想法。"
        else:
            ack_prompt = f"Okay! Opening Node Palette.\n\nLet's generate more steps for process \"{center_topic}\". Currently {step_count} steps.\n\n**Important**: Flow map steps need to be in chronological order. The system will generate ordered steps, and each step will display a sequence number. You can review the sequence numbers to ensure logical ordering.\n\nThe system will use 4 AI models simultaneously to generate creative step ideas."
        
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
        
        # Yield action event with stage info
        yield {
            'event': 'action',
            'action': 'open_node_palette',
            'data': {
                'center_topic': center_topic,
                'current_node_count': step_count,
                'diagram_data': diagram_data,
                'session_id': session['session_id'],
                'educational_context': educational_context,
                # Add stage info (always 'steps' for flow map)
                'stage': 'steps',
                'stage_data': {}
            }
        }
    
    def _get_state_prompt(
        self,
        session: Dict,
        message: str = None,
        intent: Dict = None
    ) -> str:
        """
        Get Flow Map-specific prompt for current state.
        
        Focuses on sequential processes and steps.
        """
        current_state = session.get('state', 'CONTEXT_GATHERING')
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        
        title = diagram_data.get('title', '')
        steps = diagram_data.get('steps', [])
        step_count = len(steps)
        
        if current_state == 'CONTEXT_GATHERING':
            if language == 'zh':
                return f"""你好！我来帮你优化"{title}"的流程图。

流程图用于展示事件的顺序和步骤，帮助理解过程的先后关系。

请简单说说：
- 你的教学背景（年级、学科）
- 你想让学生理解{title}过程的哪些关键步骤？
- 或者直接告诉我你想怎么调整这个图

目前有{step_count}个步骤。"""
            else:
                return f"""Hi! I'll help you refine your Flow Map on "{title}".

Flow Maps show the sequence of events and steps, helping understand the order of a process.

Please briefly share:
- Your teaching context (grade level, subject)
- What key steps of the {title} process should students understand?
- Or tell me directly how you'd like to adjust the diagram

Currently {step_count} steps."""
        
        # Add more states as needed
        return self._get_default_prompt(session, message)
    
    async def _generate_suggested_nodes(self, session: Dict) -> list:
        """Generate suggested nodes for Flow Map"""
        return []

