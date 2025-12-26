"""
Prompt to Diagram Agent Prompts

This module contains prompts for direct prompt-to-diagram generation using a single LLM call.
Used by simplified endpoints that need fast, efficient diagram generation.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

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

# Bubble Map
BUBBLE_MAP_SPEC_EN = """1. bubble_map:
You can generate a bubble map with a central core topic surrounded by "bubbles" connected to the topic. Each bubble uses adjectives or descriptive phrases to describe the attributes of the core topic.
Thinking approach: Use adjectives for description and explanation of characteristics.
- Use adjectives
- Describe the central topic from multiple dimensions
{{
  "topic": "Central Topic",
  "attributes": ["Feature1", "Feature2", "Feature3", "Feature4", "Feature5", "Feature6", "Feature7", "Feature8"]
}}
Requirements: Each characteristic should be concise and clear. Use adjectives or adjectival phrases to describe the central topic. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences."""

BUBBLE_MAP_SPEC_ZH = """1. bubble_map:
你能够生成气泡图，中心是一个核心主题，周围是与主题连接的"气泡"，每个气泡使用形容词或描述性短语来描述核心主题的属性。
思维方式： 使用形容词进行描述、说明特质。
- 使用形容词
- 从多个维度对中心词进行描述
{{
  "topic": "主题",
  "attributes": ["特征1", "特征2", "特征3", "特征4", "特征5", "特征6", "特征7", "特征8"]
}}
要求：每个特征要简洁明了，使用形容词或形容词短语对中心词进行描述，可以超过4个字，但不要太长，避免完整句子。"""

# Circle Map
CIRCLE_MAP_SPEC_EN = """2. circle_map:
You can draw a circle map to brainstorm the central topic and associate it with related information or background knowledge.
Thinking approach: Association, Divergence
- Be able to diverge and associate from multiple angles, the wider the angle the better
- Feature words should be as concise as possible
{{
  "topic": "Central Topic",
  "context": ["Feature1", "Feature2", "Feature3", "Feature4", "Feature5", "Feature6"]
}}
Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences."""

CIRCLE_MAP_SPEC_ZH = """2. circle_map:
你能绘制圆圈图，对中心词进行头脑风暴，联想出与之相关的信息或背景知识。
思维方式：关联、发散
- 能够从多个角度进行发散、联想，角度越广越好
- 特征词要尽可能简洁
{{
  "topic": "主题",
  "context": ["特征1", "特征2", "特征3", "特征4", "特征5", "特征6"]
}}
要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。"""

# Double Bubble Map
DOUBLE_BUBBLE_MAP_SPEC_EN = """3. double_bubble_map:
You can draw a double bubble map to compare two central topics and output their similarities and differences.
- Compare from multiple angles
- Be concise and clear, avoid long sentences
- Differences should correspond one-to-one. For example, when comparing apples and bananas, if left_differences: "Feature1" is red, then right_differences: "Feature1" must be yellow, both belonging to the color dimension.
{{
  "left": "Topic1",
  "right": "Topic2",
  "similarities": ["Feature1", "Feature2", "Feature3", "Feature4", "Feature5"],
  "left_differences": ["Feature1", "Feature2", "Feature3", "Feature4", "Feature5"],
  "right_differences": ["Feature1", "Feature2", "Feature3", "Feature4", "Feature5"]
}}
Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences."""

DOUBLE_BUBBLE_MAP_SPEC_ZH = """3. double_bubble_map:
你能够绘制双气泡图，对两个中心词进行对比，输出他们的相同点和不同点。
- 从多个角度进行对比
- 简洁明了，不要使用长句
- 不同点要一一对应，如对比苹果和香蕉，left_differences: "特点1"是红色，那么right_differences: "特点1"必须是黄色，都属于颜色维度。
{{
  "left": "主题1",
  "right": "主题2",
  "similarities": ["特征1", "特征2", "特征3", "特征4", "特征5"],
  "left_differences": ["特点1", "特点2", "特点3", "特点4", "特点5"],
  "right_differences": ["特点1", "特点2", "特点3", "特点4", "特点5"]
}}
要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。"""

# Brace Map
BRACE_MAP_SPEC_EN = """4. brace_map:
Brace maps are used for decomposition, representing the relationship between the whole and its parts.
- Understanding the physical components of an object, not classifying the central topic.

CRITICAL: DIMENSION EXTRACTION
A brace map can decompose a topic using DIFFERENT DIMENSIONS. You MUST:
✓ Extract the decomposition dimension from the user's prompt if explicitly specified
✓ If user mentions "decompose by X", "using X approach", "break down by X", "from X perspective", "based on X", etc., extract X as the dimension
✓ Common patterns: "从用途出发" (from usage perspective) → extract "用途" (usage), "从功能角度" (from function angle) → extract "功能" (function), "按物理部件" (by physical parts) → extract "物理部件" (physical parts)
✓ Use that EXACT dimension for decomposition throughout the entire map
✓ If no dimension is specified, choose an appropriate one and include it in the output

Common Decomposition Dimensions (examples):
- Physical Parts, Functional Modules, Life Cycle Stages, User Experience, Manufacturing Process
- For "Computer": Physical Parts, Functional Modules, Life Cycle, etc.
- For "Car": Physical Parts, Functional Modules, Price Segments, etc.

{{
  "whole": "Main topic (the whole to be decomposed)",
  "dimension": "The decomposition dimension being used (e.g., 'Physical Parts', 'Functional Modules')",
  "parts": [{{"name": "Part1", "subparts": [{{"name": "Subpart1.1"}}]}}],
  "alternative_dimensions": ["Dimension1", "Dimension2", "Dimension3", "Dimension4"]
}}
Requirements:
- Generate 3-6 main parts with clear, descriptive names
- Each part should have 2-5 subparts that are specific and detailed
- Use concise, clear language - avoid long sentences
- Ensure logical whole-to-part relationships (whole → parts → subparts)
- Parts should be major categories or divisions of the topic
- Subparts should be specific components, features, or elements of each part
- MUST include "dimension" field describing the decomposition approach used
- MUST include "alternative_dimensions" array with 4-6 other valid dimensions for this topic
- ALL parts must follow the SAME dimension consistently
- If user specifies a dimension, use it EXACTLY as specified
- Do not include any information about visual layout or braces; only provide the hierarchical data."""

BRACE_MAP_SPEC_ZH = """4. brace_map:
括号图用于拆分，表示整体与部分之间的关系。
- 理解一个物体的物理组成部分，不是对中心词进行分类。

关键：维度提取
括号图可以使用不同的维度来拆解主题。您必须：
✓ 如果用户在提示中明确指定了拆解维度，请提取它
✓ 如果用户提到"按X拆解"、"使用X方法"、"按X分解"、"从X出发"、"以X角度"、"基于X"等，请将X提取为维度
✓ 常见模式："从用途出发" → 提取"用途"、"从功能角度" → 提取"功能"、"按物理部件" → 提取"物理部件"
✓ 在整个图中使用该确切的维度进行拆解
✓ 如果未指定维度，请选择适当的维度并在输出中包含它

常见拆解维度（示例）：
- 物理部件、功能模块、生命周期阶段、用户体验、制造流程
- 对于"计算机"：物理部件、功能模块、生命周期等
- 对于"汽车"：物理部件、功能模块、价格区间等

{{
  "whole": "主题（要拆解的整体）",
  "dimension": "使用的拆解维度（例如：'物理部件'、'功能模块'）",
  "parts": [{{"name": "部分1", "subparts": [{{"name": "子部分1.1"}}]}}],
  "alternative_dimensions": ["维度1", "维度2", "维度3", "维度4"]
}}
要求：
- 生成3-6个主要部分，名称清晰、描述性强
- 每个部分应有2-5个子部分，具体且详细
- 使用简洁、清晰的语言，避免长句
- 确保逻辑的整体→部分→子部分关系
- 部分应为主题的主要类别或分支
- 子部分应为每个部分的具体组件、特征或元素
- 必须包含 "dimension" 字段，描述所使用的拆解方法
- 必须包含 "alternative_dimensions" 数组，列出此主题的 4-6 个其他有效维度
- 所有部分必须一致地遵循相同的维度
- 如果用户指定了维度，请完全按照指定使用
- 不要包含任何关于可视化布局或括号形状的说明；只提供层级数据。"""

# Bridge Map
BRIDGE_MAP_SPEC_EN = """5. bridge_map:
You can use analogies to explain the central concept and draw a bridge map. The upper and lower parts of the bridge are groups of things with the same relationship. The core function is to show similar relationships between different things.

CRITICAL: DIMENSION EXTRACTION
A bridge map uses a relationship pattern (dimension) to create analogies. You MUST:
✓ Extract the relationship pattern from the user's prompt if explicitly specified
✓ If user mentions "X to Y", "X and Y", "X like Y", "从X角度" (from X perspective), "基于X" (based on X), or describes a relationship type, extract it as the dimension
✓ Examples: "Capital to Country", "Author to Book", "Currency to Country", "货币和国家", "首都到国家", "从用途出发" → extract "用途" (usage)
✓ Use that EXACT relationship pattern for ALL analogy pairs
✓ If no dimension is specified, identify the relationship pattern from the user's examples or topic

Common Relationship Patterns:
- Capital to Country, Author to Work, Function to Object, Part to Whole, Tool to Worker
- Cause to Effect, Animal to Habitat, Product to Company, Inventor to Invention

- Clear Relationship Pattern: Clearly define the core analogy relationship. The relationship between each group of elements must follow the same pattern. The format is usually "A is to B as C is to D".
- ABSOLUTE UNIQUENESS: Every element must appear EXACTLY ONCE on each side. NO DUPLICATES ALLOWED.
- Consistent Count: Generate exactly 6 elements for each side (we'll use 5, keeping 1 as backup)
- No Repetition: Never repeat the same element, category, or similar concept on either side
- No variations of the same concept (e.g., don't use "China" and "Chinese" or "Beijing" and "Beijing City")

{{
  "relating_factor": "as",
  "dimension": "The relationship pattern name (e.g., 'Capital to Country', 'Author to Work')",
  "analogies": [
    {{"left": "First item in analogy pair", "right": "Second item in analogy pair", "id": 0}},
    {{"left": "First item in analogy pair", "right": "Second item in analogy pair", "id": 1}},
    {{"left": "First item in analogy pair", "right": "Second item in analogy pair", "id": 2}},
    {{"left": "First item in analogy pair", "right": "Second item in analogy pair", "id": 3}},
    {{"left": "First item in analogy pair", "right": "Second item in analogy pair", "id": 4}},
    {{"left": "First item in analogy pair", "right": "Second item in analogy pair", "id": 5}}
  ],
  "alternative_dimensions": ["Alternative Pattern 1", "Alternative Pattern 2", "Alternative Pattern 3", "Alternative Pattern 4"]
}}
Validation Checklist:
- [ ] Exactly 6 analogy pairs (6 elements per side)
- [ ] Each left element appears only once
- [ ] Each right element appears only once
- [ ] No conceptual duplicates (e.g., "China" vs "Chinese")
- [ ] All analogies follow the same relationship pattern
- [ ] MUST include "dimension" field with the relationship pattern name
- [ ] MUST include "alternative_dimensions" array with 4-6 other valid patterns
- [ ] If user specifies a dimension, use it EXACTLY as specified
- [ ] JSON format is valid and complete"""

BRIDGE_MAP_SPEC_ZH = """5. bridge_map:
你能够使用类比的方法来解释中心词，绘制出桥型图，桥梁上下是一组组具有相同关系的事物，核心作用是展示不同事物之间相似的关系。

关键：维度提取
桥形图使用关系模式（维度）来创建类比。您必须：
✓ 如果用户在提示中明确指定了关系模式，请提取它
✓ 如果用户提到"X到Y"、"X和Y"、"X像Y"、"从X出发"、"以X角度"、"基于X"或描述关系类型，请将其提取为维度
✓ 示例："首都到国家"、"作者到作品"、"货币到国家"、"Capital to Country"、"Author to Book"、"从用途出发" → 提取"用途"
✓ 所有类比对都使用该确切的关系模式
✓ 如果未指定维度，请从用户的示例或主题中识别关系模式

常见关系模式：
- 首都到国家、作者到作品、功能到对象、部分到整体、工具到工人
- 原因到结果、动物到栖息地、产品到公司、发明者到发明

- 明确关系模式：明确核心的类比关系，每组元素之间的关系必须遵循同一个模式。格式通常是 "A 对于 B，如同 C 对于 D"。
- 绝对唯一性：每个元素在每一边必须出现且仅出现一次。绝对不允许重复。
- 数量一致：每一边生成恰好6个元素（我们将使用5个，保留1个作为备用）
- 无重复：永远不要在任一边重复相同的元素、类别或相似概念
- 不要使用同一概念的变化形式（例如，不要使用"中国"和"中国的"或"北京"和"北京城"）

{{
  "relating_factor": "as",
  "dimension": "关系模式名称（例如：'首都到国家'、'作者到作品'）",
  "analogies": [
    {{"left": "类比对中的第一项", "right": "类比对中的第二项", "id": 0}},
    {{"left": "类比对中的第一项", "right": "类比对中的第二项", "id": 1}},
    {{"left": "类比对中的第一项", "right": "类比对中的第二项", "id": 2}},
    {{"left": "类比对中的第一项", "right": "类比对中的第二项", "id": 3}},
    {{"left": "类比对中的第一项", "right": "类比对中的第二项", "id": 4}},
    {{"left": "类比对中的第一项", "right": "类比对中的第二项", "id": 5}}
  ],
  "alternative_dimensions": ["替代模式1", "替代模式2", "替代模式3", "替代模式4"]
}}
验证清单：
- [ ] 恰好6个类比对（每边6个元素）
- [ ] 每个左侧元素只出现一次
- [ ] 每个右侧元素只出现一次
- [ ] 无概念重复（例如，"中国"与"中国的"）
- [ ] 所有类比遵循相同的关系模式
- [ ] 必须包含 "dimension" 字段，包含关系模式名称
- [ ] 必须包含 "alternative_dimensions" 数组，列出 4-6 个其他有效模式
- [ ] 如果用户指定了维度，请完全按照指定使用
- [ ] JSON格式有效且完整"""

# Tree Map
TREE_MAP_SPEC_EN = """6. tree_map:
You can classify the central topic.
Purpose: Classification, Induction, Hierarchical organization of information.

CRITICAL: DIMENSION EXTRACTION
A tree map can classify a topic using DIFFERENT DIMENSIONS. You MUST:
✓ Extract the classification dimension from the user's prompt if explicitly specified
✓ If user mentions "classify by X", "using X taxonomy", "categorize by X", "from X perspective", "based on X", "从X出发" (from X perspective), "以X角度" (from X angle), "基于X" (based on X), etc., extract X as the dimension
✓ Common patterns: "从用途出发" (from usage perspective) → extract "用途" (usage), "从功能角度" (from function angle) → extract "功能" (function), "按生物分类" (by biological taxonomy) → extract "生物分类" (biological taxonomy)
✓ Use that EXACT dimension for classification throughout the entire map
✓ If no dimension is specified, choose an appropriate one and include it in the output

Common Classification Dimensions (examples):
- Biological Taxonomy, Habitat, Diet, Size, Geographic Region, Conservation Status
- For "Animals": Biological Taxonomy, Habitat, Diet, Size, etc.
- For "Plants": Botanical Classification, Habitat, Growth Pattern, Uses, etc.

{{
  "topic": "Main topic",
  "dimension": "The classification dimension being used (e.g., 'Biological Taxonomy', 'Habitat', 'Diet')",
  "children": [
    {{"text": "Category 1", "children": [
      {{"text": "Item 1", "children": []}},
      {{"text": "Item 2", "children": []}}
    ]}},
    {{"text": "Category 2", "children": [
      {{"text": "Item A", "children": []}}
    ]}}
  ],
  "alternative_dimensions": ["Dimension1", "Dimension2", "Dimension3", "Dimension4"]
}}
Strict requirements:
- Top-level children: generate 4–6 categories under "children" (each a short phrase, 1–5 words)
- For EACH top-level child, generate 2–6 sub-children in its "children" array (short phrases, 1–5 words)
- Use concise phrases only; no punctuation; no numbering prefixes; avoid full sentences
- All labels must be unique and non-redundant
- MUST include "dimension" field describing the classification approach used
- MUST include "alternative_dimensions" array with 4-6 other valid dimensions for this topic
- ALL categories must follow the SAME dimension consistently
- If user specifies a dimension, use it EXACTLY as specified
- Return only valid JSON. Do NOT include code block markers."""

TREE_MAP_SPEC_ZH = """6. tree_map:
你能对中心词进行分类。
目的是：分类、归纳、层级化组织信息。

关键：维度提取
树形图可以使用不同的维度来分类主题。您必须：
✓ 如果用户在提示中明确指定了分类维度，请提取它
✓ 如果用户提到"按X分类"、"使用X分类法"、"按X分类"、"从X出发"、"以X角度"、"基于X"等，请将X提取为维度
✓ 常见模式："从用途出发" → 提取"用途"、"从功能角度" → 提取"功能"、"按生物分类" → 提取"生物分类"
✓ 在整个图中使用该确切的维度进行分类
✓ 如果未指定维度，请选择适当的维度并在输出中包含它

常见分类维度（示例）：
- 生物分类、栖息地、食性、体型、地理区域、保护状态
- 对于"动物"：生物分类、栖息地、食性、体型等
- 对于"植物"：植物分类、栖息地、生长模式、用途等

{{
  "topic": "主题",
  "dimension": "使用的分类维度（例如：'生物分类'、'栖息地'、'食性'）",
  "children": [
    {{"text": "类别一", "children": [
      {{"text": "条目一", "children": []}},
      {{"text": "条目二", "children": []}}
    ]}},
    {{"text": "类别二", "children": [
      {{"text": "条目甲", "children": []}}
    ]}}
  ],
  "alternative_dimensions": ["维度1", "维度2", "维度3", "维度4"]
}}
严格要求：
- 顶层 children：生成 4–6 个类别（短语，1–5 个词/字）
- 每个顶层 child 的 "children" 数组：生成 2–6 个子项（短语，1–5 个词/字）
- 仅用简短短语；不要标点；不要编号前缀；不要完整句子
- 所有标签必须唯一且不冗余
- 必须包含 "dimension" 字段，描述所使用的分类方法
- 必须包含 "alternative_dimensions" 数组，列出此主题的 4-6 个其他有效维度
- 所有类别必须一致地遵循相同的维度
- 如果用户指定了维度，请完全按照指定使用
- 只返回有效 JSON，不要包含代码块标记。"""

# Flow Map
FLOW_MAP_SPEC_EN = """7. flow_map:
Please generate a flow map with MAJOR steps and SUB-STEPS.
Definitions and intent:
- Steps (major steps): high-level phases that keep the flow neat, clean, and professional. They should read like milestones or stage names, and each one should GENERALIZE its own sub-steps.
- Sub-steps: concrete, detailed actions that explain how each step is carried out. They provide depth without cluttering the main flow and must be logically contained by their step.
{{
  "title": "Main topic",
  "steps": ["Major step 1", "Major step 2", "Major step 3"],
  "substeps": [
    {{"step": "Major step 1", "substeps": ["Sub-step A", "Sub-step B"]}},
    {{"step": "Major step 2", "substeps": ["Sub-step A", "Sub-step B"]}}
  ]
}}
Strict requirements:
- Steps: 3–8 items, each a concise phrase (1–6 words), no punctuation, no full sentences, no numbering prefixes.
- Sub-steps: for each step, generate 1–5 detailed actions (1–7 words), no punctuation, avoid repeating the step text.
- Each step must be a category/abstraction that GENERALIZES all its sub-steps. If any sub-steps introduce a new theme not covered by existing steps, add or adjust a step to cover it.
- Do not include sub-steps that simply restate the step; add specific details (at least one key term not present in the step).
- Keep all items unique and non-redundant; avoid explanatory clauses.
- The steps array must contain ONLY strings.
- The substeps array must contain objects with fields "step" (string exactly matching a value in steps) and "substeps" (array of strings).
- If the user provides partial steps, respect their order and fill gaps sensibly."""

FLOW_MAP_SPEC_ZH = """7. flow_map:
请生成一个包含"主要步骤"和"子步骤"的流程图JSON规范。
定义与意图：
- 主要步骤（steps）：高层级阶段，用于保持流程图整洁、专业，类似里程碑或阶段名称；且每个主要步骤应当能够"概括/泛化"其所属的所有子步骤。
- 子步骤（sub-steps）：具体执行动作，用于说明"如何做"，提供细节但不让主流程拥挤；子步骤必须逻辑上被其对应的主要步骤"包含"。
{{
  "title": "主题",
  "steps": ["主要步骤1", "主要步骤2", "主要步骤3"],
  "substeps": [
    {{"step": "主要步骤1", "substeps": ["子步骤A", "子步骤B"]}},
    {{"step": "主要步骤2", "substeps": ["子步骤A", "子步骤B"]}}
  ]
}}
严格要求：
- 主要步骤：3–8项，短语（1–6个词/字），不用标点，不写完整句子，不加编号前缀。
- 子步骤：每个主要步骤生成1–5项，短语（1–7个词/字），不用标点，避免重复主要步骤的措辞。
- 每个主要步骤必须能够"概括/泛化"其子步骤。如果某些子步骤引入了现有步骤未覆盖的新主题，请新增或调整主要步骤以覆盖之。
- 不要生成仅仅复述主要步骤的子步骤；必须加入具体细节（至少包含主要步骤中未出现的关键词）。
- 保持内容唯一、具体、不重复；避免解释性从句。
- steps 数组仅包含字符串。
- substeps 数组必须包含对象，且对象含有 "step"（与 steps 中某项完全一致）与 "substeps"（字符串数组）。
- 若用户提供了部分步骤，按其顺序补全并保持合理性。"""

# Multi-Flow Map
MULTI_FLOW_MAP_SPEC_EN = """8. multi_flow_map:
Please generate a multi-flow map for analyzing cause-effect relationships.
{{
  "event": "Central event",
  "causes": ["Cause1", "Cause2", "Cause3", "Cause4"],
  "effects": ["Effect1", "Effect2", "Effect3", "Effect4"]
}}
Requirements:
- Use concise key descriptions (1–8 words) for each item
- Prefer nouns or short noun phrases; avoid full sentences and punctuation
- Keep items focused and non-redundant; no explanatory clauses"""

MULTI_FLOW_MAP_SPEC_ZH = """8. multi_flow_map:
请生成一个复流程图的JSON规范。
{{
  "event": "中心事件",
  "causes": ["原因1", "原因2", "原因3", "原因4"],
  "effects": ["结果1", "结果2", "结果3", "结果4"]
}}
要求：
- 每项使用关键描述，尽量简短（1–8个词/字）
- 优先使用名词或短名词短语；避免完整句子与标点
- 内容聚焦且不重复，不要解释性从句"""

# Mind Map
MIND_MAP_SPEC_EN = """9. mind_map:
You are an advanced mind mapping architecture expert. Create a detailed mind map specification.
{{
  "topic": "Central Topic",
  "children": [
    {{
      "id": "branch_1",
      "label": "Branch 1 Label",
      "children": [
        {{"id": "sub_1_1", "label": "Sub-item 1.1"}},
        {{"id": "sub_1_2", "label": "Sub-item 1.2"}}
      ]
    }},
    {{
      "id": "branch_2",
      "label": "Branch 2 Label",
      "children": [
        {{"id": "sub_2_1", "label": "Sub-item 2.1"}}
      ]
    }}
  ]
}}
Absolute Rule: Every mind map you generate MUST have exactly 4, 6, or 8 main branches. You must proactively choose the most appropriate even number of branches based on the complexity and breadth of the user's topic to ensure structural balance and completeness. All branch divisions should follow the MECE principle (Mutually Exclusive, Collectively Exhaustive) as much as possible.
CRITICAL Requirements:
- Central topic should be clear, specific, and have educational value
- Main branches MUST strictly follow 4, 6, or 8 branches (even number rule)
- Each node must have both id and label fields
- Branches should follow MECE principle (Mutually Exclusive, Collectively Exhaustive)
- Sub-items should have hierarchy and instructional guidance significance
- ALL children arrays must be properly closed with ]
- ALL objects must be properly closed with }}
- Use concise but educationally practical text"""

MIND_MAP_SPEC_ZH = """9. mind_map:
你是一名专为提升教师思维教学水平而设计的高级思维导图架构专家。创建详细的思维导图规范。
{{
  "topic": "中心主题",
  "children": [
    {{
      "id": "fen_zhi_1",
      "label": "分支1标签",
      "children": [
        {{"id": "zi_xiang_1_1", "label": "子项1.1"}},
        {{"id": "zi_xiang_1_2", "label": "子项1.2"}}
      ]
    }},
    {{
      "id": "fen_zhi_2",
      "label": "分支2标签",
      "children": [
        {{"id": "zi_xiang_2_1", "label": "子项2.1"}}
      ]
    }}
  ]
}}
绝对规则：你生成的每一个思维导图，必须有且只能有4个、6个或8个主分支。你必须主动根据用户提供主题的复杂度和广度，智能选择最合适的偶数分支数量，以确保结构的平衡与完整。所有分支的划分应尽可能遵循"相互独立，完全穷尽"（MECE）原则。
关键要求：
- 中心主题应该清晰明确且具有教学价值
- 主分支必须严格遵循4个、6个或8个（偶数规则）
- 每个节点必须有id和label字段
- 分支应该遵循MECE原则（相互独立，完全穷尽）
- 子项应该具有层次性和教学指导意义
- 所有children数组必须用]正确闭合
- 所有对象必须用}}正确闭合
- 使用简洁但具有教学实践指导价值的文本"""

# Concept Map
CONCEPT_MAP_SPEC_EN = """10. concept_map:
Generate a concept map showing complex concept relationships.
{{
  "topic": "Central Concept",
  "concepts": ["Concept 1", "Concept 2", ...],
  "relationships": [
    {{"from": "Concept 1", "to": "Concept 2", "label": "relationship"}},
    ...
  ]
}}
Requirements:
- Concepts should be diverse and cover different aspects of the topic
- Relationships should be meaningful and clearly labeled
- Keep concepts concise (1-3 words maximum)
- Ensure relationships form a coherent network"""

CONCEPT_MAP_SPEC_ZH = """10. concept_map:
生成一个概念图，展示复杂的概念关系。
{{
  "topic": "中心概念",
  "concepts": ["概念1", "概念2", ...],
  "relationships": [
    {{"from": "概念1", "to": "概念2", "label": "关系"}},
    ...
  ]
}}
要求：
- 概念应该多样化，涵盖主题的不同方面
- 关系应该有意义且标签清晰
- 保持概念简洁（最多1-3个词）
- 确保关系形成连贯的网络"""

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
