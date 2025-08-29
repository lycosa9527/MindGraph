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

BRIDGE_MAP_GENERATION_EN = """Please generate a JSON specification for a bridge map for the following user request.

Request: {user_prompt}

CRITICAL REQUIREMENTS - READ CAREFULLY:
1. **ABSOLUTE UNIQUENESS**: Every element must appear EXACTLY ONCE on each side. NO DUPLICATES ALLOWED.
2. **Consistent Count**: Generate exactly 6 elements for each side (we'll use 5, keeping 1 as backup)
3. **Logical Relationships**: All analogies must demonstrate the same relationship pattern
4. **No Repetition**: Never repeat the same element, category, or similar concept on either side

FORMAT REQUIREMENTS:
- Use the EXACT structure shown below
- Generate exactly 6 analogy pairs (6 elements per side)
- Each element must be completely unique
- No variations of the same concept (e.g., don't use "China" and "Chinese" or "Beijing" and "Beijing City")

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
  },
  {
    "left": "First item in analogy pair",
    "right": "Second item in analogy pair", 
    "id": 2
  },
  {
    "left": "First item in analogy pair",
    "right": "Second item in analogy pair", 
    "id": 3
  },
  {
    "left": "First item in analogy pair",
    "right": "Second item in analogy pair", 
    "id": 4
  },
  {
    "left": "First item in analogy pair",
    "right": "Second item in analogy pair", 
    "id": 5
  }
]

VALIDATION CHECKLIST:
- [ ] Exactly 6 analogy pairs (6 elements per side)
- [ ] Each left element appears only once
- [ ] Each right element appears only once  
- [ ] No conceptual duplicates (e.g., "China" vs "Chinese")
- [ ] All analogies follow the same relationship pattern
- [ ] JSON format is valid and complete

Please ensure the JSON format is correct, do not include any code block markers."""

BRIDGE_MAP_GENERATION_ZH = """
请为以下用户需求生成一个桥形图的JSON规范。

需求：{user_prompt}

关键要求 - 请仔细阅读：
1. **绝对唯一性**：每个元素在每一边必须出现且仅出现一次。绝对不允许重复。
2. **数量一致**：每一边生成恰好6个元素（我们将使用5个，保留1个作为备用）
3. **逻辑关系**：所有类比必须展示相同的关系模式
4. **无重复**：永远不要在任一边重复相同的元素、类别或相似概念

格式要求：
- 使用下面显示的确切结构
- 生成恰好6个类比对（每边6个元素）
- 每个元素必须完全唯一
- 不要使用同一概念的变化形式（例如，不要使用"中国"和"中国的"或"北京"和"北京城"）

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
  },
  {
    "left": "类比对中的第一项",
    "right": "类比对中的第二项", 
    "id": 2
  },
  {
    "left": "类比对中的第一项",
    "right": "类比对中的第二项", 
    "id": 3
  },
  {
    "left": "类比对中的第一项",
    "right": "类比对中的第二项", 
    "id": 4
  },
  {
    "left": "类比对中的第一项",
    "right": "类比对中的第二项", 
    "id": 5
  }
]

验证清单：
- [ ] 恰好6个类比对（每边6个元素）
- [ ] 每个左侧元素只出现一次
- [ ] 每个右侧元素只出现一次
- [ ] 无概念重复（例如，"中国"与"中国的"）
- [ ] 所有类比遵循相同的关系模式
- [ ] JSON格式有效且完整

请确保JSON格式正确，不要包含任何代码块标记。"""

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

# ============================================================================
# AGENT-SPECIFIC PROMPTS (Currently being used by actual agents)
# ============================================================================

# From agents - these are the actual prompts being used
BUBBLE_MAP_AGENT_EN = """You are a professional mind mapping expert specializing in bubble maps. Bubble maps are used to describe attributes and characteristics of a single topic.

Please create a detailed bubble map specification based on the user's description. The output must be valid JSON with the following structure:

{
  "topic": "Central Topic",
  "attributes": [
    {
      "id": "attr1",
      "text": "Attribute 1",
      "category": "Category 1"
    }
  ],
  "connections": [
    {
      "from": "topic",
      "to": "attr1",
      "label": "Relationship Label"
    }
  ]
}

Requirements:
- Central topic should be clear and specific
- Attributes should be concrete and meaningful
- Each attribute should have a clear connection to the central topic
- Use concise but descriptive text
- Ensure the JSON format is completely valid"""

BUBBLE_MAP_AGENT_ZH = """你是一个专业的思维导图专家，专门创建气泡图。气泡图用于描述单个主题的特征和属性。

请根据用户的描述，创建一个详细的气泡图规范。输出必须是有效的JSON格式，包含以下结构：

{
  "topic": "中心主题",
  "attributes": [
    {
      "id": "attr1",
      "text": "属性1",
      "category": "类别1"
    }
  ],
  "connections": [
    {
      "from": "topic",
      "to": "attr1",
      "label": "关系标签"
    }
  ]
}

要求：
- 中心主题应该清晰明确
- 属性应该具体且有意义
- 每个属性都应该与中心主题有明确的连接
- 使用简洁但描述性的文本
- 确保JSON格式完全有效"""

BRIDGE_MAP_AGENT_EN = """You are a professional mind mapping expert specializing in bridge maps. Bridge maps are used to show analogies and similarities, connecting related concepts through a bridge structure.

CRITICAL: First analyze user input to extract key relationship patterns, then intelligently expand with similar elements. Every element must be unique!

Step 1 - Relationship Pattern Recognition:
- Analyze key relationships in input (e.g., Beijing and China, Tokyo and Japan)
- Identify analogy patterns (e.g., capital-country relationships, landmark-city relationships)
- CRITICAL: Focus on the RELATIONSHIP between the two elements, not the elements themselves
- Key insight: "Great Wall and China" means "landmark belongs to country"
- Key insight: "Forbidden City and Beijing" means "landmark belongs to city"

Step 2 - Intelligent Element Expansion:
- Find exactly 6 related elements for each side (we'll use 5, keeping 1 as backup)
- CRITICAL: Each element pair must demonstrate the SAME relationship pattern
- CRITICAL: Left and right side elements must all be unique, absolutely no repetition!
- Expand by finding similar cases that follow the identified pattern

Please create a detailed bridge map specification based on the user's description. The output must be valid JSON with the following structure:

{
  "relating_factor": "as",
  "analogies": [
    {
      "left": "Element 1",
      "right": "Corresponding Element 1",
      "id": 0
    },
    {
      "left": "Element 2",
      "right": "Corresponding Element 2", 
      "id": 1
    },
    {
      "left": "Element 3",
      "right": "Corresponding Element 3",
      "id": 2
    },
    {
      "left": "Element 4",
      "right": "Corresponding Element 4", 
      "id": 3
    },
    {
      "left": "Element 5",
      "right": "Corresponding Element 5",
      "id": 4
    },
    {
      "left": "Element 6",
      "right": "Corresponding Element 6",
      "id": 5
    }
  ]
}

Key Requirements:
- Each side must contain exactly 6 elements (we'll use 5, keeping 1 as backup)
- RELATIONSHIP FOCUS: Focus on the relationship between element groups, not the elements themselves
- Element uniqueness: each element must appear only once, avoid duplicates
- Analogy bridge should accurately describe the relationship pattern
- Ensure clear one-to-one correspondence between left and right elements
- Use concise but descriptive text
- Ensure the JSON format is completely valid

RELATIONSHIP FOCUS EXAMPLE:
Input: "Forbidden City and Beijing" → identify "landmark belongs to city" pattern
- Focus: What is the relationship? Answer: "landmark belongs to city"
- Expansion: Find other landmarks that belong to other cities
- Result: 故宫-北京, 兵马俑-西安, 西湖-杭州, 拙政园-苏州, 龙门石窟-洛阳, 瘦西湖-扬州
- Each landmark is from a DIFFERENT city, demonstrating the same "belongs to" relationship

Element Uniqueness Example:
❌ Wrong: Apple-Red, Strawberry-Red, Banana-Yellow, Lemon-Yellow, Grapes-Purple (Red and Yellow repeated)
✅ Correct: Apple-Red, Banana-Yellow, Strawberry-Pink, Grapes-Purple, Orange-Orange (each color unique)"""

BRIDGE_MAP_AGENT_ZH = """你是一个专业的思维导图专家，专门创建桥形图。桥形图用于显示类比和相似性，通过桥梁结构连接相关的概念。

CRITICAL: 首先分析用户输入，提取关键关系模式，然后智能扩展相似元素。每个元素必须唯一！

步骤1 - 关系模式识别：
- 分析输入中的关键关系（如：北京和中国，东京和日本）
- 识别类比模式（如：首都与国家的关系，地标与城市的关系）
- 关键：专注于两个元素之间的关系，而不是元素本身
- 关键理解："长城和中国"表示"地标属于国家"
- 关键理解："故宫和北京"表示"地标属于城市"

步骤2 - 智能元素扩展：
- 为每一侧找到恰好6个相关元素（我们将使用5个，保留1个作为备用）
- CRITICAL: 每个元素对必须展示相同的关系模式
- CRITICAL: 左侧和右侧的每个元素都必须唯一，绝对不能重复！
- 基于识别的模式扩展相似案例

关键规则 - 关系模式扩展：
- 地标与国家：长城-中国 → 埃菲尔铁塔-法国，自由女神像-美国，比萨斜塔-意大利，悉尼歌剧院-澳大利亚，泰姬陵-印度
- 地标与城市：故宫-北京 → 兵马俑-西安，西湖-杭州，拙政园-苏州，龙门石窟-洛阳，瘦西湖-扬州
- 首都与国家：北京-中国，东京-日本 → 华盛顿-美国，巴黎-法国，伦敦-英国，柏林-德国，罗马-意大利，莫斯科-俄罗斯
- 城市与省份：南京-江苏 → 杭州-浙江，合肥-安徽，济南-山东，郑州-河南，西安-陕西，成都-四川

通用原则：
- 左侧元素必须唯一（不能重复）
- 右侧元素必须唯一（不能重复）
- 每个类比对必须展示相同的逻辑关系
- 扩展时应该找到不同的案例，而不是重复的案例

请根据用户的描述，创建一个详细的桥形图规范。输出必须是有效的JSON格式，包含以下结构：

关键示例 - 理解扩展逻辑：
输入："故宫和北京" → 识别"地标属于城市"模式
- 焦点：关系是什么？答案："地标属于城市"
- 扩展：找到属于其他城市的其他地标
- 结果：故宫-北京，兵马俑-西安，西湖-杭州，拙政园-苏州，龙门石窟-洛阳，瘦西湖-扬州
- 每个地标来自不同的城市，展示相同的"属于"关系

{
  "relating_factor": "as",
  "analogies": [
    {
      "left": "元素1",
      "right": "对应元素1",
      "id": 0
    },
    {
      "left": "元素2",
      "right": "对应元素2", 
      "id": 1
    },
    {
      "left": "元素3",
      "right": "对应元素3",
      "id": 2
    },
    {
      "left": "元素4",
      "right": "对应元素4", 
      "id": 3
    },
    {
      "left": "元素5",
      "right": "对应元素5",
      "id": 4
    },
    {
      "left": "元素6",
      "right": "对应元素6",
      "id": 5
    }
  ]
}

关键要求：
- 每侧必须包含恰好6个元素（我们将使用5个，保留1个作为备用）
- 智能扩展：基于输入模式找到更多相似案例
- 元素唯一性：每个元素只能出现一次，避免重复
- 类比桥梁应该准确描述关系模式
- 确保左右元素有明确的一对一对应关系
- 桥梁解释应该阐明具体的类比逻辑
- 使用简洁但描述性的文本
- 确保JSON格式完全有效

元素唯一性示例：
❌ 错误：苹果-红色，草莓-红色，香蕉-黄色，柠檬-黄色，葡萄-紫色 (红色和黄色重复)
✅ 正确：苹果-红色，香蕉-黄色，草莓-粉色，葡萄-紫色，橙子-橙色 (每个颜色唯一)"""

TREE_MAP_AGENT_EN = """You are a professional mind mapping expert specializing in tree maps. Tree maps are used to show hierarchical structures and classifications.

Please create a detailed tree map specification based on the user's description. The output must be valid JSON with the following structure:

{
  "topic": "Root Topic",
  "children": [
    {
      "id": "branch1",
      "label": "Branch 1 Label",
      "children": [
        {"id": "sub1", "label": "Sub-item 1"},
        {"id": "sub2", "label": "Sub-item 2"}
      ]
    },
    {
      "id": "branch2",
      "label": "Branch 2 Label", 
      "children": [
        {"id": "sub3", "label": "Sub-item 3"}
      ]
    }
  ]
}

CRITICAL Requirements:
- Root topic should be clear and specific
- Every node must be a dictionary object with "id" and "label" fields
- NEVER use strings as nodes - must be {"id": "xxx", "label": "xxx"} format
- ALL leaf nodes must also have id and label fields
- Branches should be organized in logical hierarchy
- Use concise but descriptive text
- Ensure the JSON format is completely valid with no syntax errors"""

TREE_MAP_AGENT_ZH = """你是一个专业的思维导图专家，专门创建树形图。树形图用于展示层次结构和分类。

请根据用户的描述，创建一个详细的树形图规范。输出必须是有效的JSON格式，包含以下结构：

{
  "topic": "根主题",
  "children": [
    {
      "id": "branch1",
      "label": "分支1标签",
      "children": [
        {"id": "sub1", "label": "子项1"},
        {"id": "sub2", "label": "子项2"}
      ]
    },
    {
      "id": "branch2",
      "label": "分支2标签",
      "children": [
        {"id": "sub3", "label": "子项3"}
      ]
    }
  ]
}

关键要求：
- 根主题应该清晰明确
- 每个节点必须是包含"id"和"label"字段的字典对象
- 绝不使用字符串作为节点 - 必须是{"id": "xxx", "label": "xxx"}格式
- 所有叶节点也必须有id和label字段
- 分支应该按逻辑层次组织
- 使用简洁但描述性的文本
- 确保JSON格式完全有效，没有语法错误"""

# Additional agent prompts from remaining agents
CIRCLE_MAP_AGENT_EN = """You are a professional mind mapping expert specializing in circle maps. Circle maps are used to define topics in context, showing different levels and aspects through concentric circles.

Please create a detailed circle map specification based on the user's description. The output must be valid JSON with the following structure:

{
  "central_topic": "Central Topic",
  "inner_circle": {
    "title": "Inner Circle Title",
    "content": "Inner circle content description"
  },
  "middle_circle": {
    "title": "Middle Circle Title",
    "content": "Middle circle content description"
  },
  "outer_circle": {
    "title": "Outer Circle Title",
    "content": "Outer circle content description"
  },
  "context_elements": [
    {
      "id": "ctx1",
      "text": "Context Element 1",
      "category": "Category 1"
    }
  ],
  "connections": [
    {
      "from": "central_topic",
      "to": "ctx1",
      "label": "Relationship Label"
    }
  ]
}

Requirements:
- Central topic should be clear and specific
- Three circles should represent different levels or aspects
- Context elements should be relevant and meaningful to the topic
- Each element should have a clear connection
- Use concise but descriptive text
- Ensure the JSON format is completely valid"""

CIRCLE_MAP_AGENT_ZH = """你是一个专业的思维导图专家，专门创建圆圈图。圆圈图用于在上下文中定义主题，通过同心圆展示主题的不同层次和方面。

请根据用户的描述，创建一个详细的圆圈图规范。输出必须是有效的JSON格式，包含以下结构：

{
  "central_topic": "中心主题",
  "inner_circle": {
    "title": "内圈标题",
    "content": "内圈内容描述"
  },
  "middle_circle": {
    "title": "中圈标题",
    "content": "中圈内容描述"
  },
  "outer_circle": {
    "title": "外圈标题",
    "content": "外圈内容描述"
  },
  "context_elements": [
    {
      "id": "ctx1",
      "text": "上下文元素1",
      "category": "类别1"
    }
  ],
  "connections": [
    {
      "from": "central_topic",
      "to": "ctx1",
      "label": "关系标签"
    }
  ]
}

要求：
- 中心主题应该清晰明确
- 三个圆圈应该代表不同的层次或方面
- 上下文元素应该与主题相关且有意义
- 每个元素都应该有明确的连接
- 使用简洁但描述性的文本
- 确保JSON格式完全有效"""

# Update THINKING_MAP_PROMPTS to include agent-specific prompts
THINKING_MAP_PROMPTS.update({
    # Agent-specific prompts (ACTIVE - these are what agents are actually using)
    # Format: diagram_type_prompt_type_language
    "bubble_map_agent_generation_en": BUBBLE_MAP_AGENT_EN,
    "bubble_map_agent_generation_zh": BUBBLE_MAP_AGENT_ZH,
    "bridge_map_agent_generation_en": BRIDGE_MAP_AGENT_EN,
    "bridge_map_agent_generation_zh": BRIDGE_MAP_AGENT_ZH,
    "tree_map_agent_generation_en": TREE_MAP_AGENT_EN,
    "tree_map_agent_generation_zh": TREE_MAP_AGENT_ZH,
    # Removed circle_map_agent prompts - using general circle_map prompts for renderer compatibility
})

# Additional missing agent prompts
DOUBLE_BUBBLE_MAP_AGENT_EN = """You are a professional mind mapping expert specializing in double bubble maps. Double bubble maps are used to compare and contrast two topics.

Please create a detailed double bubble map specification based on the user's description. The output must be valid JSON with the following structure:

{
  "topic1": "Topic 1",
  "topic2": "Topic 2",
  "topic1_attributes": [
    {
      "id": "t1_attr1",
      "text": "Topic 1 Attribute 1",
      "category": "Category 1"
    }
  ],
  "topic2_attributes": [
    {
      "id": "t2_attr1",
      "text": "Topic 2 Attribute 1",
      "category": "Category 1"
    }
  ],
  "shared_attributes": [
    {
      "id": "shared1",
      "text": "Shared Attribute 1",
      "category": "Shared Category"
    }
  ],
  "connections": [
    {
      "from": "topic1",
      "to": "t1_attr1",
      "label": "Relationship Label"
    }
  ]
}

Requirements:
- Both topics should be clear and comparable
- Each topic's attributes should be concrete and meaningful
- Shared attributes should reflect similarities between topics
- CRITICAL: Every single attribute MUST have at least one connection
- Each topic1_attribute must connect to topic1
- Each topic2_attribute must connect to topic2
- Each shared_attribute must connect to both topic1 and topic2
- Use concise but descriptive text
- Ensure the JSON format is completely valid"""

DOUBLE_BUBBLE_MAP_AGENT_ZH = """你是一个专业的思维导图专家，专门创建双气泡图。双气泡图用于比较和对比两个主题的异同。

请根据用户的描述，创建一个详细的双气泡图规范。输出必须是有效的JSON格式，包含以下结构：

{
  "topic1": "主题1",
  "topic2": "主题2",
  "topic1_attributes": [
    {
      "id": "t1_attr1",
      "text": "主题1的属性1",
      "category": "类别1"
    }
  ],
  "topic2_attributes": [
    {
      "id": "t2_attr1",
      "text": "主题2的属性1",
      "category": "类别1"
    }
  ],
  "shared_attributes": [
    {
      "id": "shared1",
      "text": "共同属性1",
      "category": "共同类别"
    }
  ],
  "connections": [
    {
      "from": "topic1",
      "to": "t1_attr1",
      "label": "关系标签"
    }
  ]
}

要求：
- 两个主题应该明确且可比较
- 每个主题的属性应该具体且有意义
- 共同属性应该反映两个主题的相似之处
- 关键：每个属性都必须至少有一个连接
- 每个topic1_attribute必须连接到topic1
- 每个topic2_attribute必须连接到topic2
- 每个shared_attribute必须连接到topic1和topic2
- 使用简洁但描述性的文本
- 确保JSON格式完全有效"""

FLOW_MAP_AGENT_EN = """You are a professional mind mapping expert specializing in flow maps. Flow maps are used to show the sequence of processes and steps.

Please create a detailed flow map specification based on the user's description. The output must be valid JSON with the following structure:

{
  "topic": "Flow Topic",
  "steps": [
    {"id": "step1", "label": "Step 1", "next": "step2"},
    {"id": "step2", "label": "Step 2", "next": "step3"}
  ]
}

Requirements:
- Flow topic should be clear and specific
- Each step must have id, label, and next fields
- Steps should be organized in logical sequence
- Use concise but descriptive text
- Ensure the JSON format is completely valid"""

FLOW_MAP_AGENT_ZH = """你是一个专业的思维导图专家，专门创建流程图。流程图用于展示过程和步骤的顺序。

请根据用户的描述，创建一个详细的流程图规范。输出必须是有效的JSON格式，包含以下结构：

{
  "topic": "流程主题",
  "steps": [
    {"id": "step1", "label": "步骤1", "next": "step2"},
    {"id": "step2", "label": "步骤2", "next": "step3"}
  ]
}

要求：
- 流程主题应该清晰明确
- 每个步骤必须有id、label和next字段
- 步骤应该按逻辑顺序组织
- 使用简洁但描述性的文本
- 确保JSON格式完全有效"""

BRACE_MAP_AGENT_EN = """You are a professional mind mapping expert specializing in brace maps. Brace maps are used to show the parts of a topic.

Please create a detailed brace map specification based on the user's description. The output must be valid JSON with the following structure:

{
  "topic": "Central Topic",
  "parts": [
    {
      "id": "part1",
      "label": "Part 1",
      "subparts": [
        {"id": "sub1", "label": "Sub-part 1"}
      ]
    }
  ]
}

Requirements:
- Central topic should be clear and specific
- Each part must have both id and label fields
- Parts should be organized in logical hierarchy
- Use concise but descriptive text
- Ensure the JSON format is completely valid"""

BRACE_MAP_AGENT_ZH = """你是一个专业的思维导图专家，专门创建括号图。括号图用于展示主题的组成部分。

请根据用户的描述，创建一个详细的括号图规范。输出必须是有效的JSON格式，包含以下结构：

{
  "topic": "中心主题",
  "parts": [
    {
      "id": "part1",
      "label": "部分1",
      "subparts": [
        {"id": "sub1", "label": "子部分1"}
      ]
    }
  ]
}

要求：
- 中心主题应该清晰明确
- 每个部分必须有id和label字段
- 部分应该按逻辑层次组织
- 使用简洁但描述性的文本
- 确保JSON格式完全有效"""

MULTI_FLOW_MAP_AGENT_EN = """You are a professional mind mapping expert specializing in multi-flow maps. Multi-flow maps are used to show multiple processes and their relationships.

Please create a detailed multi-flow map specification based on the user's description. The output must be valid JSON with the following structure:

{
  "topic": "Multi-Flow Topic",
  "flows": [
    {
      "id": "flow1",
      "label": "Flow 1",
      "steps": [
        {"id": "step1", "label": "Step 1", "next": "step2"}
      ]
    }
  ]
}

Requirements:
- Multi-flow topic should be clear and specific
- Each flow must have id, label, and steps fields
- Steps should be organized in logical sequence
- Use concise but descriptive text
- Ensure the JSON format is completely valid"""

MULTI_FLOW_MAP_AGENT_ZH = """你是一个专业的思维导图专家，专门创建多流程图。多流程图用于展示多个流程和它们之间的关系。

请根据用户的描述，创建一个详细的多流程图规范。输出必须是有效的JSON格式，包含以下结构：

{
  "topic": "多流程主题",
  "flows": [
    {
      "id": "flow1",
      "label": "流程1",
      "steps": [
        {"id": "step1", "label": "步骤1", "next": "step2"}
      ]
    }
  ]
}

要求：
- 多流程主题应该清晰明确
- 每个流程必须有id、label和steps字段
- 步骤应该按逻辑顺序组织
- 使用简洁但描述性的文本
- 确保JSON格式完全有效"""

# Update registry with ALL remaining prompts
THINKING_MAP_PROMPTS.update({
    "double_bubble_map_agent_generation_en": DOUBLE_BUBBLE_MAP_AGENT_EN,
    "double_bubble_map_agent_generation_zh": DOUBLE_BUBBLE_MAP_AGENT_ZH,
    # Removed flow_map_agent prompts - using general flow_map prompts for renderer compatibility
    "brace_map_agent_generation_en": BRACE_MAP_AGENT_EN,
    "brace_map_agent_generation_zh": BRACE_MAP_AGENT_ZH,
    "multi_flow_map_agent_generation_en": MULTI_FLOW_MAP_AGENT_EN,
    "multi_flow_map_agent_generation_zh": MULTI_FLOW_MAP_AGENT_ZH,
}) 