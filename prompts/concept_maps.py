"""
Concept Maps Prompts

This module contains prompts for concept maps and related diagrams.
"""

# ============================================================================
# CONCEPT MAP PROMPTS
# ============================================================================

CONCEPT_MAP_GENERATION_EN = """
Please generate a JSON specification for a concept map for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
topic: "Topic"
concepts: ["Concept1", "Concept2", "Concept3", "Concept4"]
relationships: [{{"from": "Concept1", "to": "Concept2", "label": "relates to"}}]

Please ensure the JSON format is correct, do not include any code block markers.
"""

CONCEPT_MAP_GENERATION_ZH = """
请为以下用户需求生成一个概念图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
topic: "主题"
concepts: ["概念1", "概念2", "概念3", "概念4"]
relationships: [{{"from": "概念1", "to": "概念2", "label": "关联"}}]

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# SEMANTIC WEB PROMPTS
# ============================================================================

SEMANTIC_WEB_GENERATION_EN = """
Please generate a JSON specification for a semantic web for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
topic: "Central concept"
branches: [{{"name": "Branch1", "children": [{{"name": "Branch1.1"}}]}}]

Please ensure the JSON format is correct, do not include any code block markers.
"""

SEMANTIC_WEB_GENERATION_ZH = """
请为以下用户需求生成一个语义网的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
topic: "中心概念"
branches: [{{"name": "分支1", "children": [{{"name": "分支1.1"}}]}}]

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# PROMPT REGISTRY
# ============================================================================

CONCEPT_MAP_PROMPTS = {
    "concept_map_generation_en": CONCEPT_MAP_GENERATION_EN,
    "concept_map_generation_zh": CONCEPT_MAP_GENERATION_ZH,
    "semantic_web_generation_en": SEMANTIC_WEB_GENERATION_EN,
    "semantic_web_generation_zh": SEMANTIC_WEB_GENERATION_ZH,
} 