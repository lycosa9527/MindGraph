"""
Mind Maps Prompts

This module contains prompts for mind maps and related diagrams.
"""

# ============================================================================
# MIND MAP PROMPTS
# ============================================================================

MINDMAP_GENERATION_EN = """
Please generate a JSON specification for a mind map for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
topic: "Topic"
children: [{{"name": "Subtopic1", "children": [{{"name": "Subtopic1.1"}}]}}]

Please ensure the JSON format is correct, do not include any code block markers.
"""

MINDMAP_GENERATION_ZH = """
请为以下用户需求生成一个思维导图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
topic: "主题"
children: [{{"name": "子主题1", "children": [{{"name": "子主题1.1"}}]}}]

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# RADIAL MIND MAP PROMPTS
# ============================================================================

RADIAL_MINDMAP_GENERATION_EN = """
Please generate a JSON specification for a radial mind map for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
topic: "Central topic"
branches: [{{"name": "Branch1", "children": [{{"name": "Branch1.1"}}]}}]

Please ensure the JSON format is correct, do not include any code block markers.
"""

RADIAL_MINDMAP_GENERATION_ZH = """
请为以下用户需求生成一个径向思维导图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
topic: "中心主题"
branches: [{{"name": "分支1", "children": [{{"name": "分支1.1"}}]}}]

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# PROMPT REGISTRY
# ============================================================================

MIND_MAP_PROMPTS = {
    "mindmap_generation_en": MINDMAP_GENERATION_EN,
    "mindmap_generation_zh": MINDMAP_GENERATION_ZH,
    "radial_mindmap_generation_en": RADIAL_MINDMAP_GENERATION_EN,
    "radial_mindmap_generation_zh": RADIAL_MINDMAP_GENERATION_ZH,
} 