"""
Prompt to Diagram Agent Prompts

This module contains prompts for direct prompt-to-diagram generation using a single LLM call.
Used by simplified endpoints that need fast, efficient diagram generation.

All diagram specs are imported from their source modules (thinking_maps, mind_maps,
concept_maps) to ensure consistency with specialized agents used by /api/generate_graph.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from prompts.concept_maps import (
    CONCEPT_MAP_GENERATION_EN,
    CONCEPT_MAP_GENERATION_ZH,
)
from prompts.mind_maps import (
    MIND_MAP_AGENT_GENERATION_EN,
    MIND_MAP_AGENT_GENERATION_ZH,
)
from prompts.thinking_maps import (
    BRACE_MAP_GENERATION_EN,
    BRACE_MAP_GENERATION_ZH,
    BRIDGE_MAP_GENERATION_EN,
    BRIDGE_MAP_GENERATION_ZH,
    BUBBLE_MAP_GENERATION_EN,
    BUBBLE_MAP_GENERATION_ZH,
    CIRCLE_MAP_GENERATION_EN,
    CIRCLE_MAP_GENERATION_ZH,
    DOUBLE_BUBBLE_MAP_GENERATION_EN,
    DOUBLE_BUBBLE_MAP_GENERATION_ZH,
    FLOW_MAP_GENERATION_EN,
    FLOW_MAP_GENERATION_ZH,
    MULTI_FLOW_MAP_GENERATION_EN,
    MULTI_FLOW_MAP_GENERATION_ZH,
    TREE_MAP_GENERATION_EN,
    TREE_MAP_GENERATION_ZH,
)


def _escape_braces_for_format(text: str, preserve_user_prompt: bool = False) -> str:
    """Escape { } for Python format(), optionally preserving {user_prompt}."""
    if preserve_user_prompt:
        placeholder = "\x00USER_PROMPT_PLACEHOLDER\x00"
        text = text.replace("{user_prompt}", placeholder)
    text = text.replace("{", "{{").replace("}", "}}")
    if preserve_user_prompt:
        text = text.replace(placeholder, "{user_prompt}")
    return text


# ============================================================================
# COMMON SECTIONS - Shared across all prompts
# ============================================================================

# Classification examples - distinguishing diagram type vs topic content
CLASSIFICATION_EXAMPLES_EN = """IMPORTANT: Distinguish between the diagram type the user wants vs the topic content
- "generate a bubble map about double bubble maps" → user wants bubble_map, topic is about double bubble maps → bubble_map
- "generate a bubble map about mind maps" → user wants bubble_map, topic is about mind maps → bubble_map
- "generate a mind map about concept maps" → user wants mind_map, topic is about concept maps → mind_map
- "generate a concept map about mind maps" → user wants concept_map, topic is about mind maps → concept_map
- "generate a double bubble map comparing apples and oranges" → user wants double_bubble_map → double_bubble_map
- "generate a bridge map showing learning is like building" → user wants bridge_map → bridge_map
- "generate a tree map for animal classification" → user wants tree_map → tree_map
- "generate a circle map defining climate change" → user wants circle_map → circle_map
- "generate a multi-flow map analyzing lamp explosion" → user wants multi_flow_map → multi_flow_map
- "generate a flow map showing coffee making steps" → user wants flow_map → flow_map
- "generate a brace map breaking down computer parts" → user wants brace_map → brace_map"""

CLASSIFICATION_EXAMPLES_ZH = """重要：区分用户想要创建的图表类型 vs 图表内容主题
- "生成一个关于双气泡图的气泡图" → 用户要创建气泡图，主题是双气泡图 → bubble_map
- "生成一个关于思维导图的气泡图" → 用户要创建气泡图，主题是思维导图 → bubble_map
- "生成一个关于概念图的思维导图" → 用户要创建思维导图，主题是概念图 → mind_map
- "生成一个关于思维导图的概念图" → 用户要创建概念图，主题是思维导图 → concept_map
- "生成一个双气泡图比较苹果和橙子" → 用户要创建双气泡图 → double_bubble_map
- "生成一个桥形图说明学习像建筑" → 用户要创建桥形图 → bridge_map
- "生成一个树形图展示动物分类" → 用户要创建树形图 → tree_map
- "生成一个圆圈图定义气候变化" → 用户要创建圆圈图 → circle_map
- "生成一个复流程图分析酒精灯爆炸" → 用户要创建复流程图 → multi_flow_map
- "生成一个流程图展示制作咖啡步骤" → 用户要创建流程图 → flow_map
- "生成一个括号图分解电脑组成部分" → 用户要创建括号图 → brace_map"""

# Diagram type definitions
DIAGRAM_TYPES_EN = """Available diagram types:
1. bubble_map (Bubble Map) - describing attributes, characteristics, features
2. bridge_map (Bridge Map) - analogies, comparing similarities between concepts
3. tree_map (Tree Map) - classification, hierarchy, organizational structure
4. circle_map (Circle Map) - association, generating related information around the central topic
5. double_bubble_map (Double Bubble Map) - comparing and contrasting two things
6. multi_flow_map (Multi-Flow Map) - cause-effect relationships, multiple causes and effects
7. flow_map (Flow Map) - step sequences, process flows
8. brace_map (Brace Map) - decomposing the central topic, whole-to-part relationships
9. concept_map (Concept Map) - relationship networks between concepts
10. mind_map (Mind Map) - divergent thinking, brainstorming"""

DIAGRAM_TYPES_ZH = """可用的图表类型：
1. bubble_map (气泡图) - 描述事物的属性、特征、特点
2. bridge_map (桥形图) - 通过类比来理解新概念
3. tree_map (树形图) - 分类、层次结构、组织架构
4. circle_map (圆圈图) - 联想，围绕中心主题生成相关的信息
5. double_bubble_map (双气泡图) - 对比两个事物的异同
6. multi_flow_map (复流程图) - 因果关系、事件的多重原因和结果
7. flow_map (流程图) - 步骤序列、过程流程
8. brace_map (括号图) - 对中心词进行拆分，整体与部分的关系
9. concept_map (概念图) - 概念间的关系网络
10. mind_map (思维导图) - 发散思维、头脑风暴"""

# Edge cases and decision logic
EDGE_CASES_EN = """Edge Cases and Decision Logic:
- If user intent is unclear or ambiguous, prefer mind_map (most versatile)
- If multiple types could fit, choose the most specific one
- If user mentions "chart", "graph", or "diagram" without specifics, analyze the content intent
- If user wants to compare/contrast two things, use double_bubble_map
- If user wants to show causes and effects, use multi_flow_map
- If user wants to show steps or processes, use flow_map"""

EDGE_CASES_ZH = """边缘情况和决策逻辑：
- 如果用户意图不明确或模糊，优先选择 mind_map（最通用）
- 如果多个类型都适用，选择最具体的那个
- 如果用户提到"图表"、"图形"或"图"但没有具体说明，分析内容意图
- 如果用户想要对比两个事物，使用 double_bubble_map
- 如果用户想要显示因果关系，使用 multi_flow_map
- 如果用户想要显示步骤或流程，使用 flow_map"""

# JSON output format template
JSON_FORMAT_TEMPLATE = """{{
  "diagram_type": "{diagram_type_placeholder}",
  "spec": {{
    // Diagram-specific structure based on diagram_type
    // See examples below for each type
  }}
}}"""

# Critical requirements
CRITICAL_REQUIREMENTS_EN = """CRITICAL Requirements:
- Output ONLY valid JSON - no explanations, no code blocks, no markdown
- Determine diagram type based on user intent (comparison → double_bubble_map, process → flow_map, etc.)
- Generate appropriate number of items for each diagram type (see specifications above)
- Keep text concise (1-8 words per item depending on diagram type)
- Ensure JSON is valid and complete
- Follow all specific requirements for each diagram type

Return ONLY the JSON object, nothing else."""

CRITICAL_REQUIREMENTS_ZH = """关键要求：
- 仅输出有效的JSON - 不要解释，不要代码块，不要markdown
- 根据用户意图确定图表类型（比较 → double_bubble_map，过程 → flow_map等）
- 为每种图表类型生成适当数量的项目（参见上面的规范）
- 保持文本简洁（根据图表类型，每个项目1-8个词）
- 确保JSON有效且完整
- 遵循每种图表类型的所有具体要求

仅返回JSON对象，不要其他内容。"""

# ============================================================================
# DIAGRAM TYPE SPECIFICATIONS - Individual specs for each diagram type
# ============================================================================

# Bubble Map - use same prompts as BubbleMapAgent
BUBBLE_MAP_SPEC_EN = "1. bubble_map:\n" + _escape_braces_for_format(BUBBLE_MAP_GENERATION_EN)
BUBBLE_MAP_SPEC_ZH = "1. bubble_map:\n" + _escape_braces_for_format(BUBBLE_MAP_GENERATION_ZH)

# Circle Map - use same prompts as CircleMapAgent
CIRCLE_MAP_SPEC_EN = "2. circle_map:\n" + _escape_braces_for_format(CIRCLE_MAP_GENERATION_EN)
CIRCLE_MAP_SPEC_ZH = "2. circle_map:\n" + _escape_braces_for_format(CIRCLE_MAP_GENERATION_ZH)

# Double Bubble Map - use same prompts as DoubleBubbleMapAgent
DOUBLE_BUBBLE_MAP_SPEC_EN = "3. double_bubble_map:\n" + _escape_braces_for_format(DOUBLE_BUBBLE_MAP_GENERATION_EN)
DOUBLE_BUBBLE_MAP_SPEC_ZH = "3. double_bubble_map:\n" + _escape_braces_for_format(DOUBLE_BUBBLE_MAP_GENERATION_ZH)

# Brace Map - use same prompts as BraceMapAgent
BRACE_MAP_SPEC_EN = "4. brace_map:\n" + _escape_braces_for_format(BRACE_MAP_GENERATION_EN)
BRACE_MAP_SPEC_ZH = "4. brace_map:\n" + _escape_braces_for_format(BRACE_MAP_GENERATION_ZH)

# Bridge Map - use same prompts as BridgeMapAgent
BRIDGE_MAP_SPEC_EN = "5. bridge_map:\n" + _escape_braces_for_format(BRIDGE_MAP_GENERATION_EN)
BRIDGE_MAP_SPEC_ZH = "5. bridge_map:\n" + _escape_braces_for_format(BRIDGE_MAP_GENERATION_ZH)

# Tree Map - use same prompts as TreeMapAgent
TREE_MAP_SPEC_EN = "6. tree_map:\n" + _escape_braces_for_format(TREE_MAP_GENERATION_EN)
TREE_MAP_SPEC_ZH = "6. tree_map:\n" + _escape_braces_for_format(TREE_MAP_GENERATION_ZH)

# Flow Map - use same prompts as FlowMapAgent
FLOW_MAP_SPEC_EN = "7. flow_map:\n" + _escape_braces_for_format(FLOW_MAP_GENERATION_EN)
FLOW_MAP_SPEC_ZH = "7. flow_map:\n" + _escape_braces_for_format(FLOW_MAP_GENERATION_ZH)

# Multi-Flow Map - use same prompts as MultiFlowMapAgent
MULTI_FLOW_MAP_SPEC_EN = "8. multi_flow_map:\n" + _escape_braces_for_format(MULTI_FLOW_MAP_GENERATION_EN)
MULTI_FLOW_MAP_SPEC_ZH = "8. multi_flow_map:\n" + _escape_braces_for_format(MULTI_FLOW_MAP_GENERATION_ZH)

# Mind Map - use same prompts as MindMapAgent
MIND_MAP_SPEC_EN = "9. mind_map:\n" + _escape_braces_for_format(MIND_MAP_AGENT_GENERATION_EN)
MIND_MAP_SPEC_ZH = "9. mind_map:\n" + _escape_braces_for_format(MIND_MAP_AGENT_GENERATION_ZH)

# Concept Map - use same prompts as ConceptMapAgent (preserve {user_prompt})
CONCEPT_MAP_SPEC_EN = "10. concept_map:\n" + _escape_braces_for_format(CONCEPT_MAP_GENERATION_EN, preserve_user_prompt=True)
CONCEPT_MAP_SPEC_ZH = "10. concept_map:\n" + _escape_braces_for_format(CONCEPT_MAP_GENERATION_ZH, preserve_user_prompt=True)

# ============================================================================
# PROMPT BUILDERS - Functions to assemble complete prompts
# ============================================================================

def _build_diagram_specs_section(language: str) -> str:
    """Build the diagram specifications section for a given language."""
    specs = {
        'en': [
            BUBBLE_MAP_SPEC_EN,
            CIRCLE_MAP_SPEC_EN,
            DOUBLE_BUBBLE_MAP_SPEC_EN,
            BRACE_MAP_SPEC_EN,
            BRIDGE_MAP_SPEC_EN,
            TREE_MAP_SPEC_EN,
            FLOW_MAP_SPEC_EN,
            MULTI_FLOW_MAP_SPEC_EN,
            MIND_MAP_SPEC_EN,
            CONCEPT_MAP_SPEC_EN,
        ],
        'zh': [
            BUBBLE_MAP_SPEC_ZH,
            CIRCLE_MAP_SPEC_ZH,
            DOUBLE_BUBBLE_MAP_SPEC_ZH,
            BRACE_MAP_SPEC_ZH,
            BRIDGE_MAP_SPEC_ZH,
            TREE_MAP_SPEC_ZH,
            FLOW_MAP_SPEC_ZH,
            MULTI_FLOW_MAP_SPEC_ZH,
            MIND_MAP_SPEC_ZH,
            CONCEPT_MAP_SPEC_ZH,
        ],
    }
    return "\n\n".join(specs.get(language, specs['en']))


def _build_prompt(language: str) -> str:
    """Build the complete prompt for a given language."""
    # Select language-specific components
    if language == 'zh':
        task_header = """你是一名专业的图表生成助手。分析用户的提示，在一步中生成完整的图表规范。

你的任务：
1. 从用户的意图中确定图表类型
2. 提取主要主题/概念
3. 生成完整的图表规范"""
        classification_examples = CLASSIFICATION_EXAMPLES_ZH
        diagram_types = DIAGRAM_TYPES_ZH
        edge_cases = EDGE_CASES_ZH
        json_format_instruction = """分析提示并生成相应的图表规范。仅返回有效的JSON格式："""
        critical_requirements = CRITICAL_REQUIREMENTS_ZH
    else:
        task_header = """You are an expert diagram generation assistant. Analyze the user's prompt and generate a complete diagram specification in ONE step.

Your task:
1. Determine the diagram type from the user's intent
2. Extract the main topic/concept
3. Generate the complete diagram specification"""
        classification_examples = CLASSIFICATION_EXAMPLES_EN
        diagram_types = DIAGRAM_TYPES_EN
        edge_cases = EDGE_CASES_EN
        json_format_instruction = """Analyze the prompt and generate the appropriate diagram specification. Return ONLY valid JSON in this format:"""
        critical_requirements = CRITICAL_REQUIREMENTS_EN

    # Build the complete prompt
    prompt_parts = [
        task_header,
        "",
        classification_examples,
        "",
        diagram_types,
        "",
        edge_cases,
        "",
        'User prompt: "{user_prompt}"',
        "",
        json_format_instruction,
        "",
        JSON_FORMAT_TEMPLATE.replace("{diagram_type_placeholder}", "detected_diagram_type"),
        "",
        "Diagram Type Specifications:",
        "",
        _build_diagram_specs_section(language),
        "",
        critical_requirements,
    ]

    return "\n".join(prompt_parts)


# ============================================================================
# EXPORTED PROMPTS - Main prompt constants
# ============================================================================

PROMPT_TO_DIAGRAM_EN = _build_prompt('en')
PROMPT_TO_DIAGRAM_ZH = _build_prompt('zh')

# Prompt registry
PROMPT_TO_DIAGRAM_PROMPTS = {
    'prompt_to_diagram_en': PROMPT_TO_DIAGRAM_EN,
    'prompt_to_diagram_zh': PROMPT_TO_DIAGRAM_ZH,
}
