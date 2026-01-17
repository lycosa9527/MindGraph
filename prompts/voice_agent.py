"""
Voice Agent Prompts

This module contains prompts used by the voice agent for:
- Paragraph processing and content extraction
- Intent detection and diagram type recommendation

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

# Paragraph processing prompt for Qwen Plus (English)
PARAGRAPH_PROCESSING_EN = """You are an intelligent diagram assistant. A teacher has provided a paragraph of text. Your task is to:

1. **Understand what the teacher wants**:
   - Do they want to extract content for a diagram?
   - Do they want to generate a new diagram from scratch?
   - Do they want to update/enhance an existing diagram?
   - What is the main intent?

2. **Determine the best diagram type** (if not already specified or if current type doesn't fit):
   Available diagram types:
   - circle_map: For defining concepts in context (observations, examples, characteristics)
   - bubble_map: For describing attributes/characteristics of a topic
   - tree_map: For classifying/categorizing information
   - flow_map: For sequential processes/steps
   - multi_flow_map: For cause-and-effect relationships
   - double_bubble_map: For comparing two topics (similarities and differences)
   - brace_map: For whole-to-parts relationships
   - bridge_map: For analogies and relationships
   - mindmap: For brainstorming and hierarchical ideas
   - concept_map: For complex concept relationships

3. **Extract and structure content** based on the determined diagram type

【Paragraph Text】
{paragraph_text}

【Current Diagram State】
- Type: {current_diagram_type}
- Current Topic: {current_topic}
- Current Nodes: {current_nodes_count} nodes
- Has Existing Content: {has_existing_content}

【Your Task】
Analyze the paragraph and return a JSON response with:

{{
  "intent": "extract_content" | "generate_diagram" | "update_diagram" | "enhance_diagram",
  "recommended_diagram_type": "best diagram type for this content",
  "should_change_diagram_type": true/false (only if current type doesn't fit well),
  "topic": "Main topic extracted from paragraph" (or null if updating existing),
  "nodes": ["node1", "node2", ...] (extracted nodes appropriate for diagram type),
  "summary": "Brief explanation of what was extracted and why",
  "reasoning": "Why this diagram type fits the content"
}}

【Diagram Type Specific Fields】
- For double_bubble_map: Include "left_topic", "right_topic", "similarities", "left_differences", "right_differences"
- For flow_map: Use "title" instead of "topic", nodes are sequential steps
- For multi_flow_map: Use "event" instead of "topic", include "causes" and "effects" arrays
- For brace_map: Use "whole" instead of "topic", include "parts" array
- For bridge_map: Use "dimension" instead of "topic", include "analogies" array [{{"left": "...", "right": "..."}}]

【Important Guidelines】
- Analyze the content structure: Is it sequential? Comparative? Hierarchical? Descriptive?
- Match diagram type to content structure (e.g., process → flow_map, comparison → double_bubble_map)
- Extract actual content from paragraph, don't invent content
- Generate 5-15 nodes appropriate for the diagram type
- Keep node text concise (1-5 words each)
- If current diagram has content, determine if paragraph enhances it or replaces it
- If paragraph doesn't match current diagram type well, recommend a better type

Return ONLY valid JSON, no other text."""

# Paragraph processing prompt for Qwen Plus (Chinese)
PARAGRAPH_PROCESSING_ZH = """你是一个智能图表助手。老师提供了一段文本。你的任务是：

1. **理解老师的意图**：
   - 他们想要提取内容用于图表吗？
   - 他们想要从头生成新图表吗？
   - 他们想要更新/增强现有图表吗？
   - 主要意图是什么？

2. **确定最佳图表类型**（如果未指定或当前类型不合适）：
   可用的图表类型：
   - circle_map: 用于在上下文中定义概念（观察、例子、特征）
   - bubble_map: 用于描述主题的属性/特征
   - tree_map: 用于分类/归类信息
   - flow_map: 用于顺序过程/步骤
   - multi_flow_map: 用于因果关系
   - double_bubble_map: 用于比较两个主题（相似点和不同点）
   - brace_map: 用于整体到部分的关系
   - bridge_map: 用于类比和关系
   - mindmap: 用于头脑风暴和层次化想法
   - concept_map: 用于复杂的概念关系

3. **根据确定的图表类型提取和结构化内容**

【段落文本】
{paragraph_text}

【当前图表状态】
- 类型: {current_diagram_type}
- 当前主题: {current_topic}
- 当前节点: {current_nodes_count} 个节点
- 有现有内容: {has_existing_content}

【你的任务】
分析段落并返回JSON响应：

{{
  "intent": "extract_content" | "generate_diagram" | "update_diagram" | "enhance_diagram",
  "recommended_diagram_type": "最适合此内容的图表类型",
  "should_change_diagram_type": true/false（仅在当前类型不合适时）,
  "topic": "从段落中提取的主题"（如果更新现有则为null）,
  "nodes": ["节点1", "节点2", ...]（适合图表类型的提取节点）,
  "summary": "提取内容的简要说明及原因",
  "reasoning": "为什么此图表类型适合内容"
}}

【图表类型特定字段】
- 对于 double_bubble_map: 包含 "left_topic", "right_topic", "similarities", "left_differences", "right_differences"
- 对于 flow_map: 使用 "title" 而不是 "topic"，节点是顺序步骤
- 对于 multi_flow_map: 使用 "event" 而不是 "topic"，包含 "causes" 和 "effects" 数组
- 对于 brace_map: 使用 "whole" 而不是 "topic"，包含 "parts" 数组
- 对于 bridge_map: 使用 "dimension" 而不是 "topic"，包含 "analogies" 数组 [{{"left": "...", "right": "..."}}]

【重要指南】
- 分析内容结构：是顺序的？比较的？层次的？描述性的？
- 将图表类型与内容结构匹配（例如，过程 → flow_map，比较 → double_bubble_map）
- 从段落中提取实际内容，不要编造内容
- 生成5-15个适合图表类型的节点
- 保持节点文本简洁（每个1-5个词）
- 如果当前图表有内容，确定段落是增强还是替换它
- 如果段落与当前图表类型不匹配，推荐更好的类型

仅返回有效的JSON，不要其他文本。"""

# Export prompts dictionary following the pattern used in other prompt files
VOICE_AGENT_PROMPTS = {
    'paragraph_processing_en': PARAGRAPH_PROCESSING_EN,
    'paragraph_processing_zh': PARAGRAPH_PROCESSING_ZH,
}

