#【************雅萱改了********** 1--490】
"""
Thinking Maps Prompts

This module contains all prompts for the 8 Thinking Maps®:
1. Circle Map - association, generating related information around the central topic
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

BRIDGE_MAP_GENERATION_EN = """Please generate a JSON specification for a bridge map.

CRITICAL REQUIREMENTS - READ CAREFULLY:
You can use analogies to explain the central concept and draw a bridge map. The upper and lower parts of the bridge are groups of things with the same relationship. The core function is to show similar relationships between different things.
1. **Clear Relationship Pattern**: Clearly define the core analogy relationship. The relationship between each group of elements must follow the same pattern. The format is usually "A is to B as C is to D".
2. **ABSOLUTE UNIQUENESS**: Every element must appear EXACTLY ONCE on each side. NO DUPLICATES ALLOWED.
3. **Consistent Count**: Generate exactly 6 elements for each side (we'll use 5, keeping 1 as backup)
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
请生成一个桥形图的JSON规范。

关键要求 - 请仔细阅读：
你能够使用类比的方法来解释中心词，绘制出桥型图，桥梁上下是一组组具有相同关系的事物，核心作用是展示不同事物之间相似的关系。
1. **明确关系模式**：明确核心的类比关系，每组元素之间的关系必须遵循同一个模式。格式通常是 "A 对于 B，如同 C 对于 D"。
2. **绝对唯一性**：每个元素在每一边必须出现且仅出现一次。绝对不允许重复。
3. **数量一致**：每一边生成恰好6个元素（我们将使用5个，保留1个作为备用）
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
Please generate a JSON specification for a bubble map.

CRITICAL: If the user request contains a quoted topic (e.g., "about 'Transportation'"), you MUST use that EXACT topic word in the "topic" field. Do not paraphrase, translate, or modify it.

You can generate a bubble map with a central core topic surrounded by "bubbles" connected to the topic. Each bubble uses adjectives or descriptive phrases to describe the attributes of the core topic.
Thinking approach: Use adjectives for description and explanation of characteristics.
1. Use adjectives
2. Describe the central topic from multiple dimensions

Please output a JSON object containing the following fields:
topic: "Topic" (MUST match the topic mentioned in the user request EXACTLY if provided)
attributes: ["Feature1", "Feature2", "Feature3", "Feature4", "Feature5", "Feature6", "Feature7", "Feature8"]

Requirements: Each characteristic should be concise and clear. Use adjectives or adjectival phrases to describe the central topic. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences.

Please ensure the JSON format is correct, do not include any code block markers.
"""

BUBBLE_MAP_GENERATION_ZH = """
请生成一个气泡图的JSON规范。

重要提示：如果用户需求中包含引号标注的主题（例如："为主题'交通工具'创建..."），你必须在"topic"字段中使用完全相同的主题词。不要改写、翻译或修改它。

你能够生成气泡图，中心是一个核心主题，周围是与主题连接的"气泡"，每个气泡使用形容词或描述性短语来描述核心主题的属性。
思维方式： 使用形容词进行描述、说明特质。
1. 使用形容词
2. 从多个维度对中心词进行描述
请输出一个包含以下字段的JSON对象：
topic: "主题"（如果需求中明确指定主题，必须完全匹配）
attributes: ["特征1", "特征2", "特征3", "特征4", "特征5", "特征6", "特征7", "特征8"]

要求：每个特征要简洁明了，使用形容词或形容词短语对中心词进行描述，可以超过4个字，但不要太长，避免完整句子。

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# DOUBLE BUBBLE MAP PROMPTS
# ============================================================================

DOUBLE_BUBBLE_MAP_GENERATION_EN = """
Please generate a JSON specification for a double bubble map.

You can draw a double bubble map to compare two central topics and output their similarities and differences.
1. Compare from multiple angles
2. Be concise and clear, avoid long sentences
3. Differences should correspond one-to-one. For example, when comparing apples and bananas, if left_differences: "Feature1" is red, then right_differences: "Feature1" must be yellow, both belonging to the color dimension.

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
请生成一个双气泡图的JSON规范。
你能够绘制双气泡图，对两个中心词进行对比，输出他们的相同点和不同点。
1. 从多个角度进行对比
2. 简洁明了，不要使用长句
3. 不同点要一一对应，如对比苹果和香蕉，left_differences: "特点1"是红色，那么right_differences: "特点1"必须是黄色，都属于颜色维度。
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
Please generate a JSON specification for a circle map.

CRITICAL: If the user request contains a quoted topic (e.g., "about 'Transportation'"), you MUST use that EXACT topic word in the "topic" field. Do not paraphrase, translate, or modify it.

You can draw a circle map to brainstorm the central topic and associate it with related information or background knowledge.
Thinking approach: Association, Divergence
1. Be able to diverge and associate from multiple angles, the wider the angle the better
2. Feature words should be as concise as possible

Please output a JSON object containing the following fields:
topic: "Topic" (MUST match the topic mentioned in the user request EXACTLY if provided)
context: ["Feature1", "Feature2", "Feature3", "Feature4", "Feature5", "Feature6", "Feature7", "Feature8"]

Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences.

Please ensure the JSON format is correct, do not include any code block markers.
"""

CIRCLE_MAP_GENERATION_ZH = """
请生成一个圆圈图的JSON规范。

重要提示：如果用户需求中包含引号标注的主题（例如："为主题'交通工具'创建..."），你必须在"topic"字段中使用完全相同的主题词。不要改写、翻译或修改它。

你能绘制圆圈图，对中心词进行头脑风暴，联想出与之相关的信息或背景知识。
思维方式：关联、发散
1. 能够从多个角度进行发散、联想，角度越广越好
2. 特征词要尽可能简洁
请输出一个包含以下字段的JSON对象：
topic: "主题"（如果需求中明确指定主题，必须完全匹配）
context: ["特征1", "特征2", "特征3", "特征4", "特征5", "特征6", "特征7", "特征8"]

要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# TREE MAP PROMPTS
# ============================================================================

TREE_MAP_GENERATION_EN = """
Please generate a JSON specification for a tree map.

You can classify the central topic.
Purpose: Classification, Induction, Hierarchical organization of information.

CRITICAL: If the user request contains a quoted topic (e.g., "about 'Transportation'"), you MUST use that EXACT topic word in the "topic" field. Do not paraphrase, translate, or modify it.

Output a SINGLE JSON object with the following fields (example shown below):
- topic: "Main topic" (MUST match the topic mentioned in the user request EXACTLY if provided)
- children: [
  {{"text": "Category 1", "children": [
    {{"text": "Item 1", "children": []}},
    {{"text": "Item 2", "children": []}}
  ]}},
  {{"text": "Category 2", "children": [
    {{"text": "Item A", "children": []}}
  ]}}
]

Strict requirements:
- Topic: Use the EXACT topic from the request if specified (e.g., if request says "about 'Transportation'", use "Transportation")
- Top-level children: generate 4–6 categories under "children" (each a short phrase, 1–5 words)
- For EACH top-level child, generate 2–6 sub-children in its "children" array (short phrases, 1–5 words)
- Each child MUST have a "text" field (the label) and a "children" field (array, can be empty)
- Use concise phrases only; no punctuation; no numbering prefixes; avoid full sentences
- All text labels must be unique and non-redundant
- Do not include extra fields beyond topic, children, text

Return only valid JSON. Do NOT include code block markers.
"""

TREE_MAP_GENERATION_ZH = """
请生成一个树形图的JSON规范。
你能对中心词进行分类。
目的是：分类、归纳、层级化组织信息。

重要提示：如果用户需求中包含引号标注的主题（例如："为主题'交通工具'创建..."），你必须在"topic"字段中使用完全相同的主题词。不要改写、翻译或修改它。

输出且仅输出一个JSON对象，包含以下字段（示例如下）：
- topic: "主题"（如果需求中明确指定主题，必须完全匹配）
- children: [
  {{"text": "类别一", "children": [
    {{"text": "条目一", "children": []}},
    {{"text": "条目二", "children": []}}
  ]}},
  {{"text": "类别二", "children": [
    {{"text": "条目甲", "children": []}}
  ]}}
]

严格要求：
- 主题：如果需求中指定了主题（例如"为主题'交通工具'创建..."），必须使用"交通工具"作为topic
- 顶层 children：生成 4–6 个类别（短语，1–5 个词/字）
- 每个顶层 child 的 "children" 数组：生成 2–6 个子项（短语，1–5 个词/字）
- 每个 child 必须有 "text" 字段（标签）和 "children" 字段（数组，可以为空）
- 仅用简短短语；不要标点；不要编号前缀；不要完整句子
- 所有 text 标签必须唯一且不冗余
- 不要包含 topic、children、text 之外的字段

只返回有效 JSON，不要包含代码块标记。
"""

# ============================================================================
# FLOW MAP PROMPTS
# ============================================================================

FLOW_MAP_GENERATION_EN = """
Please generate a JSON specification for a flow map with MAJOR steps and SUB-STEPS.

CRITICAL: If the user request contains a quoted title/topic (e.g., "about 'Water Cycle'"), you MUST use that EXACT title in the "title" field. Do not paraphrase, translate, or modify it.

Output a SINGLE JSON object with the following fields:
- title: "Main topic" (if specified in request, use EXACT title)
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
请生成一个包含"主要步骤"和"子步骤"的流程图JSON规范。

重要提示：如果用户需求中包含引号标注的主题（例如："为主题'水循环'创建..."），你必须在"title"字段中使用完全相同的主题词。不要改写、翻译或修改它。

关键要求：必须全部使用中文生成内容，包括steps数组和substeps数组中的所有文本。不要混用英文和中文。

输出一个且仅一个JSON对象，包含以下字段：
- title: "主题"（如果需求中明确指定主题，必须完全匹配）
- steps: ["准备阶段", "执行阶段", "检查阶段", "完成阶段"]
- substeps: [
  {"step": "准备阶段", "substeps": ["收集需求", "制定计划"]},
  {"step": "执行阶段", "substeps": ["实施任务", "监控进度"]},
  {"step": "检查阶段", "substeps": ["质量检验", "验收确认"]},
  {"step": "完成阶段", "substeps": ["交付成果", "总结归档"]}
]

注意：以上示例仅为格式参考，实际内容应根据用户需求生成。steps数组中的步骤名称必须与substeps数组中的"step"字段完全一致。

定义与意图：
- 主要步骤（steps）：高层级阶段，用于保持流程图整洁、专业，类似里程碑或阶段名称；且每个主要步骤应当能够"概括/泛化"其所属的所有子步骤。
- 子步骤（sub-steps）：具体执行动作，用于说明"如何做"，提供细节但不让主流程拥挤；子步骤必须逻辑上被其对应的主要步骤"包含"。

严格要求：
- 主要步骤：3–8项，短语（1–6个词/字），不用标点，不写完整句子，不加编号前缀。
- 子步骤：每个主要步骤生成1–5项，短语（1–7个词/字），不用标点，避免重复主要步骤的措辞。
- 每个主要步骤必须能够"概括/泛化"其子步骤。如果某些子步骤引入了现有步骤未覆盖的新主题，请新增或调整主要步骤以覆盖之。
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
Please generate a JSON specification for a brace map.

Brace maps are used for decomposition, representing the relationship between the whole and its parts.
1. Understanding the physical components of an object, not classifying the central topic.

Please output a JSON object containing the following fields:
topic: "Main topic"
parts: [{{"name": "Part1", "subparts": [{{"name": "Subpart1.1"}}]}}]

CRITICAL: If the user request contains a quoted topic (e.g., "about 'Transportation'"), you MUST use that EXACT topic word in the "topic" field. Do not paraphrase, translate, or modify it.

IMPORTANT: Generate fresh, meaningful content for parts and subparts. Do not use placeholder text like "Part1", "Subpart1.1", etc.

Requirements:
- Generate 3-6 main parts with clear, descriptive names
- Each part should have 2-5 subparts that are specific and detailed
- Use concise, clear language - avoid long sentences
- Ensure logical whole-to-part relationships (whole → parts → subparts)
- Parts should be major categories or divisions of the topic
- Subparts should be specific components, features, or elements of each part

Example format (for reference only):
topic: "Car"
parts: [
  {{"name": "Body Parts", "subparts": [{{"name": "Doors"}}, {{"name": "Windows"}}, {{"name": "Roof"}}]}},
  {{"name": "Powertrain", "subparts": [{{"name": "Engine"}}, {{"name": "Transmission"}}, {{"name": "Driveshaft"}}]}}
]

Do not include any information about visual layout or braces; only provide the hierarchical data.

Please ensure the JSON format is correct, do not include any code block markers.
"""

BRACE_MAP_GENERATION_ZH = """
请生成一个括号图（Brace Map）的JSON规范。

括号图用于拆分，表示整体与部分之间的关系。
1. 理解一个物体的物理组成部分，不是对中心词进行分类。

请输出一个包含以下字段的JSON对象：
topic: "主题"
parts: [{{"name": "部分1", "subparts": [{{"name": "子部分1.1"}}]}}]

重要提示：如果用户需求中包含引号标注的主题（例如："为主题'植物'创建..."），你必须在"topic"字段中使用完全相同的主题词。不要改写、翻译或修改它。

关键要求：必须全部使用中文生成内容，包括topic、parts数组和subparts数组中的所有文本。不要混用英文和中文。请生成全新的、有意义的部分和子部分内容，不要使用占位符文本如"部分1"、"子部分1.1"等。

要求：
- 生成3-6个主要部分，名称清晰、描述性强
- 每个部分应有2-5个子部分，具体且详细
- 使用简洁、清晰的语言，避免长句
- 确保逻辑的整体→部分→子部分关系
- 部分应为主题的主要类别或分支
- 子部分应为每个部分的具体组件、特征或元素

示例格式（仅供参考）：
topic: "汽车"
parts: [
  {{"name": "车身部分", "subparts": [{{"name": "车门"}}, {{"name": "车窗"}}, {{"name": "车顶"}}]}},
  {{"name": "动力系统", "subparts": [{{"name": "发动机"}}, {{"name": "变速箱"}}, {{"name": "传动轴"}}]}}
]

不要包含任何关于可视化布局或括号形状的说明；只提供层级数据。

请确保JSON格式正确，不要包含任何代码块标记。
"""

# ============================================================================
# MULTI-FLOW MAP PROMPTS
# ============================================================================

MULTI_FLOW_MAP_GENERATION_EN = """
Please generate a JSON specification for a multi-flow map.

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
请生成一个复流程图的JSON规范。

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
# 【雅萱改动结束】

# ============================================================================
# PROMPT REGISTRY
# ============================================================================

THINKING_MAP_PROMPTS = {
    # Generation prompts for each diagram type
    "bridge_map_generation_en": BRIDGE_MAP_GENERATION_EN,
    "bridge_map_generation_zh": BRIDGE_MAP_GENERATION_ZH,
    "bubble_map_generation_en": BUBBLE_MAP_GENERATION_EN,
    "bubble_map_generation_zh": BUBBLE_MAP_GENERATION_ZH,
    "double_bubble_map_generation_en": DOUBLE_BUBBLE_MAP_GENERATION_EN,
    "double_bubble_map_generation_zh": DOUBLE_BUBBLE_MAP_GENERATION_ZH,
    "circle_map_generation_en": CIRCLE_MAP_GENERATION_EN,
    "circle_map_generation_zh": CIRCLE_MAP_GENERATION_ZH,
    "tree_map_generation_en": TREE_MAP_GENERATION_EN,
    "tree_map_generation_zh": TREE_MAP_GENERATION_ZH,
    "flow_map_generation_en": FLOW_MAP_GENERATION_EN,
    "flow_map_generation_zh": FLOW_MAP_GENERATION_ZH,
    "brace_map_generation_en": BRACE_MAP_GENERATION_EN,
    "brace_map_generation_zh": BRACE_MAP_GENERATION_ZH,
    "multi_flow_map_generation_en": MULTI_FLOW_MAP_GENERATION_EN,
    "multi_flow_map_generation_zh": MULTI_FLOW_MAP_GENERATION_ZH,
    
    # Agent-specific prompt keys (what agents are actually calling for)
    "bridge_map_agent_generation_en": BRIDGE_MAP_GENERATION_EN,
    "bridge_map_agent_generation_zh": BRIDGE_MAP_GENERATION_ZH,
    "bubble_map_agent_generation_en": BUBBLE_MAP_GENERATION_EN,
    "bubble_map_agent_generation_zh": BUBBLE_MAP_GENERATION_ZH,
    "double_bubble_map_agent_generation_en": DOUBLE_BUBBLE_MAP_GENERATION_EN,
    "double_bubble_map_agent_generation_zh": DOUBLE_BUBBLE_MAP_GENERATION_ZH,
    "circle_map_agent_generation_en": CIRCLE_MAP_GENERATION_EN,
    "circle_map_agent_generation_zh": CIRCLE_MAP_GENERATION_ZH,
    "tree_map_agent_generation_en": TREE_MAP_GENERATION_EN,
    "tree_map_agent_generation_zh": TREE_MAP_GENERATION_ZH,
    "flow_map_agent_generation_en": FLOW_MAP_GENERATION_EN,
    "flow_map_agent_generation_zh": FLOW_MAP_GENERATION_ZH,
    "brace_map_agent_generation_en": BRACE_MAP_GENERATION_EN,
    "brace_map_agent_generation_zh": BRACE_MAP_GENERATION_ZH,
    "multi_flow_map_agent_generation_en": MULTI_FLOW_MAP_GENERATION_EN,
    "multi_flow_map_agent_generation_zh": MULTI_FLOW_MAP_GENERATION_ZH,
} 