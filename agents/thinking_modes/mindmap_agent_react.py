"""
Mind Map Thinking Mode Agent (ReAct Pattern)
=============================================

Guides K12 teachers through associative thinking for Mind Maps.

Mind Map Purpose: Explore ideas through free association and branching

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from enum import Enum
from typing import Dict, AsyncGenerator

from agents.thinking_modes.base_thinking_agent import BaseThinkingAgent

logger = logging.getLogger(__name__)


class MindMapState(Enum):
    """State machine for Mind Map thinking workflow"""
    CONTEXT_GATHERING = "CONTEXT_GATHERING"
    BRANCH_ANALYSIS = "BRANCH_ANALYSIS"
    REFINEMENT_1 = "REFINEMENT_1"
    REFINEMENT_2 = "REFINEMENT_2"
    FINAL_REFINEMENT = "FINAL_REFINEMENT"
    COMPLETE = "COMPLETE"


class MindMapThinkingAgent(BaseThinkingAgent):
    """
    ThinkGuide agent for Mind Maps.
    
    Mind Map-specific workflow:
    1. Context Gathering: Understand teaching context
    2. Branch Analysis: Analyze idea branches and connections
    3. Refinement: Improve branch organization
    
    Focus: Associative thinking and idea exploration
    """
    
    def __init__(self):
        """Initialize Mind Map agent"""
        super().__init__(diagram_type='mindmap')
    
    async def _detect_user_intent(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> Dict:
        """Detect user intent for Mind Map operations"""
        if not message:
            return {'action': 'discuss'}
        
        language = session.get('language', 'en')
        
        if language == 'zh':
            system_prompt = """你是意图识别专家。分析用户想对思维导图做什么操作。

返回JSON：
{
  "action": "change_center" | "update_branch" | "delete_branch" | "add_branches" | "add_subbranches" | "open_node_palette" | "discuss",
  "target": "目标文本",
  "branch_path": "分支路径"
}"""
        else:
            system_prompt = """You are an intent recognition expert for Mind Maps.

Return JSON:
{
  "action": "change_center" | "update_branch" | "delete_branch" | "add_branches" | "add_subbranches" | "open_node_palette" | "discuss",
  "target": "target text",
  "branch_path": "branch path"
}"""
        
        user_prompt = f"User message: {message}"
        
        try:
            # Ensure _call_llm method exists (inherited from BaseThinkingAgent)
            if not hasattr(self, '_call_llm'):
                logger.error(f"[MindMapThinkingAgent] _call_llm method not found. Check BaseThinkingAgent inheritance.")
                return {'action': 'discuss'}
            
            result = await self._call_llm(system_prompt, user_prompt, session)
            
            # Try to parse JSON, handle various formats
            if not result or not result.strip():
                logger.warning(f"[MindMapThinkingAgent] Empty response from LLM")
                return {'action': 'discuss'}
            
            # Extract JSON if wrapped in code blocks
            result_text = result.strip()
            if '```json' in result_text:
                result_text = result_text.split('```json')[1].split('```')[0].strip()
            elif '```' in result_text:
                result_text = result_text.split('```')[1].split('```')[0].strip()
            
            intent = json.loads(result_text)
            return intent
        except json.JSONDecodeError as e:
            logger.error(f"[MindMapThinkingAgent] JSON parsing failed: {e}. Response: {result[:200] if 'result' in locals() else 'N/A'}")
            return {'action': 'discuss'}
        except AttributeError as e:
            logger.error(f"[MindMapThinkingAgent] Attribute error in intent detection: {e}", exc_info=True)
            return {'action': 'discuss'}
        except Exception as e:
            logger.error(f"[MindMapThinkingAgent] Intent detection failed: {e}", exc_info=True)
            return {'action': 'discuss'}
    
    async def _generate_greeting(self, session: Dict) -> AsyncGenerator[Dict, None]:
        """Generate initial greeting for Mind Map"""
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        topic = diagram_data.get('topic', '')
        branches = diagram_data.get('children', [])
        branch_count = len(branches)
        
        if language == 'zh':
            if topic:
                greeting = f"""👋 你好！我是 ThinkGuide，帮助你优化【思维导图】的联想思维。

我看到你正在创建关于【{topic}】的思维导图，目前有 **{branch_count} 个主分支**。

思维导图的核心是：**联想和发散**
- 从中心主题自由发散
- 建立多层级分支
- 探索想法之间的联系

让我们一起完善你的思维导图！请告诉我：
1. 这是什么教学情境？（年级、学科）
2. 你想让学生从【{topic}】联想到哪些方面？"""
            else:
                greeting = """👋 你好！我是 ThinkGuide，帮助你优化【思维导图】的联想思维。

思维导图的核心是：**联想和发散**
- 从中心主题自由发散
- 建立多层级分支
- 探索想法之间的联系

让我们一起完善你的思维导图！请告诉我：
1. 这是什么教学情境？
2. 你的中心主题是什么？"""
        else:
            if topic:
                greeting = f"""👋 Hello! I'm ThinkGuide, here to help you refine your 【Mind Map】associative thinking.

I see you're creating a mind map about 【{topic}】with **{branch_count} main branches**.

Mind Maps focus on: **Association and Divergence**
- Branch freely from central theme
- Build multi-level branches
- Explore connections between ideas

Let's refine your mind map! Please tell me:
1. What is your teaching context? (grade level, subject)
2. What aspects should students associate with 【{topic}】?"""
            else:
                greeting = """👋 Hello! I'm ThinkGuide, here to help you refine your 【Mind Map】associative thinking.

Mind Maps focus on: **Association and Divergence**
- Branch freely from central theme
- Build multi-level branches
- Explore connections between ideas

Let's refine your mind map! Please tell me:
1. What is your teaching context?
2. What is your central theme?"""
        
        yield {'event': 'message_chunk', 'content': greeting}
        yield {'event': 'message_complete', 'new_state': 'CONTEXT_GATHERING'}
    
    async def _handle_discussion(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """Handle pure discussion for Mind Map (overrides base implementation)."""
        diagram_data = session.get('diagram_data', {})
        topic = diagram_data.get('topic', 'this topic')
        branches = diagram_data.get('children', [])
        context = session.get('context', {})
        language = session.get('language', 'en')
        
        # Build branch list with their texts
        branch_list = []
        for i, branch in enumerate(branches):
            branch_text = branch.get('text', f'Branch {i+1}')
            sub_items = branch.get('children', [])
            sub_texts = [sub.get('text', '') for sub in sub_items if sub.get('text')]
            if sub_texts:
                branch_list.append(f"{i+1}. {branch_text} ({len(sub_texts)} sub-ideas: {', '.join(sub_texts[:3])}{'...' if len(sub_texts) > 3 else ''})")
            else:
                branch_list.append(f"{i+1}. {branch_text}")
        
        branches_text = '\n'.join(branch_list) if branch_list else '(No branches yet)'
        total_ideas = sum(len(branch.get('children', [])) for branch in branches)
        
        if language == 'zh':
            discussion_prompt = f"""教师正在讨论思维导图：「{topic}」。

当前状态：{current_state}
主分支数：{len(branches)}
子想法数：{total_ideas}
教学背景：{context.get('raw_message', '未指定')}

当前分支内容：
{branches_text}

教师说：{message}

请作为思维教练回应：
1. 承认他们的想法
2. 提出1-2个深入的苏格拉底式问题
3. 鼓励进一步思考

保持简洁、专业、无表情符号。"""
        else:
            discussion_prompt = f"""Teacher is discussing a Mind Map about "{topic}".

Current state: {current_state}
Main branches: {len(branches)}
Sub-ideas: {total_ideas}
Educational context: {context.get('raw_message', 'Not specified')}

Current branches:
{branches_text}

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
        """Handle Mind Map-specific actions"""
        action = intent.get('action')
        
        if action == 'open_node_palette':
            async for event in self._handle_open_node_palette(session):
                yield event
        else:
            async for event in self._handle_discussion(session, message, current_state):
                yield event
    
    async def _handle_open_node_palette(self, session: Dict) -> AsyncGenerator[Dict, None]:
        """Handle opening Node Palette for Mind Map"""
        diagram_data = session['diagram_data']
        language = session.get('language', 'en')
        # Mind Map: main topic is in "topic" field
        center_topic = diagram_data.get('topic', 'Unknown Topic')
        current_node_count = sum(len(branch.get('children', [])) for branch in diagram_data.get('children', []))
        current_branch_count = len(diagram_data.get('children', []))
        
        # Acknowledge request
        if language == 'zh':
            ack_prompt = f"用户想要打开节点选择板，为「{center_topic}」头脑风暴更多想法分支。目前有{current_branch_count}个主分支和{current_node_count}个子想法。用1-2句话说你将使用多个AI模型生成创意联想想法。"
        else:
            ack_prompt = f"User wants to open Node Palette to brainstorm more ideas for \"{center_topic}\". Currently {current_branch_count} main branches and {current_node_count} sub-ideas. Say in 1-2 sentences you'll generate creative associative ideas using multiple AI models."
        
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
        Get Mind Map-specific prompt for current state.
        
        Focuses on associative and divergent thinking.
        """
        current_state = session.get('state', 'CONTEXT_GATHERING')
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        
        topic = diagram_data.get('topic', '')
        branches = diagram_data.get('children', [])
        branch_count = len(branches)
        total_ideas = sum(len(branch.get('children', [])) for branch in branches)
        
        # Build branch list
        branch_texts = []
        for i, branch in enumerate(branches):
            branch_text = branch.get('text', f'Branch {i+1}')
            branch_texts.append(f"{i+1}. {branch_text}")
        branches_summary = '\n'.join(branch_texts) if branch_texts else '(No branches yet)'
        
        if current_state == 'CONTEXT_GATHERING':
            if language == 'zh':
                return f"""你好！我来帮你优化"{topic}"的思维导图。

思维导图用于发散思维和联想，从中心主题延伸出多个分支和想法。

请简单说说：
- 你的教学背景（年级、学科）
- 你想让学生通过{topic}联想到哪些方面？
- 或者直接告诉我你想怎么调整这个图

目前有{branch_count}个主分支，{total_ideas}个子想法。
当前分支：
{branches_summary}"""
            else:
                return f"""Hi! I'll help you refine your Mind Map on "{topic}".

Mind Maps use divergent and associative thinking, branching out from a central topic into multiple ideas.

Please briefly share:
- Your teaching context (grade level, subject)
- What aspects should students associate with {topic}?
- Or tell me directly how you'd like to adjust the diagram

Currently {branch_count} main branches and {total_ideas} sub-ideas.
Current branches:
{branches_summary}"""
        
        # Add more states as needed
        return self._get_default_prompt(session, message)
    
    async def _generate_suggested_nodes(self, session: Dict) -> list:
        """Generate suggested nodes for Mind Map"""
        return []

