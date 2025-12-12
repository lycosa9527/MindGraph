"""
Tree Map Thinking Mode Agent (ReAct Pattern)
==============================================

Guides K12 teachers through hierarchical categorization thinking for Tree Maps.

Tree Map Purpose: Classify items into categories and sub-categories

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from enum import Enum
from typing import Dict, AsyncGenerator

from agents.thinking_modes.base_thinking_agent import BaseThinkingAgent

logger = logging.getLogger(__name__)


class TreeMapState(Enum):
    """State machine for Tree Map thinking workflow"""
    CONTEXT_GATHERING = "CONTEXT_GATHERING"
    CATEGORY_ANALYSIS = "CATEGORY_ANALYSIS"
    REFINEMENT_1 = "REFINEMENT_1"
    REFINEMENT_2 = "REFINEMENT_2"
    FINAL_REFINEMENT = "FINAL_REFINEMENT"
    COMPLETE = "COMPLETE"


class TreeMapThinkingAgent(BaseThinkingAgent):
    """
    ThinkGuide agent for Tree Maps.
    
    Tree Map-specific workflow:
    1. Context Gathering: Understand teaching context
    2. Category Analysis: Analyze classification structure
    3. Refinement: Improve categorization clarity
    
    Focus: Hierarchical classification and grouping
    """
    
    def __init__(self):
        """Initialize Tree Map agent"""
        super().__init__(diagram_type='tree_map')
    
    async def _detect_user_intent(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> Dict:
        """Detect user intent for Tree Map operations"""
        if not message:
            return {'action': 'discuss'}
        
        diagram_data = session.get('diagram_data', {})
        language = session.get('language', 'en')
        
        # Build intent detection prompt
        if language == 'zh':
            system_prompt = """你是意图识别专家。分析用户想对树状图做什么操作。

返回JSON：
{
  "action": "change_topic" | "update_node" | "delete_node" | "add_nodes" | "open_node_palette" | "discuss",
  "target": "目标文本",
  "category": "类别名称"
}"""
        else:
            system_prompt = """You are an intent recognition expert for Tree Maps.

Return JSON:
{
  "action": "change_topic" | "update_node" | "delete_node" | "add_nodes" | "open_node_palette" | "discuss",
  "target": "target text",
  "category": "category name"
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
        """Generate initial greeting for Tree Map"""
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        topic = diagram_data.get('topic', '')
        children = diagram_data.get('children', [])
        category_count = len(children)
        
        if language == 'zh':
            if topic:
                greeting = f"""👋 你好！我是 ThinkGuide，专门帮助你优化【树状图】的分类思维。

我看到你正在对【{topic}】进行分类，目前有 **{category_count} 个类别**。

树状图的核心是：**分类和归类**
- 将事物按照共同特征分组
- 建立清晰的层次结构
- 每个类别要互不重叠

让我们一起完善你的分类结构吧！请告诉我：
1. 这是什么教学情境？（年级、学科）
2. 你对【{topic}】的分类标准是什么？是否还有其他分类方式？"""
            else:
                greeting = f"""👋 你好！我是 ThinkGuide，专门帮助你优化【树状图】的分类思维。

树状图的核心是：**分类和归类**
- 将事物按照共同特征分组
- 建立清晰的层次结构
- 每个类别要互不重叠

让我们一起完善你的分类结构吧！请告诉我：
1. 这是什么教学情境？
2. 你想分类的主题是什么？"""
        else:
            if topic:
                greeting = f"""👋 Hello! I'm ThinkGuide, here to help you refine your 【Tree Map】classification thinking.

I see you're classifying 【{topic}】with **{category_count} categories**.

Tree Maps focus on: **Classification and Categorization**
- Group items by shared characteristics
- Build clear hierarchical structures
- Ensure categories are mutually exclusive

Let's refine your classification! Please tell me:
1. What is your teaching context? (grade level, subject)
2. What criteria are you using to classify 【{topic}】? Are there other ways to categorize it?"""
            else:
                greeting = f"""👋 Hello! I'm ThinkGuide, here to help you refine your 【Tree Map】classification thinking.

Tree Maps focus on: **Classification and Categorization**
- Group items by shared characteristics
- Build clear hierarchical structures
- Ensure categories are mutually exclusive

Let's refine your classification! Please tell me:
1. What is your teaching context?
2. What topic are you classifying?"""
        
        yield {'event': 'message_chunk', 'content': greeting}
        yield {'event': 'message_complete', 'new_state': 'CONTEXT_GATHERING'}
    
    async def _handle_discussion(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """Handle pure discussion for Tree Map (overrides base implementation)."""
        diagram_data = session.get('diagram_data', {})
        topic = diagram_data.get('topic', 'this topic')
        branches = diagram_data.get('children', [])
        context = session.get('context', {})
        language = session.get('language', 'en')
        
        total_items = sum(len(branch.get('children', [])) for branch in branches)
        
        if language == 'zh':
            discussion_prompt = f"""教师正在讨论树状图：「{topic}」。

当前状态：{current_state}
分类数：{len(branches)}
项目数：{total_items}
教学背景：{context.get('raw_message', '未指定')}

教师说：{message}

请作为思维教练回应：
1. 承认他们的想法
2. 提出1-2个深入的苏格拉底式问题
3. 鼓励进一步思考

保持简洁、专业、无表情符号。"""
        else:
            discussion_prompt = f"""Teacher is discussing a Tree Map about "{topic}".

Current state: {current_state}
Categories: {len(branches)}
Items: {total_items}
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
        """Handle Tree Map-specific actions"""
        action = intent.get('action')
        
        if action == 'open_node_palette':
            async for event in self._handle_open_node_palette(session):
                yield event
        else:
            # Delegate other actions to discussion
            async for event in self._handle_discussion(session, message, current_state):
                yield event
    
    async def _handle_open_node_palette(self, session: Dict) -> AsyncGenerator[Dict, None]:
        """Handle opening Node Palette for Tree Map with stage-aware guidance"""
        diagram_data = session['diagram_data']
        language = session.get('language', 'en')
        center_topic = diagram_data.get('topic', 'Unknown Topic')
        current_node_count = sum(len(branch.get('children', [])) for branch in diagram_data.get('children', []))
        
        # Determine current stage based on diagram data
        has_dimension = diagram_data.get('dimension') is not None and diagram_data.get('dimension') != ''
        has_categories = diagram_data.get('children') is not None and len(diagram_data.get('children', [])) > 0
        
        if not has_dimension:
            # Stage 1: Dimension Selection
            stage = 'dimensions'
            if language == 'zh':
                ack_prompt = f"好的！节点调色板（维度选择）即将打开。\n\n为「{center_topic}」选择分类维度是第一步。维度决定了如何分类这个主题（例如：按功能、按结构、按时间等）。\n\n我将使用4个AI模型为你生成多个维度选项。**请只选择1个维度**，然后点击\"下一步\"继续到类别生成阶段。"
            else:
                ack_prompt = f"Great! Node Palette (dimension selection) is opening.\n\nChoosing a classification dimension for \"{center_topic}\" is the first step. The dimension determines how we'll classify this topic (e.g., by function, by structure, by time, etc.).\n\nI'll use 4 AI models to generate dimension options for you. **Please select ONLY 1 dimension**, then click \"Next\" to continue to category generation."
        elif not has_categories:
            # Stage 2: Category Generation
            stage = 'categories'
            dimension = diagram_data.get('dimension', '')
            if language == 'zh':
                ack_prompt = f"好的！节点调色板（类别生成）即将打开。\n\n现在让我们为「{center_topic}」生成分类类别，使用维度：{dimension}。\n\n我将使用4个AI模型生成符合这个维度的类别。**请选择你想要的类别**（可以选择多个），然后点击\"下一步\"。\n\n系统将为你选择的每个类别创建一个独立的标签页，并同时启动多个AI模型为所有类别生成具体项目。"
            else:
                ack_prompt = f"Great! Node Palette (category generation) is opening.\n\nNow let's generate categories for \"{center_topic}\" using dimension: {dimension}.\n\nI'll use 4 AI models to generate categories that follow this dimension. **Please select the categories you want** (multiple selection allowed), then click \"Next\".\n\nThe system will create a separate tab for each selected category and launch multiple AI models simultaneously to generate specific items for all categories."
        else:
            # Stage 3: Children Generation
            stage = 'children'
            dimension = diagram_data.get('dimension', '')
            category_count = len(diagram_data.get('children', []))
            if language == 'zh':
                ack_prompt = f"好的！现在让我们为你的{category_count}个类别添加具体项目。\n\n选择一个类别，我将使用4个AI模型为该类别生成具体的项目。你可以为每个类别分别选择项目。"
            else:
                ack_prompt = f"Great! Now let's add specific items to your {category_count} categories.\n\nSelect a category, and I'll use 4 AI models to generate specific items for it. You can select items for each category separately."
        
        async for chunk in self._stream_llm_response(ack_prompt, session):
            yield chunk
        
        # Extract educational context
        context = session.get('context', {})
        educational_context = {
            'grade_level': context.get('grade_level', '5th grade'),
            'subject': context.get('subject', 'General'),
            'objective': context.get('objective', ''),
            'raw_message': context.get('raw_message', ''),
            'language': language
        }
        
        # Build stage-specific data
        stage_data = {}
        if stage == 'categories' and has_dimension:
            stage_data['dimension'] = diagram_data.get('dimension', '')
        elif stage == 'children' and has_dimension:
            stage_data['dimension'] = diagram_data.get('dimension', '')
            # For children stage, we'll need to know which category - this will be set by frontend
            # when user selects a category
        
        # Yield action event with stage information
        yield {
            'event': 'action',
            'action': 'open_node_palette',
            'data': {
                'center_topic': center_topic,
                'current_node_count': current_node_count,
                'diagram_data': diagram_data,
                'session_id': session['session_id'],
                'educational_context': educational_context,
                'stage': stage,  # NEW: Current stage
                'stage_data': stage_data  # NEW: Stage-specific data
            }
        }
    
    def _get_state_prompt(
        self,
        session: Dict,
        message: str = None,
        intent: Dict = None
    ) -> str:
        """
        Get Tree Map-specific prompt for current state.
        
        Focuses on hierarchical classification and categorization.
        """
        current_state = session.get('state', 'CONTEXT_GATHERING')
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        
        topic = diagram_data.get('topic', '')
        branches = diagram_data.get('children', [])
        category_count = len(branches)
        item_count = sum(len(branch.get('children', [])) for branch in branches)
        
        if current_state == 'CONTEXT_GATHERING':
            if language == 'zh':
                return f"""你好！我来帮你优化"{topic}"的树状图。

树状图用于分类和归纳，将主题分解为不同的类别和子项。

请简单说说：
- 你的教学背景（年级、学科）
- 你想让学生理解{topic}的哪些分类方式？
- 或者直接告诉我你想怎么调整这个图

目前有{category_count}个分类，{item_count}个子项。"""
            else:
                return f"""Hi! I'll help you refine your Tree Map on "{topic}".

Tree Maps are used for classification and categorization, breaking a topic into categories and sub-items.

Please briefly share:
- Your teaching context (grade level, subject)
- What classification methods of {topic} should students understand?
- Or tell me directly how you'd like to adjust the diagram

Currently {category_count} categories and {item_count} items."""
        
        # Add more states as needed
        return self._get_default_prompt(session, message)
    
    async def _generate_suggested_nodes(self, session: Dict) -> list:
        """Generate suggested nodes for Tree Map"""
        return []  # Node Palette handles this

