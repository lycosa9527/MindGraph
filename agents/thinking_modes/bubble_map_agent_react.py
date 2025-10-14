"""
Bubble Map Thinking Mode Agent (ReAct Pattern)
================================================

Guides K12 teachers through descriptive thinking for Bubble Maps using ReAct pattern.
Inherits from BaseThinkingAgent and provides Bubble Map-specific behavior.

Bubble Map Purpose: Describe attributes and characteristics using adjectives

@author lycosa9527
@made_by MindSpring Team
"""

import logging
import json
from enum import Enum
from typing import Dict, AsyncGenerator, List

from agents.thinking_modes.base_thinking_agent import BaseThinkingAgent
from prompts.thinking_modes.circle_map import get_prompt  # Will use generic prompts for now

logger = logging.getLogger(__name__)


class BubbleMapState(Enum):
    """State machine for Bubble Map thinking workflow"""
    CONTEXT_GATHERING = "CONTEXT_GATHERING"
    ATTRIBUTE_ANALYSIS = "ATTRIBUTE_ANALYSIS"
    REFINEMENT_1 = "REFINEMENT_1"
    REFINEMENT_2 = "REFINEMENT_2"
    FINAL_REFINEMENT = "FINAL_REFINEMENT"
    COMPLETE = "COMPLETE"


class BubbleMapThinkingAgent(BaseThinkingAgent):
    """
    ThinkGuide agent for Bubble Maps.
    
    Bubble Map-specific workflow:
    1. Context Gathering: Understand teaching context
    2. Attribute Analysis: Analyze descriptive attributes
    3. Refinement 1: N → 8 attributes
    4. Refinement 2: 8 → 6 attributes
    5. Final Refinement: 6 → 5 core attributes
    
    Focus: Descriptive adjectives and characteristics
    """
    
    def __init__(self):
        """Initialize Bubble Map agent"""
        super().__init__(diagram_type='bubble_map')
    
    # ===== DIAGRAM-SPECIFIC: INTENT DETECTION =====
    
    async def _detect_user_intent(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> Dict:
        """
        Detect user intent for Bubble Map operations.
        
        Bubble Map-specific actions:
        - change_center: Change the center topic being described
        - update_node: Modify an attribute
        - delete_node: Remove an attribute
        - update_properties: Change node styling
        - add_nodes: Add new attributes
        - discuss: Just talking, no diagram changes
        """
        if not message:
            return {'action': 'discuss'}
        
        diagram_data = session.get('diagram_data', {})
        center_text = diagram_data.get('center', {}).get('text', '')
        children = diagram_data.get('children', [])
        language = session.get('language', 'en')
        
        # Build attribute list for context
        attrs_list = '\n'.join([f"{i+1}. {node['text']}" for i, node in enumerate(children)])
        
        # LLM-based intent detection
        if language == 'zh':
            system_prompt = f"""你是意图识别专家。分析用户想对气泡图做什么操作。

当前工作流阶段：{current_state}

返回JSON格式：
{{
  "action": "change_center" | "update_node" | "delete_node" | "update_properties" | "add_nodes" | "open_node_palette" | "discuss",
  "target": "目标文本",
  "node_index": 节点序号（1-based），
  "properties": {{"fillColor": "#颜色代码", "bold": true/false, "italic": true/false}}
}}

操作说明：
- change_center: 改变中心主题
- update_node: 修改某个属性节点的文字
- delete_node: 删除某个属性节点
- update_properties: 修改节点样式（颜色、粗体、斜体等）
- add_nodes: 明确要求添加新的属性节点
- open_node_palette: 用户想要打开节点选择板，使用多个AI模型头脑风暴更多节点
- discuss: 只是讨论，不修改图表

⚠️ 在CONTEXT_GATHERING阶段，除非用户明确说"添加"、"生成"，否则返回"discuss"

颜色映射：红色→#F44336, 蓝色→#2196F3, 绿色→#4CAF50, 黄色→#FFEB3B, 橙色→#FF9800, 紫色→#9C27B0

只返回JSON，不要其他文字。"""
            
            user_prompt = f"""当前气泡图：
中心主题：{center_text}
属性节点 ({len(children)}个)：
{attrs_list if attrs_list else '（暂无节点）'}

用户消息：{message}"""
        else:
            system_prompt = f"""You are an intent recognition expert. Analyze what the user wants to do with the Bubble Map.

Current workflow stage: {current_state}

Return JSON format:
{{
  "action": "change_center" | "update_node" | "delete_node" | "update_properties" | "add_nodes" | "open_node_palette" | "discuss",
  "target": "target text",
  "node_index": node number (1-based),
  "properties": {{"fillColor": "#color", "bold": true/false, "italic": true/false}}
}}

Action descriptions:
- change_center: Change the center topic being described
- update_node: Modify an attribute node's text
- delete_node: Remove an attribute node
- update_properties: Change node styling (color, bold, italic, etc.)
- add_nodes: Explicitly add new attribute nodes
- open_node_palette: User wants to open Node Palette to brainstorm more attributes
- discuss: Just discussing, no diagram changes

⚠️ During CONTEXT_GATHERING, unless user explicitly says "add", "generate", return "discuss"

Color mapping: red→#F44336, blue→#2196F3, green→#4CAF50, yellow→#FFEB3B, orange→#FF9800, purple→#9C27B0

Return only JSON, no other text."""
            
            user_prompt = f"""Current Bubble Map:
Center topic: {center_text}
Attribute nodes ({len(children)} total):
{attrs_list if attrs_list else '(No attributes yet)'}

User message: {message}"""
        
        try:
            response = await self.llm.chat_stream_complete(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            # Clean and parse JSON
            response = response.strip()
            if response.startswith('```'):
                response = response.split('```')[1]
                if response.startswith('json'):
                    response = response[4:]
            response = response.strip()
            
            intent = json.loads(response)
            logger.info(f"[BubbleMapThinkingAgent] Detected intent: {intent.get('action')}")
            return intent
            
        except Exception as e:
            logger.error(f"[BubbleMapThinkingAgent] Intent detection error: {e}")
            return {'action': 'discuss'}
    
    # ===== DIAGRAM-SPECIFIC: ACTION HANDLER =====
    
    async def _handle_action(
        self,
        session: Dict,
        intent: Dict,
        message: str
    ) -> AsyncGenerator[str, None]:
        """
        Handle Bubble Map-specific actions.
        
        Actions delegate to frontend for diagram updates.
        Agent provides conversational feedback.
        """
        action = intent.get('action', 'discuss')
        language = session.get('language', 'en')
        
        if action == 'open_node_palette':
            # Yield action event for frontend
            yield json.dumps({
                'type': 'action',
                'action': 'open_node_palette',
                'data': {}
            }) + '\n\n'
            
            # Provide conversational feedback
            msg = "正在打开节点选择板..." if language == 'zh' else "Opening Node Palette..."
            yield json.dumps({
                'type': 'message',
                'content': msg
            }) + '\n\n'
            return
        
        # For other actions, provide guidance based on current state
        current_state = session.get('state', 'CONTEXT_GATHERING')
        
        # Generate response using state-specific prompts
        async for chunk in self._generate_state_response(session, message, intent):
            yield chunk
    
    # ===== DIAGRAM-SPECIFIC: STATE PROMPTS =====
    
    def _get_state_prompt(
        self,
        session: Dict,
        message: str = None,
        intent: Dict = None
    ) -> str:
        """
        Get Bubble Map-specific prompt for current state.
        
        Focuses on descriptive attributes and adjectives.
        """
        current_state = session.get('state', 'CONTEXT_GATHERING')
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        
        center_text = diagram_data.get('center', {}).get('text', '')
        children = diagram_data.get('children', [])
        attr_count = len(children)
        
        if current_state == 'CONTEXT_GATHERING':
            if language == 'zh':
                return f"""你好！我来帮你优化"{center_text}"的气泡图。

气泡图用形容词和描述性短语来描述中心主题的属性特征。

请简单说说：
- 你的教学背景（年级、学科）
- 你想让学生理解{center_text}的哪些方面？
- 或者直接告诉我你想怎么调整这个图

目前有{attr_count}个属性节点。"""
            else:
                return f"""Hi! I'll help you refine your Bubble Map on "{center_text}".

Bubble Maps use adjectives and descriptive phrases to describe attributes of the central topic.

Please briefly share:
- Your teaching context (grade level, subject)
- What aspects of {center_text} should students understand?
- Or tell me directly how you'd like to adjust the diagram

Currently {attr_count} attribute nodes."""
        
        elif current_state == 'ATTRIBUTE_ANALYSIS':
            attrs_list = ', '.join([node['text'] for node in children])
            
            if language == 'zh':
                return f"""让我帮你分析这些属性词与"{center_text}"的关系。

当前属性 ({attr_count}个)：{attrs_list}

思考这些问题：
- 哪些属性词最能抓住{center_text}的本质特征？
- 哪些属性是学生最需要理解的？
- 是否有些属性词太相似或重复？
- 从哪些维度描述的？（外观、功能、感受等）

你觉得这些属性词中，哪些最重要？"""
            else:
                return f"""Let me help you analyze these attributes for "{center_text}".

Current attributes ({attr_count}): {attrs_list}

Think about:
- Which attributes best capture the essence of {center_text}?
- Which attributes do students most need to understand?
- Are any attributes too similar or redundant?
- What dimensions do they cover? (appearance, function, feeling, etc.)

Which of these attributes do you think are most important?"""
        
        # Add more states as needed
        return self._get_default_prompt(session, message)
    
    # ===== DIAGRAM-SPECIFIC: NODE GENERATION =====
    
    async def _generate_suggested_nodes(
        self,
        session: Dict
    ) -> List[str]:
        """
        Generate suggested attribute nodes for Bubble Map.
        
        Uses educational context to suggest descriptive adjectives.
        """
        diagram_data = session.get('diagram_data', {})
        center_text = diagram_data.get('center', {}).get('text', '')
        language = session.get('language', 'en')
        
        if language == 'zh':
            prompt = f"""为气泡图生成5个描述"{center_text}"的属性词。

要求：
1. 使用形容词或形容词短语
2. 从多个维度描述（外观、功能、特点、感受等）
3. 简洁明了，适合K12教学
4. 每个属性词单独一行

只输出属性词，不要编号："""
        else:
            prompt = f"""Generate 5 attribute words describing "{center_text}" for a Bubble Map.

Requirements:
1. Use adjectives or adjectival phrases
2. Cover multiple dimensions (appearance, function, characteristics, feeling, etc.)
3. Concise and clear, suitable for K12 teaching
4. One attribute per line

Output only the attributes, no numbering:"""
        
        try:
            response = await self.llm.chat_stream_complete(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': '你是K12教育专家。' if language == 'zh' else 'You are a K12 education expert.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0.8,
                max_tokens=200
            )
            
            # Parse line-by-line
            lines = [line.strip() for line in response.split('\n') if line.strip()]
            # Remove numbering if present
            suggestions = [line.lstrip('0123456789.-、）) ').strip() for line in lines if len(line.strip()) > 1]
            
            return suggestions[:5]  # Return max 5
            
        except Exception as e:
            logger.error(f"[BubbleMapThinkingAgent] Node generation error: {e}")
            return []


def get_bubble_map_thinking_agent() -> BubbleMapThinkingAgent:
    """Get singleton instance of Bubble Map thinking agent"""
    global _bubble_map_thinking_agent
    if '_bubble_map_thinking_agent' not in globals():
        globals()['_bubble_map_thinking_agent'] = BubbleMapThinkingAgent()
    return globals()['_bubble_map_thinking_agent']

