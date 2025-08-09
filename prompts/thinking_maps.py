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
  {
    "left": "First item in analogy pair",
    "right": "Second item in analogy pair",
    "id": 0
  },
  {
    "left": "First item in analogy pair", 
    "right": "Second item in analogy pair",
    "id": 1
  }
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
  {
    "left": "类比对中的第一项",
    "right": "类比对中的第二项", 
    "id": 0
  },
  {
    "left": "类比对中的第一项",
    "right": "类比对中的第二项", 
    "id": 1
  }
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

Output a SINGLE JSON object with the following fields (example shown below):
- topic: "Main topic"
- children: [
  {{"id": "category-1", "label": "Category 1", "children": [
    {{"id": "item-1", "label": "Item 1"}},
    {{"id": "item-2", "label": "Item 2"}}
  ]}},
  {{"id": "category-2", "label": "Category 2", "children": [
    {{"id": "item-a", "label": "Item A"}}
  ]}}
]

Strict requirements:
- Top-level children: generate 4–6 categories under "children" (each a short phrase, 1–5 words)
- For EACH top-level child, generate 2–6 sub-children in its "children" array (short phrases, 1–5 words)
- Use concise phrases only; no punctuation; no numbering prefixes; avoid full sentences
- All labels must be unique and non-redundant
- Do not include extra fields beyond topic, children, id, label

Return only valid JSON. Do NOT include code block markers.
"""

TREE_MAP_GENERATION_ZH = """
请为以下用户需求生成一个树形图的JSON规范。

需求：{user_prompt}

输出且仅输出一个JSON对象，包含以下字段（示例如下）：
- topic: "主题"
- children: [
  {{"id": "category-1", "label": "类别一", "children": [
    {{"id": "item-1", "label": "条目一"}},
    {{"id": "item-2", "label": "条目二"}}
  ]}},
  {{"id": "category-2", "label": "类别二", "children": [
    {{"id": "item-a", "label": "条目甲"}}
  ]}}
]

严格要求：
- 顶层 children：生成 4–6 个类别（短语，1–5 个词/字）
- 每个顶层 child 的 "children" 数组：生成 2–6 个子项（短语，1–5 个词/字）
- 仅用简短短语；不要标点；不要编号前缀；不要完整句子
- 所有标签必须唯一且不冗余
- 不要包含 topic、children、id、label 之外的字段

只返回有效 JSON，不要包含代码块标记。
"""

# ============================================================================
# FLOW MAP PROMPTS
# ============================================================================

FLOW_MAP_GENERATION_EN = """
Please generate a JSON specification for a flow map with MAJOR steps and SUB-STEPS for the following user request.

Request: {user_prompt}

Output a SINGLE JSON object with the following fields:
- title: "Main topic"
- steps: ["Major step 1", "Major step 2", "Major step 3"]
- substeps: [
  {"step": "Major step 1", "substeps": ["Sub-step A", "Sub-step B"]},
  {"step": "Major step 2", "substeps": ["Sub-step A", "Sub-step B"]}
]

Definitions and intent:
- Steps (major steps): high-level phases that keep the flow neat, clean, and professional. They should read like milestones or stage names, and each one should GENERALIZE its own sub-steps.
- Sub-steps: concrete, detailed actions that explain how each step is carried out. They provide depth without cluttering the main flow and must be logically contained by their step.

Strict requirements:
- Steps: 3–8 items, each a concise phrase (1–6 words), no punctuation, no full sentences, no numbering prefixes.
- Sub-steps: for each step, generate 1–5 detailed actions (1–7 words), no punctuation, avoid repeating the step text.
- Each step must be a category/abstraction that GENERALIZES all its sub-steps. If any sub-steps introduce a new theme not covered by existing steps, add or adjust a step to cover it.
- Do not include sub-steps that simply restate the step; add specific details (at least one key term not present in the step).
- Keep all items unique and non-redundant; avoid explanatory clauses.
- The steps array must contain ONLY strings.
- The substeps array must contain objects with fields "step" (string exactly matching a value in steps) and "substeps" (array of strings).
- If the user provides partial steps, respect their order and fill gaps sensibly.

Return only valid JSON. Do NOT include code block markers.
"""

FLOW_MAP_GENERATION_ZH = """
请为以下用户需求生成一个包含“主要步骤”和“子步骤”的流程图JSON规范。

需求：{user_prompt}

输出一个且仅一个JSON对象，包含以下字段：
- title: "主题"
- steps: ["主要步骤1", "主要步骤2", "主要步骤3"]
- substeps: [
  {"step": "主要步骤1", "substeps": ["子步骤A", "子步骤B"]},
  {"step": "主要步骤2", "substeps": ["子步骤A", "子步骤B"]}
]

定义与意图：
- 主要步骤（steps）：高层级阶段，用于保持流程图整洁、专业，类似里程碑或阶段名称；且每个主要步骤应当能够“概括/泛化”其所属的所有子步骤。
- 子步骤（sub-steps）：具体执行动作，用于说明“如何做”，提供细节但不让主流程拥挤；子步骤必须逻辑上被其对应的主要步骤“包含”。

严格要求：
- 主要步骤：3–8项，短语（1–6个词/字），不用标点，不写完整句子，不加编号前缀。
- 子步骤：每个主要步骤生成1–5项，短语（1–7个词/字），不用标点，避免重复主要步骤的措辞。
- 每个主要步骤必须能够“概括/泛化”其子步骤。如果某些子步骤引入了现有步骤未覆盖的新主题，请新增或调整主要步骤以覆盖之。
- 不要生成仅仅复述主要步骤的子步骤；必须加入具体细节（至少包含主要步骤中未出现的关键词）。
- 保持内容唯一、具体、不重复；避免解释性从句。
- steps 数组仅包含字符串。
- substeps 数组必须包含对象，且对象含有 "step"（与 steps 中某项完全一致）与 "substeps"（字符串数组）。
- 若用户提供了部分步骤，按其顺序补全并保持合理性。

只返回有效JSON，不要包含代码块标记。
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

Requirements:
- Generate 3-6 main parts with clear, descriptive names
- Each part should have 2-5 subparts that are specific and detailed
- Use concise, clear language - avoid long sentences
- Ensure logical whole-to-part relationships (whole → parts → subparts)
- Parts should be major categories or divisions of the topic
- Subparts should be specific components, features, or elements of each part

Do not include any information about visual layout or braces; only provide the hierarchical data.

Please ensure the JSON format is correct, do not include any code block markers.
"""

BRACE_MAP_GENERATION_ZH = """
请为以下用户需求生成一个括号图（Brace Map）的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
topic: "主题"
parts: [{{"name": "部分1", "subparts": [{{"name": "子部分1.1"}}]}}]

要求：
- 生成3-6个主要部分，名称清晰、描述性强
- 每个部分应有2-5个子部分，具体且详细
- 使用简洁、清晰的语言，避免长句
- 确保逻辑的整体→部分→子部分关系
- 部分应为主题的主要类别或分支
- 子部分应为每个部分的具体组件、特征或元素

不要包含任何关于可视化布局或括号形状的说明；只提供层级数据。

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

Requirements:
- Use concise key descriptions (1–8 words) for each item
- Prefer nouns or short noun phrases; avoid full sentences and punctuation
- Keep items focused and non-redundant; no explanatory clauses

Please ensure the JSON format is correct, do not include any code block markers.
"""

MULTI_FLOW_MAP_GENERATION_ZH = """
请为以下用户需求生成一个复流程图的JSON规范。

需求：{user_prompt}

请输出一个包含以下字段的JSON对象：
event: "中心事件"
causes: ["原因1", "原因2", "原因3", "原因4"]
effects: ["结果1", "结果2", "结果3", "结果4"]

要求：
- 每项使用关键描述，尽量简短（1–8个词/字）
- 优先使用名词或短名词短语；避免完整句子与标点
- 内容聚焦且不重复，不要解释性从句

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