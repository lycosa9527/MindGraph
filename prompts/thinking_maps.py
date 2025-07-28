"""
Thinking Maps Prompts

This module contains all prompts for the 8 Thinking Maps®:
1. Circle Map - Define topics in context
2. Bubble Map - Describe attributes and characteristics  
3. Double Bubble Map - Compare and contrast two topics
4. Tree Map - Categorize and classify information
5. Brace Map - Show whole/part relationships
6. Flow Map - Sequence events and processes
7. Multi-Flow Map - Analyze cause and effect relationships
8. Bridge Map - Show analogies and similarities
"""

# ============================================================================
# BRIDGE MAP PROMPTS
# ============================================================================

BRIDGE_MAP_GENERATION_EN = """
Please generate a JSON specification for a bridge map for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
relating_factor: "as" (fixed relationship identifier)
analogies: [
  {{
    "left": "First item in analogy pair",
    "right": "Second item in analogy pair",
    "id": 0
  }},
  {{
    "left": "First item in analogy pair", 
    "right": "Second item in analogy pair",
    "id": 1
  }}
]

Requirements:
- Generate 4-6 analogy pairs in the format a:b, c:d, e:f, etc.
- Each analogy pair should demonstrate the same relating factor
- The relating factor is fixed as "as" (standard bridge map format)
- Analogy pairs should have educational value and learning significance
- Use AT LEAST WORDS AS POSSIBLE - single words or very short phrases only
- Avoid complete sentences, long descriptions, or multiple words when one word suffices
- Ensure analogy relationships are logically clear and easy to understand
- Cover diverse fields and concepts, showing interdisciplinary connections
- Each analogy should have a unique id starting from 0

Please ensure the JSON format is correct, do not include any code block markers.
"""

BRIDGE_MAP_GENERATION_ZH = """
请为以下用户需求生成一个桥形图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
relating_factor: "as" (固定关系标识符)
analogies: [
  {{
    "left": "类比对中的第一项",
    "right": "类比对中的第二项", 
    "id": 0
  }},
  {{
    "left": "类比对中的第一项",
    "right": "类比对中的第二项", 
    "id": 1
  }}
]

要求：
- 生成4-6个类比关系对，格式为 a:b, c:d, e:f 等
- 每个类比对应该展示相同的关联因子
- 关联因子固定为 "as" (标准桥形图格式)
- 类比对应该具有教育价值和学习意义
- 使用尽可能少的词汇 - 仅使用单个词汇或极短短语
- 避免完整句子、长描述，或在单个词汇足够时使用多个词汇
- 确保类比关系逻辑清晰，易于理解
- 涵盖不同领域和概念，展示跨学科联系
- 每个类比都应该有一个从0开始的唯一id

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# BUBBLE MAP PROMPTS
# ============================================================================

BUBBLE_MAP_GENERATION_EN = """
Please generate a JSON specification for a bubble map for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
topic: "Topic"
attributes: ["Feature1", "Feature2", "Feature3", "Feature4", "Feature5", "Feature6", "Feature7", "Feature8"]

Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences.

Please ensure the JSON format is correct, do not include any code block markers.
"""

BUBBLE_MAP_GENERATION_ZH = """
请为以下用户需求生成一个气泡图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
topic: "主题"
attributes: ["特征1", "特征2", "特征3", "特征4", "特征5", "特征6", "特征7", "特征8"]

要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# DOUBLE BUBBLE MAP PROMPTS
# ============================================================================

DOUBLE_BUBBLE_MAP_GENERATION_EN = """
Please generate a JSON specification for a double bubble map for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
left: "Topic1"
right: "Topic2"
similarities: ["Feature1", "Feature2", "Feature3", "Feature4", "Feature5"]
left_differences: ["Feature1", "Feature2", "Feature3", "Feature4", "Feature5"]
right_differences: ["Feature1", "Feature2", "Feature3", "Feature4", "Feature5"]

Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences.

Please ensure the JSON format is correct, do not include any code block markers.
"""

DOUBLE_BUBBLE_MAP_GENERATION_ZH = """
请为以下用户需求生成一个双气泡图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
left: "主题1"
right: "主题2"
similarities: ["特征1", "特征2", "特征3", "特征4", "特征5"]
left_differences: ["特点1", "特点2", "特点3", "特点4", "特点5"]
right_differences: ["特点1", "特点2", "特点3", "特点4", "特点5"]

要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# CIRCLE MAP PROMPTS
# ============================================================================

CIRCLE_MAP_GENERATION_EN = """
Please generate a JSON specification for a circle map for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
topic: "Topic"
context: ["Feature1", "Feature2", "Feature3", "Feature4", "Feature5", "Feature6"]

Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences.

Please ensure the JSON format is correct, do not include any code block markers.
"""

CIRCLE_MAP_GENERATION_ZH = """
请为以下用户需求生成一个圆圈图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
topic: "主题"
context: ["特征1", "特征2", "特征3", "特征4", "特征5", "特征6"]

要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# TREE MAP PROMPTS
# ============================================================================

TREE_MAP_GENERATION_EN = """
Please generate a JSON specification for a tree map for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
topic: "Topic"
children: [{{"id": "subtopic1", "label": "Subtopic1", "children": [{{"id": "subtopic1.1", "label": "Subtopic1.1"}}]}}]

Please ensure the JSON format is correct, do not include any code block markers.
"""

TREE_MAP_GENERATION_ZH = """
请为以下用户需求生成一个树形图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
topic: "主题"
children: [{{"id": "subtopic1", "label": "子主题1", "children": [{{"id": "subtopic1.1", "label": "子主题1.1"}}]}}]

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# FLOW MAP PROMPTS
# ============================================================================

FLOW_MAP_GENERATION_EN = """
Please generate a JSON specification for a flow map for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
title: "Main topic"
steps: ["Step1", "Step2", "Step3", "Step4", "Step5"]

Please ensure the JSON format is correct, do not include any code block markers.
"""

FLOW_MAP_GENERATION_ZH = """
请为以下用户需求生成一个流程图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
title: "主题"
steps: ["步骤1", "步骤2", "步骤3", "步骤4", "步骤5"]

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# BRACE MAP PROMPTS
# ============================================================================

BRACE_MAP_GENERATION_EN = """
Please generate a JSON specification for a brace map for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
topic: "Main topic"
parts: [{{"name": "Part1", "subparts": [{{"name": "Subpart1.1"}}]}}]

Please ensure the JSON format is correct, do not include any code block markers.
"""

BRACE_MAP_GENERATION_ZH = """
请为以下用户需求生成一个括号图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
topic: "主题"
parts: [{{"name": "部分1", "subparts": [{{"name": "子部分1.1"}}]}}]

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# MULTI-FLOW MAP PROMPTS
# ============================================================================

MULTI_FLOW_MAP_GENERATION_EN = """
Please generate a JSON specification for a multi-flow map for the following user request.

Request: {user_prompt}

Please output a JSON object containing the following fields:
event: "Central event"
causes: ["Cause1", "Cause2", "Cause3", "Cause4"]
effects: ["Effect1", "Effect2", "Effect3", "Effect4"]

Please ensure the JSON format is correct, do not include any code block markers.
"""

MULTI_FLOW_MAP_GENERATION_ZH = """
请为以下用户需求生成一个多重流程图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
event: "中心事件"
causes: ["原因1", "原因2", "原因3", "原因4"]
effects: ["结果1", "结果2", "结果3", "结果4"]

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# PROMPT REGISTRY
# ============================================================================

THINKING_MAP_PROMPTS = {
    # Bridge Map
    "bridge_map_generation_en": BRIDGE_MAP_GENERATION_EN,
    "bridge_map_generation_zh": BRIDGE_MAP_GENERATION_ZH,
    
    # Bubble Map
    "bubble_map_generation_en": BUBBLE_MAP_GENERATION_EN,
    "bubble_map_generation_zh": BUBBLE_MAP_GENERATION_ZH,
    
    # Double Bubble Map
    "double_bubble_map_generation_en": DOUBLE_BUBBLE_MAP_GENERATION_EN,
    "double_bubble_map_generation_zh": DOUBLE_BUBBLE_MAP_GENERATION_ZH,
    
    # Circle Map
    "circle_map_generation_en": CIRCLE_MAP_GENERATION_EN,
    "circle_map_generation_zh": CIRCLE_MAP_GENERATION_ZH,
    
    # Tree Map
    "tree_map_generation_en": TREE_MAP_GENERATION_EN,
    "tree_map_generation_zh": TREE_MAP_GENERATION_ZH,
    
    # Flow Map
    "flow_map_generation_en": FLOW_MAP_GENERATION_EN,
    "flow_map_generation_zh": FLOW_MAP_GENERATION_ZH,
    
    # Brace Map
    "brace_map_generation_en": BRACE_MAP_GENERATION_EN,
    "brace_map_generation_zh": BRACE_MAP_GENERATION_ZH,
    
    # Multi-Flow Map
    "multi_flow_map_generation_en": MULTI_FLOW_MAP_GENERATION_EN,
    "multi_flow_map_generation_zh": MULTI_FLOW_MAP_GENERATION_ZH,
} 