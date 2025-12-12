"""
Double Bubble Map Thinking Mode Agent (ReAct Pattern)
======================================================

Guides K12 teachers through comparative thinking for Double Bubble Maps using ReAct pattern.
Inherits from BaseThinkingAgent and provides Double Bubble Map-specific behavior.

Double Bubble Map Purpose: Compare and contrast two topics by identifying similarities and differences

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


class DoubleBubbleMapState(Enum):
    """State machine for Double Bubble Map thinking workflow"""
    CONTEXT_GATHERING = "CONTEXT_GATHERING"
    COMPARISON_ANALYSIS = "COMPARISON_ANALYSIS"
    REFINEMENT_1 = "REFINEMENT_1"
    REFINEMENT_2 = "REFINEMENT_2"
    FINAL_REFINEMENT = "FINAL_REFINEMENT"
    COMPLETE = "COMPLETE"


class DoubleBubbleMapThinkingAgent(BaseThinkingAgent):
    """
    ThinkGuide agent for Double Bubble Maps.
    
    Double Bubble Map-specific workflow:
    1. Context Gathering: Understand teaching context and topics being compared
    2. Comparison Analysis: Analyze similarities and differences
    3. Refinement 1: Refine similarities and differences
    4. Refinement 2: Balance the comparison
    5. Final Refinement: Polish the comparison
    
    Focus: Comparative thinking - similarities and differences
    """
    
    def __init__(self):
        """Initialize Double Bubble Map agent"""
        super().__init__(diagram_type='double_bubble_map')
    
    # ===== DIAGRAM-SPECIFIC: GREETING =====
    
    async def _generate_greeting(self, session: Dict) -> AsyncGenerator[Dict, None]:
        """Generate initial greeting for Double Bubble Map"""
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        left_topic = diagram_data.get('left', '')
        right_topic = diagram_data.get('right', '')
        similarities = diagram_data.get('similarities', [])
        left_diffs = diagram_data.get('left_differences', [])
        right_diffs = diagram_data.get('right_differences', [])
        similarity_count = len(similarities)
        difference_count = len(left_diffs)
        
        if language == 'zh':
            if left_topic and right_topic:
                greeting = f"""👋 你好！我是 ThinkGuide，帮助你优化【双气泡图】的比较思维。

我看到你正在比较【{left_topic}】和【{right_topic}】，目前有 **{similarity_count} 个相似点** 和 **{difference_count} 个差异点**。

双气泡图的核心是：**比较和对比**
- 识别共同特征（相似点）
- 发现独特之处（差异点）
- 深入理解两者关系

让我们一起完善你的比较分析！请告诉我：
1. 这是什么教学情境？（年级、学科）
2.【{left_topic}】和【{right_topic}】还有哪些重要的相似点或差异点？"""
            else:
                greeting = """👋 你好！我是 ThinkGuide，帮助你优化【双气泡图】的比较思维。

双气泡图的核心是：**比较和对比**
- 识别共同特征（相似点）
- 发现独特之处（差异点）
- 深入理解两者关系

让我们一起完善你的比较分析！请告诉我：
1. 这是什么教学情境？
2. 你想比较哪两个事物？"""
        else:
            if left_topic and right_topic:
                greeting = f"""👋 Hello! I'm ThinkGuide, here to help you refine your 【Double Bubble Map】comparative thinking.

I see you're comparing 【{left_topic}】and 【{right_topic}】with **{similarity_count} similarities** and **{difference_count} differences**.

Double Bubble Maps focus on: **Compare and Contrast**
- Identify common features (similarities)
- Discover unique characteristics (differences)
- Understand relationships between two things

Let's refine your comparison! Please tell me:
1. What is your teaching context? (grade level, subject)
2. What other important similarities or differences exist between 【{left_topic}】and 【{right_topic}】?"""
            else:
                greeting = """👋 Hello! I'm ThinkGuide, here to help you refine your 【Double Bubble Map】comparative thinking.

Double Bubble Maps focus on: **Compare and Contrast**
- Identify common features (similarities)
- Discover unique characteristics (differences)
- Understand relationships between two things

Let's refine your comparison! Please tell me:
1. What is your teaching context?
2. What two things do you want to compare?"""
        
        yield {'event': 'message_chunk', 'content': greeting}
        yield {'event': 'message_complete', 'new_state': 'CONTEXT_GATHERING'}
    
    # ===== DIAGRAM-SPECIFIC: INTENT DETECTION =====
    
    async def _detect_user_intent(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> Dict:
        """
        Detect user intent for Double Bubble Map operations.
        
        Double Bubble Map-specific actions:
        - change_topics: Change the two topics being compared
        - update_node: Modify a similarity or difference node
        - delete_node: Remove a node
        - update_properties: Change node styling
        - add_nodes: Add new similarities or differences
        - discuss: Just talking, no diagram changes
        """
        if not message:
            return {'action': 'discuss'}
        
        diagram_data = session.get('diagram_data', {})
        left_topic = diagram_data.get('left', '')
        right_topic = diagram_data.get('right', '')
        similarities = diagram_data.get('similarities', [])
        left_diffs = diagram_data.get('left_differences', [])
        right_diffs = diagram_data.get('right_differences', [])
        language = session.get('language', 'en')
        
        # Build lists for context
        sim_list = '\n'.join([f"{i+1}. {s}" for i, s in enumerate(similarities)])
        diff_list = '\n'.join([f"{i+1}. {left_diffs[i]} ↔ {right_diffs[i]}" for i in range(len(left_diffs))])
        
        # LLM-based intent detection
        if language == 'zh':
            system_prompt = f"""你是意图识别专家。分析用户想对双气泡图做什么操作。

当前工作流阶段：{current_state}

返回JSON格式：
{{
  "action": "change_topics" | "update_node" | "delete_node" | "update_properties" | "add_nodes" | "open_node_palette" | "discuss",
  "target": "目标文本",
  "node_index": 节点序号（1-based），
  "node_type": "similarity" | "difference",
  "properties": {{"fillColor": "#颜色代码", "bold": true/false, "italic": true/false}}
}}

操作说明：
- change_topics: 改变被比较的两个主题
- update_node: 修改某个相似点或差异点
- delete_node: 删除某个节点
- update_properties: 修改节点样式（颜色、粗体、斜体等）
- add_nodes: 明确要求添加新的节点
- open_node_palette: 用户想要打开节点选择板，使用多个AI模型头脑风暴更多节点
- discuss: 只是讨论，不修改图表

⚠️ 在CONTEXT_GATHERING阶段，除非用户明确说"添加"、"生成"，否则返回"discuss"

颜色映射：红色→#F44336, 蓝色→#2196F3, 绿色→#4CAF50, 黄色→#FFEB3B, 橙色→#FF9800, 紫色→#9C27B0

只返回JSON，不要其他文字。"""
            
            user_prompt = f"""当前双气泡图：
左侧主题：{left_topic}
右侧主题：{right_topic}
相似点 ({len(similarities)}个)：
{sim_list if sim_list else '（暂无）'}
差异对 ({len(left_diffs)}对)：
{diff_list if diff_list else '（暂无）'}

用户消息：{message}"""
        else:
            system_prompt = f"""You are an intent recognition expert. Analyze what the user wants to do with the Double Bubble Map.

Current workflow stage: {current_state}

Return JSON format:
{{
  "action": "change_topics" | "update_node" | "delete_node" | "update_properties" | "add_nodes" | "open_node_palette" | "discuss",
  "target": "target text",
  "node_index": node number (1-based),
  "node_type": "similarity" | "difference",
  "properties": {{"fillColor": "#color", "bold": true/false, "italic": true/false}}
}}

Action descriptions:
- change_topics: Change the two topics being compared
- update_node: Modify a similarity or difference node
- delete_node: Remove a node
- update_properties: Change node styling (color, bold, italic, etc.)
- add_nodes: Explicitly add new nodes
- open_node_palette: User wants to open Node Palette to brainstorm more nodes
- discuss: Just discussing, no diagram changes

⚠️ During CONTEXT_GATHERING, unless user explicitly says "add", "generate", return "discuss"

Color mapping: red→#F44336, blue→#2196F3, green→#4CAF50, yellow→#FFEB3B, orange→#FF9800, purple→#9C27B0

Return only JSON, no other text."""
            
            user_prompt = f"""Current Double Bubble Map:
Left topic: {left_topic}
Right topic: {right_topic}
Similarities ({len(similarities)} total):
{sim_list if sim_list else '(None yet)'}
Difference pairs ({len(left_diffs)} total):
{diff_list if diff_list else '(None yet)'}

User message: {message}"""
        
        # Call LLM to detect intent
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
            
            response = json.loads(result_text)
            logger.debug(f"[DoubleBubbleMapAgent] Intent detected: {response.get('action', 'unknown')}")
            return response
            
        except Exception as e:
            logger.error(f"[DoubleBubbleMapAgent] Intent detection failed: {e}")
            return {'action': 'discuss'}
    
    # ===== DIAGRAM-SPECIFIC: DISCUSSION OVERRIDE =====
    
    async def _handle_discussion(
        self,
        session: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """
        Handle pure discussion for Double Bubble Map (overrides base implementation).
        Uses Double Bubble Map-specific data structure (left/right topics).
        """
        diagram_data = session.get('diagram_data', {})
        left_topic = diagram_data.get('left', '')
        right_topic = diagram_data.get('right', '')
        similarities = diagram_data.get('similarities', [])
        left_diffs = diagram_data.get('left_differences', [])
        right_diffs = diagram_data.get('right_differences', [])
        context = session.get('context', {})
        
        language = session.get('language', 'en')
        
        if language == 'zh':
            discussion_prompt = f"""教师正在讨论双气泡图：「{left_topic}」vs「{right_topic}」。

当前状态：{current_state}
相似点：{len(similarities)}个
差异对：{len(left_diffs)}对
教学背景：{context.get('raw_message', '未指定')}

教师说：{message}

请作为思维教练回应：
1. 承认他们的想法
2. 提出1-2个深入的苏格拉底式问题
3. 鼓励进一步思考

保持简洁、专业、无表情符号。"""
        else:
            discussion_prompt = f"""Teacher is discussing a Double Bubble Map: "{left_topic}" vs "{right_topic}".

Current state: {current_state}
Similarities: {len(similarities)}
Difference pairs: {len(left_diffs)}
Educational context: {context.get('raw_message', 'Not specified')}

Teacher said: {message}

Respond as a thinking coach:
1. Acknowledge their thoughts
2. Ask 1-2 deeper Socratic questions
3. Encourage further thinking

Keep it concise, professional, no emojis."""
        
        async for event in self._stream_llm_response(discussion_prompt, session):
            yield event
    
    # ===== DIAGRAM-SPECIFIC: ACTION HANDLING =====
    
    async def _handle_action(
        self,
        session: Dict,
        intent: Dict,
        message: str,
        current_state: str
    ) -> AsyncGenerator[Dict, None]:
        """
        Handle Double Bubble Map-specific actions.
        
        Actions delegate to frontend for diagram updates.
        Agent provides conversational feedback.
        """
        action = intent.get('action', 'discuss')
        language = session.get('language', 'en')
        
        if action == 'open_node_palette':
            # Yield action event for frontend
            yield {
                'event': 'action',
                'action': 'open_node_palette',
                'data': {}
            }
            
            # Provide conversational feedback
            msg = "正在打开节点选择板..." if language == 'zh' else "Opening Node Palette..."
            yield {
                'event': 'message_chunk',
                'content': msg
            }
            yield {
                'event': 'message_complete',
                'new_state': current_state
            }
            return
        
        # For other actions, fallback to discussion
        async for chunk in self._handle_discussion(session, message, current_state):
            yield chunk
    
    # ===== DIAGRAM-SPECIFIC: STATE PROMPTS =====
    
    def _get_state_prompt(
        self,
        session: Dict,
        message: str = None,
        intent: Dict = None
    ) -> str:
        """
        Get Double Bubble Map-specific prompt for current state.
        
        Focuses on comparative thinking - similarities and differences.
        """
        current_state = session.get('state', 'CONTEXT_GATHERING')
        language = session.get('language', 'en')
        diagram_data = session.get('diagram_data', {})
        
        left_topic = diagram_data.get('left', '')
        right_topic = diagram_data.get('right', '')
        similarities = diagram_data.get('similarities', [])
        left_diffs = diagram_data.get('left_differences', [])
        right_diffs = diagram_data.get('right_differences', [])
        
        sim_count = len(similarities)
        diff_count = len(left_diffs)
        
        if current_state == 'CONTEXT_GATHERING':
            if language == 'zh':
                return f"""你好！我来帮你优化"{left_topic} vs {right_topic}"的双气泡图。

双气泡图用于比较两个主题，找出它们的相似点和差异点。

请简单说说：
- 你的教学背景（年级、学科）
- 你想让学生理解这两个主题的哪些方面？
- 或者直接告诉我你想怎么调整这个图

目前有{sim_count}个相似点和{diff_count}对差异。"""
            else:
                return f"""Hi! I'll help you refine your Double Bubble Map comparing "{left_topic}" and "{right_topic}".

Double Bubble Maps are used to compare two topics, identifying their similarities and differences.

Please briefly share:
- Your teaching context (grade level, subject)
- What aspects of these topics should students understand?
- Or tell me directly how you'd like to adjust the diagram

Currently {sim_count} similarities and {diff_count} difference pairs."""
        
        elif current_state == 'COMPARISON_ANALYSIS':
            sim_list = ', '.join(similarities) if similarities else '(无)' if language == 'zh' else '(none)'
            
            if language == 'zh':
                return f"""让我帮你分析"{left_topic}"和"{right_topic}"的对比关系。

相似点 ({sim_count}个)：{sim_list}
差异对 ({diff_count}对)

思考这些问题：
- 哪些相似点最能体现两者的共同本质？
- 差异点是否形成了清晰的对比？
- 是否遗漏了重要的比较维度？
- 对比是否平衡？（相似点和差异点的数量）

你觉得这个对比中哪些部分最重要？"""
            else:
                return f"""Let me help you analyze the comparison between "{left_topic}" and "{right_topic}".

Similarities ({sim_count}): {sim_list}
Difference pairs ({diff_count})

Think about:
- Which similarities best capture their common essence?
- Do the differences form clear contrasts?
- Are any important comparison dimensions missing?
- Is the comparison balanced? (number of similarities vs differences)

Which parts of this comparison do you think are most important?"""
        
        # Default fallback for unhandled states
        if language == 'zh':
            return f"让我们继续完善「{left_topic}」与「{right_topic}」的对比分析。你有什么想法或问题吗？"
        return f"Let's continue refining your comparison of \"{left_topic}\" and \"{right_topic}\". What are your thoughts or questions?"
    
    # ===== DIAGRAM-SPECIFIC: NODE GENERATION =====
    
    async def _generate_suggested_nodes(
        self,
        session: Dict
    ) -> List[str]:
        """
        Generate suggested nodes for Double Bubble Map.
        
        Returns both similarities and difference pairs.
        """
        diagram_data = session.get('diagram_data', {})
        left_topic = diagram_data.get('left', '')
        right_topic = diagram_data.get('right', '')
        language = session.get('language', 'en')
        
        if language == 'zh':
            prompt = f"""为双气泡图生成对比建议：{left_topic} vs {right_topic}

生成2个相似点和2对差异点。

格式：
相似点：共同特征
差异：{left_topic}的特征 | {right_topic}的对比特征

适合K12教学，简洁明了："""
        else:
            prompt = f"""Generate comparison suggestions for Double Bubble Map: {left_topic} vs {right_topic}

Generate 2 similarities and 2 difference pairs.

Format:
Similarity: shared feature
Difference: {left_topic} feature | {right_topic} contrasting feature

Suitable for K12 teaching, concise and clear:"""
        
        try:
            system_message = '你是K12教育专家。' if language == 'zh' else 'You are a K12 education expert.'
            response = await self.llm.chat(
                prompt=prompt,
                model=self.model,
                system_message=system_message,
                temperature=0.8,
                max_tokens=300
            )
            
            # Parse suggestions
            suggestions = []
            for line in response.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    suggestions.append(line)
            
            return suggestions[:6]  # Return max 6 suggestions
            
        except Exception as e:
            logger.error(f"[DoubleBubbleMapAgent] Node generation error: {e}")
            return []
    
    # ===== LEGACY METHOD (kept for compatibility) =====
    
    async def _generate_nodes_with_llm(
        self,
        session: Dict,
        count: int = 5
    ) -> AsyncGenerator[Dict, None]:
        """
        Generate similarity and difference suggestions for Double Bubble Map.
        
        Yields comparison suggestions progressively.
        """
        diagram_data = session.get('diagram_data', {})
        left_topic = diagram_data.get('left', '')
        right_topic = diagram_data.get('right', '')
        educational_context = session.get('educational_context', {})
        language = session.get('language', 'en')
        
        # Build prompt for comparison generation
        if language == 'zh':
            system_prompt = """你是K12教育专家。为双气泡图生成对比分析建议。

每行输出一个JSON对象：
{"type": "similarity", "text": "相似点"}
或
{"type": "difference", "left": "左侧差异", "right": "右侧差异"}

生成规则：
1. 先生成相似点（共同特征）
2. 再生成差异对（对比特征）
3. 适合K12教学场景
4. 语言简洁清晰"""
            
            user_prompt = f"""为以下双气泡图生成{count}个对比建议：
左侧主题：{left_topic}
右侧主题：{right_topic}
教学背景：{educational_context.get('raw_message', '通用教学')}

请生成{count}个建议（相似点和差异对混合）："""
        else:
            system_prompt = """You are a K12 education expert. Generate comparison suggestions for Double Bubble Map.

Output one JSON object per line:
{"type": "similarity", "text": "shared attribute"}
or
{"type": "difference", "left": "left attribute", "right": "right attribute"}

Generation rules:
1. Generate similarities (shared features) first
2. Then generate difference pairs (contrasting features)
3. Suitable for K12 teaching scenarios
4. Keep language clear and concise"""
            
            user_prompt = f"""Generate {count} comparison suggestions for this Double Bubble Map:
Left topic: {left_topic}
Right topic: {right_topic}
Educational context: {educational_context.get('raw_message', 'General teaching')}

Please generate {count} suggestions (mix of similarities and differences):"""
        
        # Stream node suggestions from LLM
        try:
            combined_prompt = f"{system_prompt}\n\n{user_prompt}"
            async for chunk in self._stream_llm_response(combined_prompt, session):
                yield chunk
                
        except Exception as e:
            logger.error(f"[DoubleBubbleMapAgent] Node generation failed: {e}")
            yield {
                'event': 'error',
                'message': str(e)
            }


