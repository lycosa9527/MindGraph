"""
Brace Map Thinking Mode Agent (ReAct Pattern)
==============================================

Guides K12 teachers through part-whole thinking for Brace Maps.

Brace Map Purpose: Analyze whole-to-part relationships

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from enum import Enum
from typing import Dict, AsyncGenerator

from agents.thinking_modes.base_thinking_agent import BaseThinkingAgent

logger = logging.getLogger(__name__)


class BraceMapState(Enum):
    """State machine for Brace Map thinking workflow"""
    CONTEXT_GATHERING = "CONTEXT_GATHERING"
    PART_ANALYSIS = "PART_ANALYSIS"
    REFINEMENT_1 = "REFINEMENT_1"
    REFINEMENT_2 = "REFINEMENT_2"
    FINAL_REFINEMENT = "FINAL_REFINEMENT"
    COMPLETE = "COMPLETE"


class BraceMapThinkingAgent(BaseThinkingAgent):
    """
    ThinkGuide agent for Brace Maps.
    
    Brace Map-specific workflow:
    1. Context Gathering: Understand teaching context
    2. Part Analysis: Analyze component parts
    3. Refinement: Improve part-whole breakdown
    
    Focus: Part-whole relationships and physical structure
    """
    
    def __init__(self):
        """Initialize Brace Map agent"""
        super().__init__(diagram_type='brace_map')
    
    async def _detect_user_intent(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> Dict:
        """Detect user intent for Brace Map operations"""
        if not message:
            return {'action': 'discuss'}
        
        language = session.get('language', 'en')
        
        if language == 'zh':
            system_prompt = """你是意图识别专家。分析用户想对括弧图做什么操作。

返回JSON：
{
  "action": "change_whole" | "update_part" | "delete_part" | "add_parts" | "add_subparts" | "open_node_palette" | "discuss",
  "target": "目标文本",
  "level": 层级（1=主要部分，2=次级部分）
}"""
        else:
            system_prompt = """You are an intent recognition expert for Brace Maps.

Return JSON:
{
  "action": "change_whole" | "update_part" | "delete_part" | "add_parts" | "add_subparts" | "open_node_palette" | "discuss",
  "target": "target text",
  "level": level (1=main parts, 2=sub-parts)
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
            logger.debug(f"[BraceMapThinkingAgent] Detected intent: {intent}")
            return intent
        except Exception as e:
            logger.error(f"[BraceMapThinkingAgent] Intent detection failed: {e}")
            return {'action': 'discuss'}
    
    async def _generate_greeting(self, session: Dict) -> AsyncGenerator[Dict, None]:
        """Generate initial greeting for Brace Map"""
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        whole = diagram_data.get('whole', '')
        parts = diagram_data.get('parts', [])
        part_count = len(parts)
        
        if language == 'zh':
            if whole:
                greeting = f"""👋 你好！我是 ThinkGuide，帮助你优化【括弧图】的整体-部分思维。

我看到你正在分析【{whole}】的结构，目前有 **{part_count} 个主要部分**。

括弧图的核心是：**整体与部分**
- 将整体分解为主要部分
- 分析每个部分的组成
- 理解物理结构关系

让我们一起完善你的结构分析！请告诉我：
1. 这是什么教学情境？（年级、学科）
2.【{whole}】还有哪些重要部分需要分析？"""
            else:
                greeting = """👋 你好！我是 ThinkGuide，帮助你优化【括弧图】的整体-部分思维。

括弧图的核心是：**整体与部分**
- 将整体分解为主要部分
- 分析每个部分的组成
- 理解物理结构关系

让我们一起完善你的结构分析！请告诉我：
1. 这是什么教学情境？
2. 你要分析的整体是什么？"""
        else:
            if whole:
                greeting = f"""👋 Hello! I'm ThinkGuide, here to help you refine your 【Brace Map】part-whole thinking.

I see you're analyzing the structure of 【{whole}】with **{part_count} main parts**.

Brace Maps focus on: **Whole and Parts**
- Break down whole into major parts
- Analyze components of each part
- Understand physical structure relationships

Let's refine your structure analysis! Please tell me:
1. What is your teaching context? (grade level, subject)
2. What other important parts of 【{whole}】should we analyze?"""
            else:
                greeting = """👋 Hello! I'm ThinkGuide, here to help you refine your 【Brace Map】part-whole thinking.

Brace Maps focus on: **Whole and Parts**
- Break down whole into major parts
- Analyze components of each part
- Understand physical structure relationships

Let's refine your structure analysis! Please tell me:
1. What is your teaching context?
2. What whole are you analyzing?"""
        
        yield {'event': 'message_chunk', 'content': greeting}
        yield {'event': 'message_complete', 'new_state': 'CONTEXT_GATHERING'}
    
    async def _handle_discussion(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """Handle pure discussion for Brace Map (overrides base implementation)."""
        diagram_data = session.get('diagram_data', {})
        whole = diagram_data.get('whole', 'this whole')
        parts = diagram_data.get('parts', [])
        context = session.get('context', {})
        language = session.get('language', 'en')
        
        if language == 'zh':
            discussion_prompt = f"""教师正在讨论括号图：「{whole}」。

当前状态：{current_state}
部分数：{len(parts)}
教学背景：{context.get('raw_message', '未指定')}

教师说：{message}

请作为思维教练回应：
1. 承认他们的想法
2. 提出1-2个深入的苏格拉底式问题
3. 鼓励进一步思考

保持简洁、专业、无表情符号。"""
        else:
            discussion_prompt = f"""Teacher is discussing a Brace Map about "{whole}".

Current state: {current_state}
Parts: {len(parts)}
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
        """Handle Brace Map-specific actions"""
        action = intent.get('action')
        
        if action == 'open_node_palette':
            async for event in self._handle_open_node_palette(session):
                yield event
        else:
            async for event in self._handle_discussion(session, message, current_state):
                yield event
    
    async def _handle_open_node_palette(self, session: Dict) -> AsyncGenerator[Dict, None]:
        """Handle opening Node Palette for Brace Map with stage awareness"""
        diagram_data = session['diagram_data']
        language = session.get('language', 'en')
        # Brace Map: main topic is in "whole" field
        center_topic = diagram_data.get('whole', 'Unknown Whole')
        parts = diagram_data.get('parts', [])
        
        # Detect current stage
        has_parts = len(parts) > 0
        # Support both 'text' and 'name' fields for parts
        real_parts = [p for p in parts if (p.get('text') or p.get('name', '')).strip()]
        has_real_parts = len(real_parts) > 0
        
        if not has_real_parts:
            # Stage 1: Main Parts Generation
            if language == 'zh':
                ack_prompt = f"好的！节点调色板即将打开。\n\n让我们为整体「{center_topic}」生成主要组成部分。请选择你想要的部分，然后点击\"完成\"添加到图中。\n\n系统将使用4个AI模型同时生成创意想法。"
            else:
                ack_prompt = f"Okay! Opening Node Palette.\n\nLet's generate main parts for \"{center_topic}\". Select the parts you want, then click \"Finish\" to add them to the diagram.\n\nThe system will use 4 AI models simultaneously to generate creative ideas."
        else:
            # Stage 2: Sub-Parts Generation
            part_count = len(real_parts)
            # Extract part names (support both 'text' and 'name' fields)
            part_names = [p.get('text') or p.get('name', '') for p in real_parts]
            
            if language == 'zh':
                ack_prompt = f"好的！节点调色板即将打开。\n\n你已经有{part_count}个主要部分。现在让我们为每个部分生成更细致的子部件。\n\n系统将为每个部分创建独立的标签页：\n"
                ack_prompt += "\n".join(f"- {name}" for name in part_names)
                ack_prompt += f"\n\n点击标签页切换，为每个部分选择子部件。完成后点击\"完成\"。"
            else:
                ack_prompt = f"Okay! Opening Node Palette.\n\nYou already have {part_count} main parts. Now let's generate finer sub-components for each part.\n\nThe system will create separate tabs for each part:\n"
                ack_prompt += "\n".join(f"- {name}" for name in part_names)
                ack_prompt += f"\n\nSwitch between tabs to select sub-components for each part. Click \"Finish\" when done."
        
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
                'current_node_count': len(parts),
                'diagram_data': diagram_data,
                'session_id': session['session_id'],
                'educational_context': educational_context,
                # Add stage info for multi-stage workflow
                'stage': 'subparts' if has_real_parts else 'parts',
                'stage_data': {'parts': part_names} if has_real_parts else {}
            }
        }
    
    def _get_state_prompt(
        self,
        session: Dict,
        message: str = None,
        intent: Dict = None
    ) -> str:
        """
        Get Brace Map-specific prompt for current state.
        
        Focuses on part-whole relationships.
        """
        current_state = session.get('state', 'CONTEXT_GATHERING')
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        
        whole = diagram_data.get('whole', '')
        parts = diagram_data.get('parts', [])
        part_count = len(parts)
        
        if current_state == 'CONTEXT_GATHERING':
            if language == 'zh':
                return f"""你好！我来帮你优化"{whole}"的括号图。

括号图用于展示整体与部分的关系，帮助理解事物的组成结构。

请简单说说：
- 你的教学背景（年级、学科）
- 你想让学生理解{whole}由哪些主要部分组成？
- 或者直接告诉我你想怎么调整这个图

目前有{part_count}个部分。"""
            else:
                return f"""Hi! I'll help you refine your Brace Map on "{whole}".

Brace Maps show part-whole relationships, helping understand the structure and components of something.

Please briefly share:
- Your teaching context (grade level, subject)
- What main parts of {whole} should students understand?
- Or tell me directly how you'd like to adjust the diagram

Currently {part_count} parts."""
        
        # Add more states as needed
        return self._get_default_prompt(session, message)
    
    async def _generate_suggested_nodes(self, session: Dict) -> list:
        """Generate suggested nodes for Brace Map"""
        return []

