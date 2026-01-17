"""
Concept Maps Prompts

This module contains prompts for concept maps and related diagrams.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

# ============================================================================
# CONCEPT MAP PROMPTS
# ============================================================================

CONCEPT_MAP_GENERATION_EN = """
You are generating a concept map. Think in two steps internally, but OUTPUT ONLY the final JSON object.

Request: {user_prompt}

Step 1 (Idea expansion): produce 14–24 concise, distinct concepts strongly related to the topic. Use short noun/noun-phrase labels (≤4 words). Avoid duplicates and long sentences.

Step 2 (Relationships):
  2a. For each concept from Step 1, create exactly one directed relationship between the topic and that concept, using a short verb/verb-phrase (1–3 words). Choose the best direction (concept -> topic or topic -> concept).
  2b. Additionally, add several high-confidence concept–concept relationships (0–2 per concept, total 6–18). Each must be a single directed edge with a short verb/verb-phrase label.
  Examples: causes, leads to, is part of, includes, requires, results in, produces, regulates, is type of, consists of, connected to, located in.

Uniqueness constraints (very important):
- Exactly one relationship between the topic and any given concept (no duplicates in either direction).
- At most one relationship between any unordered pair of concepts (no duplicate or opposite-direction duplicates between the same pair).
- No self-loops.

Final OUTPUT (JSON only, no code fences):
{
  "topic": string,
  "concepts": [string, ...],
  "relationships": [{"from": string, "to": string, "label": string}, ...]
}

Rules:
- Relationship endpoints must be the topic or a concept from the list.
- Keep text brief; avoid punctuation except hyphens in terms.
- Do not include any fields other than topic, concepts, relationships.
"""

CONCEPT_MAP_GENERATION_ZH = """
你要生成“概念图”。按两个内部步骤思考，但最终只输出 JSON 对象。

需求：{user_prompt}

步骤 1（扩展概念）：列出 14–24 个与中心主题强相关的概念，使用简短名词/名词短语（≤4 个词），避免重复与长句。

步骤 2（关系）：
  2a. 对步骤 1 的每个概念，生成且仅生成 1 条“主题 与 该概念”之间的有向关系，使用 1–3 个词的动词/动词短语作为标签；根据含义选择方向（概念 -> 主题 或 主题 -> 概念）。
  2b. 另外补充若干概念–概念关系（每个概念 0–2 条，总计约 6–18 条），每条为单一有向边并使用简短动词/动词短语标签。
  示例标签：导致、引起、属于、包含、需要、产生、调节、是…的一种、由…组成、连接到、位于。

唯一性约束（非常重要）：
- “主题 与 任一概念”之间必须且仅能有 1 条关系（方向任选，但不得重复）。
- “任意两个概念”之间至多 1 条关系（同一无序对不得出现重复或反向重复）。
- 不允许自环（from 与 to 相同）。

最终输出（只输出 JSON，不要代码块）：
{
  "topic": "string",
  "concepts": ["string", ...],
  "relationships": [{"from": "string", "to": "string", "label": "string"}, ...]
}

规则：
- 关系两端必须是主题或概念列表中的项。
- 文本保持简短；除术语连字符外尽量不使用标点。
- 仅包含 topic、concepts、relationships 三个字段。
"""

# ============================================================================
# TWO-STAGE KEY/PARTS PROMPTS
# ============================================================================

CONCEPT_MAP_KEYS_GENERATION_EN = """
Generate key concepts for a concept map. OUTPUT ONLY JSON.

Input topic: {user_prompt}

Output JSON with EXACTLY:
{
  "topic": "Central topic (concise)",
  "keys": [
    {"name": "Key 1", "label": "verb phrase for topic→key (1–3 words)"},
    {"name": "Key 2", "label": "..."}
  ]
}

Rules:
- 4–8 keys; concise noun/noun-phrase; no duplicates; no code fences.
- Labels are short verb/verb-phrases (e.g., includes, regulates, influences).
"""

# ============================================================================
# UNIFIED (ONE-SHOT) PROMPTS
# ============================================================================

CONCEPT_MAP_UNIFIED_GENERATION_EN = """
Generate a complete concept map in ONE STRICT JSON. OUTPUT ONLY JSON.

Request: {user_prompt}

Output EXACTLY this shape (use ASCII double quotes, no trailing commas, no comments, no code fences; minify if needed):
{
  "topic": "Central topic (concise)",
  "keys": [
    {"name": "Key 1", "label": "topic→key verb phrase (1–3 words)"},
    {"name": "Key 2", "label": "..."}
  ],
  "key_parts": {
    "Key 1": [ {"name": "Part 1", "label": "key→part (1–3 words)"}, {"name": "Part 2", "label": "..."} ],
    "Key 2": [ {"name": "Part A", "label": "..."} ]
  },
  "relationships": [
    {"from": "Topic or Key or Part", "to": "Target", "label": "verb phrase"}
  ]
}

Strict rules (very important):
- 4–8 keys; each key concise and unique.
- For each key, 3–6 parts; concise and unique within that key.
- relationships must include every topic→key and key→part exactly once; may include a few key↔key or part↔part if helpful, but ensure uniqueness: no duplicate edges between the same unordered pair; no self-loops.
- Keep labels 1–3 words (e.g., includes, regulates, influences, results in). No code fences.
- Total unique concepts (keys + parts) ≤ 30.
"""

CONCEPT_MAP_UNIFIED_GENERATION_ZH = """
一次性生成完整“概念图”。只输出 严格 JSON（仅使用ASCII双引号，不要尾随逗号、不要注释、不要代码块）。

需求：{user_prompt}

输出格式（必须严格一致，必要时可压缩为单行）：
{
  "topic": "中心主题（简洁）",
  "keys": [
    {"name": "关键概念1", "label": "主题→关键 的动词短语（1–3个词）"},
    {"name": "关键概念2", "label": "..."}
  ],
  "key_parts": {
    "关键概念1": [ {"name": "子概念1", "label": "关键→子概念（1–3个词）"} ],
    "关键概念2": [ {"name": "子概念A", "label": "..."} ]
  },
  "relationships": [
    {"from": "主题或关键或子概念", "to": "目标概念", "label": "动词短语"}
  ]
}

严格规则（非常重要）：
- 4–8 个关键概念，简洁且唯一。
- 每个关键概念 3–6 个子概念，简洁且唯一。
- relationships 中必须包含所有 主题→关键 与 关键→子概念 各 1 条；可少量包含关键↔关键或子↔子，但要唯一：同一无序对最多 1 条；不允许自环。
- 标签为 1–3 个词（如：包含、调节、影响、导致）。不要代码块。
- 总概念数（关键+子概念）≤ 30。
"""

CONCEPT_MAP_KEYS_GENERATION_ZH = """
为概念图生成关键概念。只输出 JSON。

输入主题：{user_prompt}

输出必须为：
{
  "topic": "中心主题（简洁）",
  "keys": [
    {"name": "关键概念1", "label": "主题→关键的动词短语（1–3个词）"},
    {"name": "关键概念2", "label": "..."}
  ]
}

规则：
- 4–8 个关键概念；简短名词/名词短语；不重复；不要代码块。
- 关系标签用简短动词/动词短语（例如：包含、影响、调节）。
"""

CONCEPT_MAP_PARTS_GENERATION_EN = """
Generate sub-concepts for a key concept within a concept map. OUTPUT ONLY JSON.

Context:
Topic: {topic}
Key: {key}

Output JSON with EXACTLY:
{
  "key": "{key}",
  "parts": [
    {"name": "Part 1", "label": "verb phrase for key→part (1–3 words)"},
    {"name": "Part 2", "label": "..."}
  ]
}

Rules:
- 3–7 parts; concise noun/noun-phrase; no duplicates; no code fences.
- Labels are short verb/verb-phrases (e.g., includes, produces, related to).
"""

CONCEPT_MAP_PARTS_GENERATION_ZH = """
为某个关键概念生成子概念。只输出 JSON。

上下文：
主题：{topic}
关键概念：{key}

输出必须为：
{
  "key": "{key}",
  "parts": [
    {"name": "子概念1", "label": "关键→子概念 的动词短语（1–3个词）"},
    {"name": "子概念2", "label": "..."}
  ]
}

规则：
- 3–7 个子概念；简短名词/名词短语；不重复；不要代码块。
- 标签为简短动词/动词短语（例如：包含、产生、相关）。
"""

# ============================================================================
# SEMANTIC WEB PROMPTS
# ============================================================================



# ============================================================================
# ENHANCED CONCEPT MAP PROMPTS (IMPROVED VERSION)
# ============================================================================

CONCEPT_MAP_ENHANCED_STAGE1_EN = """
Generate a comprehensive list of 20-30 key concepts for a concept map. OUTPUT ONLY JSON.

Topic: {user_prompt}

CONCEPT GENERATION STRATEGY:
Think systematically about the topic from multiple perspectives:

1. CORE COMPONENTS: What are the fundamental parts or elements?
2. PROCESSES: What actions, steps, or procedures are involved?
3. CAUSES & EFFECTS: What leads to this topic? What results from it?
4. TYPES & CATEGORIES: What different forms or classifications exist?
5. CONTEXT & ENVIRONMENT: What surrounds or influences this topic?
6. TOOLS & METHODS: What is used to work with or study this topic?
7. PEOPLE & ROLES: Who is involved or affected?
8. TIME & SEQUENCE: What comes before, during, or after?

CONCEPT QUALITY RULES:
- Use concise noun phrases (2-4 words maximum)
- Make each concept distinct and non-overlapping
- Include both broad and specific concepts
- Avoid vague terms like "things" or "stuff"
- Use precise, domain-appropriate terminology
- Ensure concepts are directly related to the central topic

Output format:
{{
  "topic": "Central topic (concise)",
  "concepts": [
    "Concept 1",
    "Concept 2",
    "Concept 3"
  ]
}}

CRITICAL REQUIREMENTS:
- Exactly 20-30 concepts total
- Pure JSON only - no markdown, no code fences
- Each concept must be a short noun phrase
- No duplicates or overly similar concepts
- Ensure comprehensive coverage of the topic domain
"""

CONCEPT_MAP_ENHANCED_STAGE2_EN = """
Generate comprehensive relationships for a concept map. OUTPUT ONLY JSON.

Topic: {topic}
Concepts: {concepts}

RELATIONSHIP STRATEGY:
Create a rich network of meaningful connections:

1. CENTRAL RELATIONSHIPS: Topic → each concept (required)
2. HIERARCHICAL: Broader concepts → specific concepts
3. CAUSAL: What causes what? What leads to what?
4. COMPOSITIONAL: What is part of what? What contains what?
5. FUNCTIONAL: What enables what? What supports what?
6. TEMPORAL: What comes before/after what?
7. SPATIAL: What is located where? What surrounds what?
8. LOGICAL: What implies what? What is equivalent to what?

RELATIONSHIP LABELS:
Use precise, action-oriented verbs (1-3 words):
- CAUSAL: causes, triggers, leads to, results in, produces
- COMPOSITIONAL: includes, contains, consists of, is part of, comprises
- FUNCTIONAL: enables, supports, facilitates, requires, depends on
- TEMPORAL: precedes, follows, occurs during, happens before
- SPATIAL: located in, surrounds, adjacent to, within
- LOGICAL: implies, indicates, suggests, corresponds to
- PROCESS: transforms, converts, processes, modifies

Output format:
{{
  "relationships": [
    {{"from": "Source Concept", "to": "Target Concept", "label": "verb phrase"}}
  ]
}}

CRITICAL REQUIREMENTS:
- Include ALL topic→concept relationships (one per concept)
- Add 15-25 meaningful concept→concept connections
- Use short verb phrases (1-3 words maximum)
- No self-loops (from ≠ to)
- No duplicate relationships between the same pair
- Ensure logical consistency and meaningful connections
- Pure JSON only - no code fences or markdown
"""

# ============================================================================
# SIMPLIFIED TWO-STAGE CONCEPT MAP PROMPTS (RECOMMENDED)
# ============================================================================

CONCEPT_MAP_STAGE1_CONCEPTS_EN = """
Generate 20-30 key concepts for a concept map. OUTPUT ONLY JSON.

Topic: {user_prompt}

Generate concepts that are:
- Directly related to the central topic
- Diverse and comprehensive
- Concise (2-4 words max)
- Non-redundant

Output format:
{{
  "topic": "Central topic",
  "concepts": [
    "Concept 1",
    "Concept 2",
    "Concept 3"
  ]
}}

Rules:
- 20-30 concepts total
- Each concept should be a short noun phrase
- No duplicates
- No code fences or markdown
- Pure JSON only
"""

CONCEPT_MAP_STAGE2_RELATIONSHIPS_EN = """
Generate relationships for a concept map. OUTPUT ONLY JSON.

Topic: {topic}
Concepts: {concepts}

Create relationships between:
1. Topic → each concept (central relationships)
2. Concept → concept (cross-connections)

Output format:
{{
  "relationships": [
    {{"from": "Topic or Concept", "to": "Target", "label": "verb phrase"}}
  ]
}}

Rules:
- Include topic→concept relationships for ALL concepts
- Add 10-20 concept→concept relationships
- Use short verb phrases (1-3 words) like: causes, includes, leads to, is part of, requires
- No self-loops (from ≠ to)
- No duplicate relationships between same pair
- Pure JSON only, no code fences
"""

CONCEPT_MAP_ENHANCED_STAGE1_ZH = """
为概念图生成20-30个综合关键概念。只输出JSON。

主题：{user_prompt}

概念生成策略：
从多个角度系统思考主题：

1. 核心组件：有哪些基本部分或元素？
2. 过程：涉及哪些行动、步骤或程序？
3. 因果关系：什么导致这个主题？产生什么结果？
4. 类型分类：存在哪些不同形式或分类？
5. 背景环境：什么围绕或影响这个主题？
6. 工具方法：用什么来研究或处理这个主题？
7. 人员角色：谁参与或受影响？
8. 时间序列：之前、期间、之后发生什么？

概念质量规则：
- 使用简洁名词短语（最多2-4个词）
- 使每个概念独特且不重叠
- 包含广泛和具体的概念
- 避免模糊术语如"东西"或"物品"
- 使用精确、领域适当的术语
- 确保概念与中心主题直接相关

输出格式：
{{
  "topic": "中心主题（简洁）",
  "concepts": [
    "概念1",
    "概念2",
    "概念3"
  ]
}}

关键要求：
- 总共恰好20-30个概念
- 纯JSON格式 - 不要markdown，不要代码块
- 每个概念必须是简短名词短语
- 无重复或过于相似的概念
- 确保对主题领域的全面覆盖
"""

CONCEPT_MAP_ENHANCED_STAGE2_ZH = """
为概念图生成综合关系。只输出JSON。

主题：{topic}
概念：{concepts}

关系策略：
创建有意义连接的丰富网络：

1. 中心关系：主题 → 每个概念（必需）
2. 层次关系：广泛概念 → 具体概念
3. 因果关系：什么导致什么？什么引起什么？
4. 组成关系：什么是什么的一部分？什么包含什么？
5. 功能关系：什么促成什么？什么支持什么？
6. 时间关系：什么在什么之前/之后？
7. 空间关系：什么位于哪里？什么围绕什么？
8. 逻辑关系：什么暗示什么？什么等同于什么？

关系标签：
使用精确、行动导向的动词（1-3个词）：
- 因果：导致、触发、引起、产生、造成
- 组成：包含、由...组成、是...的一部分、构成
- 功能：促成、支持、促进、需要、依赖
- 时间：先于、跟随、在...期间发生、在...之前发生
- 空间：位于、围绕、邻近、在...内
- 逻辑：暗示、表明、建议、对应
- 过程：转换、改变、处理、修改

输出格式：
{{
  "relationships": [
    {{"from": "源概念", "to": "目标概念", "label": "动词短语"}}
  ]
}}

关键要求：
- 包含所有主题→概念关系（每个概念一条）
- 添加15-25个有意义的概念→概念连接
- 使用简短动词短语（最多1-3个词）
- 无自环（from ≠ to）
- 同一对概念间无重复关系
- 确保逻辑一致性和有意义连接
- 纯JSON格式 - 不要代码块或markdown
"""

CONCEPT_MAP_STAGE1_CONCEPTS_ZH = """
为概念图生成20-30个关键概念。只输出JSON。

主题：{user_prompt}

生成的概念应该：
- 与中心主题直接相关
- 多样且全面
- 简洁（最多2-4个词）
- 不重复

输出格式：
{{
  "topic": "中心主题",
  "concepts": [
    "概念1",
    "概念2",
    "概念3"
  ]
}}

规则：
- 总共20-30个概念
- 每个概念应该是简短的名词短语
- 不重复
- 不要代码块或markdown
- 纯JSON格式
"""

CONCEPT_MAP_STAGE2_RELATIONSHIPS_ZH = """
为概念图生成关系。只输出JSON。

主题：{topic}
概念：{concepts}

创建以下关系：
1. 主题 → 每个概念（中心关系）
2. 概念 → 概念（交叉连接）

输出格式：
{{
  "relationships": [
    {{"from": "主题或概念", "to": "目标", "label": "动词短语"}}
  ]
}}

规则：
- 包含所有主题→概念的关系
- 添加10-20个概念→概念的关系
- 使用简短动词短语（1-3个词），如：导致、包含、引起、属于、需要
- 无自环（from ≠ to）
- 同一对概念间无重复关系
- 纯JSON格式，不要代码块
"""

# ============================================================================
# HIERARCHICAL THREE-STAGE APPROACH
# ============================================================================

CONCEPT_MAP_HIERARCHICAL_STAGE1_EN = """
Generate 5-8 main categories for a concept map. OUTPUT ONLY JSON.

Topic: {user_prompt}

Output format:
{
  "topic": "Central topic",
  "categories": [
    "Category 1",
    "Category 2",
    "Category 3"
  ]
}

Rules:
- 5-8 main categories
- Each category should be a broad concept area
- Pure JSON only
"""

CONCEPT_MAP_HIERARCHICAL_STAGE2_EN = """
Generate sub-concepts for each category. OUTPUT ONLY JSON.

Topic: {topic}
Categories: {categories}

Output format:
{
  "sub_concepts": {
    "Category 1": ["Sub 1", "Sub 2", "Sub 3"],
    "Category 2": ["Sub A", "Sub B", "Sub C"]
  }
}

Rules:
- 3-5 sub-concepts per category
- Pure JSON only
"""

CONCEPT_MAP_HIERARCHICAL_STAGE3_EN = """
Generate relationships for hierarchical concept map. OUTPUT ONLY JSON.

Topic: {topic}
Categories: {categories}
Sub-concepts: {sub_concepts}

Create relationships:
1. Topic → each category
2. Each category → its sub-concepts
3. Cross-connections between related concepts

Output format:
{
  "relationships": [
    {"from": "Source", "to": "Target", "label": "verb phrase"}
  ]
}

Rules:
- Include all hierarchical relationships
- Add meaningful cross-connections
- Use short verb phrases (1-3 words)
- Pure JSON only
"""

# ============================================================================
# NETWORK-FIRST APPROACH
# ============================================================================

CONCEPT_MAP_NETWORK_STAGE1_EN = """
Generate a comprehensive list of 25-30 concepts for a concept map. OUTPUT ONLY JSON.

Topic: {user_prompt}

Generate concepts that:
- Cover all major aspects and dimensions of the topic
- Include core concepts, supporting ideas, and related phenomena
- Are diverse in scope (from broad to specific)
- Represent different perspectives and approaches
- Are concise noun phrases (2-4 words max)

Output format:
{{
  "topic": "Central topic",
  "concepts": [
    "Concept 1",
    "Concept 2",
    "Concept 3"
  ]
}}

Rules:
- Exactly 25-30 concepts total
- Each concept should be a short noun phrase
- No duplicates or overly similar concepts
- Pure JSON only, no code fences or markdown
- Ensure comprehensive coverage of the topic domain
"""

CONCEPT_MAP_NETWORK_STAGE2_EN = """
Generate a comprehensive relationship matrix for concepts. OUTPUT ONLY JSON.

Topic: {topic}
Concepts: {concepts}

Create a relationship matrix showing which concepts connect to which, including:
1. Central relationships: Topic → each concept
2. Cross-connections: Meaningful concept → concept relationships
3. Hierarchical relationships where applicable
4. Causal, logical, and associative connections

Output format:
{{
  "relationships": [
    {{"from": "Source", "to": "Target", "label": "verb phrase"}}
  ]
}}

Rules:
- Include ALL topic→concept relationships (one per concept)
- Add 15-30 meaningful concept→concept connections
- Use short verb phrases (1-3 words): causes, includes, leads to, is part of, requires, results in, produces, regulates, is type of, consists of, connected to, located in, influences, supports, enables
- No self-loops (from ≠ to)
- No duplicate relationships between other pairs
- Ensure the network shows meaningful connections and patterns
- Pure JSON only, no code fences
"""

CONCEPT_MAP_NETWORK_STAGE1_ZH = """
为概念图生成25-30个综合概念列表。只输出JSON。

主题：{user_prompt}

生成的概念应该：
- 涵盖主题的所有主要方面和维度
- 包括核心概念、支持性想法和相关现象
- 在范围上多样化（从广泛到具体）
- 代表不同的观点和方法
- 是简洁的名词短语（最多2-4个词）

输出格式：
{{
  "topic": "中心主题",
  "concepts": [
    "概念1",
    "概念2",
    "概念3"
  ]
}}

规则：
- 总共恰好25-30个概念
- 每个概念应该是简短的名词短语
- 无重复或过于相似的概念
- 纯JSON格式，不要代码块或markdown
- 确保对主题领域的全面覆盖
"""

CONCEPT_MAP_NETWORK_STAGE2_ZH = """
为概念生成综合关系矩阵。只输出JSON。

主题：{topic}
概念：{concepts}

创建关系矩阵，显示哪些概念相互连接，包括：
1. 中心关系：主题 → 每个概念
2. 交叉连接：有意义的概念 → 概念关系
3. 层次关系（如适用）
4. 因果、逻辑和关联连接

输出格式：
{{
  "relationships": [
    {{"from": "源概念", "to": "目标概念", "label": "动词短语"}}
  ]
}}

规则：
- 包含所有主题→概念关系（每个概念一条）
- 添加15-30个有意义的概念→概念连接
- 使用简短动词短语（1-3个词）：导致、包含、引起、属于、需要、产生、调节、是...的一种、由...组成、连接到、位于、影响、支持、促成
- 无自环（from ≠ to）
- 同一对概念间无重复关系
- 确保网络显示有意义的连接和模式
- 纯JSON格式，不要代码块
"""

# ============================================================================
# TEMPLATE-BASED APPROACH
# ============================================================================

CONCEPT_MAP_TEMPLATE_STAGE1_EN = """
Generate concepts using relationship templates. OUTPUT ONLY JSON.

Topic: {user_prompt}

Use these relationship templates to generate concepts:
- CAUSES: What causes this topic?
- INCLUDES: What does this topic include?
- REQUIRES: What does this topic require?
- RESULTS_IN: What results from this topic?
- IS_TYPE_OF: What types exist?
- LOCATED_IN: Where is this topic located?

Output format:
{
  "topic": "Central topic",
  "concepts": [
    "Concept 1",
    "Concept 2",
    "Concept 3"
  ]
}

Rules:
- 20-30 concepts using the templates
- Pure JSON only
"""

# ============================================================================
# TEMPLATE-BASED CONCEPT EXTRACTION (NEW)
# ============================================================================

CONCEPT_MAP_TEMPLATE_EXTRACTION_EN = """
Extract concepts using systematic templates. OUTPUT ONLY JSON.

Topic: {user_prompt}

Use these extraction templates to generate concepts:

1. COMPONENT TEMPLATES:
   - "What are the main parts of [topic]?"
   - "What elements make up [topic]?"
   - "What components are essential to [topic]?"

2. PROCESS TEMPLATES:
   - "What steps are involved in [topic]?"
   - "What procedures are used for [topic]?"
   - "What actions are taken in [topic]?"

3. CAUSE-EFFECT TEMPLATES:
   - "What causes [topic] to happen?"
   - "What results from [topic]?"
   - "What triggers [topic]?"

4. CLASSIFICATION TEMPLATES:
   - "What types of [topic] exist?"
   - "What categories can [topic] be divided into?"
   - "What forms does [topic] take?"

5. CONTEXT TEMPLATES:
   - "What environment does [topic] exist in?"
   - "What conditions affect [topic]?"
   - "What surrounds [topic]?"

6. FUNCTION TEMPLATES:
   - "What is the purpose of [topic]?"
   - "What does [topic] accomplish?"
   - "What role does [topic] play?"

Output format:
{{
  "topic": "Central topic",
  "concepts": [
    "Concept 1",
    "Concept 2",
    "Concept 3"
  ]
}}

Rules:
- Generate 20-30 concepts using the templates
- Each concept should be a concise noun phrase (2-4 words)
- Ensure diversity across all template categories
- Pure JSON only, no code fences
"""

CONCEPT_MAP_TEMPLATE_EXTRACTION_ZH = """
使用系统模板提取概念。只输出JSON。

主题：{user_prompt}

使用这些提取模板生成概念：

1. 组件模板：
   - "[主题]的主要部分是什么？"
   - "什么元素构成[主题]？"
   - "什么组件对[主题]是必需的？"

2. 过程模板：
   - "[主题]涉及哪些步骤？"
   - "什么程序用于[主题]？"
   - "[主题]中采取什么行动？"

3. 因果模板：
   - "什么导致[主题]发生？"
   - "[主题]产生什么结果？"
   - "什么触发[主题]？"

4. 分类模板：
   - "存在什么类型的[主题]？"
   - "[主题]可以分成什么类别？"
   - "[主题]采取什么形式？"

5. 背景模板：
   - "[主题]存在于什么环境中？"
   - "什么条件影响[主题]？"
   - "什么围绕[主题]？"

6. 功能模板：
   - "[主题]的目的是什么？"
   - "[主题]完成什么？"
   - "[主题]扮演什么角色？"

输出格式：
{{
  "topic": "中心主题",
  "concepts": [
    "概念1",
    "概念2",
    "概念3"
  ]
}}

规则：
- 使用模板生成20-30个概念
- 每个概念应该是简洁名词短语（2-4个词）
- 确保所有模板类别的多样性
- 纯JSON格式，不要代码块
"""

# ============================================================================
# QUALITY-FOCUSED CONCEPT GENERATION (NEW)
# ============================================================================

CONCEPT_MAP_QUALITY_FOCUSED_EN = """
Generate high-quality concepts with quality control. OUTPUT ONLY JSON.

Topic: {user_prompt}

QUALITY CHECKLIST - Generate concepts that pass ALL checks:

✓ SPECIFICITY: Each concept is specific and concrete, not vague
✓ RELEVANCE: Directly related to the central topic
✓ DIVERSITY: Covers different aspects, perspectives, and levels
✓ CLARITY: Clear meaning, no ambiguous terms
✓ COMPLETENESS: Comprehensive coverage of the topic domain
✓ BALANCE: Mix of broad categories and specific instances
✓ UNIQUENESS: No duplicate or overly similar concepts
✓ ACTIONABILITY: Concepts that can be meaningfully connected

CONCEPT TYPES TO INCLUDE:
- Core/central concepts (fundamental to the topic)
- Supporting concepts (reinforce or explain core concepts)
- Contextual concepts (environment, conditions, background)
- Process concepts (steps, procedures, methods)
- Outcome concepts (results, effects, consequences)
- Tool concepts (instruments, technologies, resources)
- People concepts (roles, stakeholders, participants)

AVOID THESE COMMON PITFALLS:
- Vague terms like "things", "stuff", "etc."
- Overly broad concepts that are too general
- Concepts that are too specific to be useful
- Concepts that are not directly related to the topic
- Duplicate concepts with different wording
- Concepts that are too similar to each other

Output format:
{{
  "topic": "Central topic",
  "concepts": [
    "Concept 1",
    "Concept 2",
    "Concept 3"
  ]
}}

Rules:
- Generate exactly 20-30 concepts
- Each concept must pass the quality checklist
- Use concise noun phrases (2-4 words maximum)
- Pure JSON only, no code fences or markdown
"""

CONCEPT_MAP_QUALITY_FOCUSED_ZH = """
生成高质量概念并进行质量控制。只输出JSON。

主题：{user_prompt}

质量检查清单 - 生成通过所有检查的概念：

✓ 具体性：每个概念具体明确，不模糊
✓ 相关性：与中心主题直接相关
✓ 多样性：涵盖不同方面、观点和层次
✓ 清晰性：含义清楚，无歧义术语
✓ 完整性：对主题领域的全面覆盖
✓ 平衡性：广泛类别和具体实例的混合
✓ 独特性：无重复或过于相似的概念
✓ 可操作性：可以有意义连接的概念

要包含的概念类型：
- 核心/中心概念（对主题至关重要）
- 支持概念（强化或解释核心概念）
- 背景概念（环境、条件、背景）
- 过程概念（步骤、程序、方法）
- 结果概念（结果、效果、后果）
- 工具概念（工具、技术、资源）
- 人员概念（角色、利益相关者、参与者）

避免这些常见陷阱：
- 模糊术语如"东西"、"物品"、"等等"
- 过于广泛而无法使用的概念
- 过于具体而无法使用的概念
- 与主题不直接相关的概念
- 用不同措辞表达的重复概念
- 彼此过于相似的概念

输出格式：
{{
  "topic": "中心主题",
  "concepts": [
    "概念1",
    "概念2",
    "概念3"
  ]
}}

规则：
- 恰好生成20-30个概念
- 每个概念必须通过质量检查清单
- 使用简洁名词短语（最多2-4个词）
- 纯JSON格式，不要代码块或markdown
"""

CONCEPT_MAP_TEMPLATE_STAGE2_EN = """
Fill relationship matrix using templates. OUTPUT ONLY JSON.

Topic: {topic}
Concepts: {concepts}

Use these relationship types:
- causes, includes, requires, results_in, is_type_of, located_in
- Add cross-connections between related concepts

Output format:
{
  "relationships": [
    {"from": "Source", "to": "Target", "label": "verb phrase"}
  ]
}

Rules:
- Apply template relationships systematically
- Add meaningful cross-connections
- Pure JSON only
"""

# ============================================================================
# ENHANCED CONCEPT MAP PROMPTS (IMPROVED VERSION)
# ============================================================================

CONCEPT_MAP_ENHANCED_STAGE1_EN = """
Generate a comprehensive list of 20-30 key concepts for a concept map. OUTPUT ONLY JSON.

Topic: {user_prompt}

CONCEPT GENERATION STRATEGY:
Think systematically about the topic from multiple perspectives:

1. CORE COMPONENTS: What are the fundamental parts or elements?
2. PROCESSES: What actions, steps, or procedures are involved?
3. CAUSES & EFFECTS: What leads to this topic? What results from it?
4. TYPES & CATEGORIES: What different forms or classifications exist?
5. CONTEXT & ENVIRONMENT: What surrounds or influences this topic?
6. TOOLS & METHODS: What is used to work with or study this topic?
7. PEOPLE & ROLES: Who is involved or affected?
8. TIME & SEQUENCE: What comes before, during, or after?

CONCEPT QUALITY RULES:
- Use concise noun phrases (2-4 words maximum)
- Make each concept distinct and non-overlapping
- Include both broad and specific concepts
- Avoid vague terms like "things" or "stuff"
- Use precise, domain-appropriate terminology
- Ensure concepts are directly related to the central topic

Output format:
{{
  "topic": "Central topic (concise)",
  "concepts": [
    "Concept 1",
    "Concept 2",
    "Concept 3"
  ]
}}

CRITICAL REQUIREMENTS:
- Exactly 20-30 concepts total
- Pure JSON only - no markdown, no code fences
- Each concept must be a short noun phrase
- No duplicates or overly similar concepts
- Ensure comprehensive coverage of the topic domain
"""

CONCEPT_MAP_ENHANCED_STAGE2_EN = """
Generate comprehensive relationships for a concept map. OUTPUT ONLY JSON.

Topic: {topic}
Concepts: {concepts}

RELATIONSHIP STRATEGY:
Create a rich network of meaningful connections:

1. CENTRAL RELATIONSHIPS: Topic → each concept (required)
2. HIERARCHICAL: Broader concepts → specific concepts
3. CAUSAL: What causes what? What leads to what?
4. COMPOSITIONAL: What is part of what? What contains what?
5. FUNCTIONAL: What enables what? What supports what?
6. TEMPORAL: What comes before/after what?
7. SPATIAL: What is located where? What surrounds what?
8. LOGICAL: What implies what? What is equivalent to what?

RELATIONSHIP LABELS:
Use precise, action-oriented verbs (1-3 words):
- CAUSAL: causes, triggers, leads to, results in, produces
- COMPOSITIONAL: includes, contains, consists of, is part of, comprises
- FUNCTIONAL: enables, supports, facilitates, requires, depends on
- TEMPORAL: precedes, follows, occurs during, happens before
- SPATIAL: located in, surrounds, adjacent to, within
- LOGICAL: implies, indicates, suggests, corresponds to
- PROCESS: transforms, converts, processes, modifies

Output format:
{{
  "relationships": [
    {{"from": "Source Concept", "to": "Target Concept", "label": "precise verb phrase"}}
  ]
}}

CRITICAL REQUIREMENTS:
- Include ALL topic→concept relationships (one per concept)
- Add 15-25 meaningful concept→concept connections
- Use short verb phrases (1-3 words maximum)
- No self-loops (from ≠ to)
- No duplicate relationships between the same pair
- Ensure logical consistency and meaningful connections
- Pure JSON only - no code fences or markdown
"""

CONCEPT_MAP_ENHANCED_STAGE1_ZH = """
为概念图生成20-30个综合关键概念。只输出JSON。

主题：{user_prompt}

概念生成策略：
从多个角度系统思考主题：

1. 核心组件：有哪些基本部分或元素？
2. 过程：涉及哪些行动、步骤或程序？
3. 因果关系：什么导致这个主题？产生什么结果？
4. 类型分类：存在哪些不同形式或分类？
5. 背景环境：什么围绕或影响这个主题？
6. 工具方法：用什么来研究或处理这个主题？
7. 人员角色：谁参与或受影响？
8. 时间序列：之前、期间、之后发生什么？

概念质量规则：
- 使用简洁名词短语（最多2-4个词）
- 使每个概念独特且不重叠
- 包含广泛和具体的概念
- 避免模糊术语如"东西"或"物品"
- 使用精确、领域适当的术语
- 确保概念与中心主题直接相关

输出格式：
{{
  "topic": "中心主题（简洁）",
  "concepts": [
    "概念1",
    "概念2",
    "概念3"
  ]
}}

关键要求：
- 总共恰好20-30个概念
- 纯JSON格式 - 不要markdown，不要代码块
- 每个概念必须是简短名词短语
- 无重复或过于相似的概念
- 确保对主题领域的全面覆盖
"""

CONCEPT_MAP_ENHANCED_STAGE2_ZH = """
为概念图生成综合关系。只输出JSON。

主题：{topic}
概念：{concepts}

关系策略：
创建有意义连接的丰富网络：

1. 中心关系：主题 → 每个概念（必需）
2. 层次关系：广泛概念 → 具体概念
3. 因果关系：什么导致什么？什么引起什么？
4. 组成关系：什么是什么的一部分？什么包含什么？
5. 功能关系：什么促成什么？什么支持什么？
6. 时间关系：什么在什么之前/之后？
7. 空间关系：什么位于哪里？什么围绕什么？
8. 逻辑关系：什么暗示什么？什么等同于什么？

关系标签：
使用精确、行动导向的动词（1-3个词）：
- 因果：导致、触发、引起、产生、造成
- 组成：包含、由...组成、是...的一部分、构成
- 功能：促成、支持、促进、需要、依赖
- 时间：先于、跟随、在...期间发生、在...之前发生
- 空间：位于、围绕、邻近、在...内
- 逻辑：暗示、表明、建议、对应
- 过程：转换、改变、处理、修改

输出格式：
{{
  "relationships": [
    {{"from": "源概念", "to": "目标概念", "label": "动词短语"}}
  ]
}}

关键要求：
- 包含所有主题→概念关系（每个概念一条）
- 添加15-25个有意义的概念→概念连接
- 使用简短动词短语（最多1-3个词）
- 无自环（from ≠ to）
- 同一对概念间无重复关系
- 确保逻辑一致性和有意义连接
- 纯JSON格式 - 不要代码块或markdown
"""

# ============================================================================
# TEMPLATE-BASED CONCEPT EXTRACTION (NEW)
# ============================================================================

CONCEPT_MAP_TEMPLATE_EXTRACTION_EN = """
Extract concepts using systematic templates. OUTPUT ONLY JSON.

Topic: {user_prompt}

Use these extraction templates to generate concepts:

1. COMPONENT TEMPLATES:
   - "What are the main parts of [topic]?"
   - "What elements make up [topic]?"
   - "What components are essential to [topic]?"

2. PROCESS TEMPLATES:
   - "What steps are involved in [topic]?"
   - "What procedures are used for [topic]?"
   - "What actions are taken in [topic]?"

3. CAUSE-EFFECT TEMPLATES:
   - "What causes [topic] to happen?"
   - "What results from [topic]?"
   - "What triggers [topic]?"

4. CLASSIFICATION TEMPLATES:
   - "What types of [topic] exist?"
   - "What categories can [topic] be divided into?"
   - "What forms does [topic] take?"

5. CONTEXT TEMPLATES:
   - "What environment does [topic] exist in?"
   - "What conditions affect [topic]?"
   - "What surrounds [topic]?"

6. FUNCTION TEMPLATES:
   - "What is the purpose of [topic]?"
   - "What does [topic] accomplish?"
   - "What role does [topic] play?"

Output format:
{{
  "topic": "Central topic",
  "concepts": [
    "Concept 1",
    "Concept 2",
    "Concept 3"
  ]
}}

Rules:
- Generate 20-30 concepts using the templates
- Each concept should be a concise noun phrase (2-4 words)
- Ensure diversity across all template categories
- Pure JSON only, no code fences
"""

CONCEPT_MAP_TEMPLATE_EXTRACTION_ZH = """
使用系统模板提取概念。只输出JSON。

主题：{user_prompt}

使用这些提取模板生成概念：

1. 组件模板：
   - "[主题]的主要部分是什么？"
   - "什么元素构成[主题]？"
   - "什么组件对[主题]是必需的？"

2. 过程模板：
   - "[主题]涉及哪些步骤？"
   - "什么程序用于[主题]？"
   - "[主题]中采取什么行动？"

3. 因果模板：
   - "什么导致[主题]发生？"
   - "[主题]产生什么结果？"
   - "什么触发[主题]？"

4. 分类模板：
   - "存在什么类型的[主题]？"
   - "[主题]可以分成什么类别？"
   - "[主题]采取什么形式？"

5. 背景模板：
   - "[主题]存在于什么环境中？"
   - "什么条件影响[主题]？"
   - "什么围绕[主题]？"

6. 功能模板：
   - "[主题]的目的是什么？"
   - "[主题]完成什么？"
   - "[主题]扮演什么角色？"

输出格式：
{{
  "topic": "中心主题",
  "concepts": [
    "概念1",
    "概念2",
    "概念3"
  ]
}}

规则：
- 使用模板生成20-30个概念
- 每个概念应该是简洁名词短语（2-4个词）
- 确保所有模板类别的多样性
- 纯JSON格式，不要代码块
"""

# ============================================================================
# QUALITY-FOCUSED CONCEPT GENERATION (NEW)
# ============================================================================

CONCEPT_MAP_QUALITY_FOCUSED_EN = """
Generate high-quality concepts with quality control. OUTPUT ONLY JSON.

Topic: {user_prompt}

QUALITY CHECKLIST - Generate concepts that pass ALL checks:

✓ SPECIFICITY: Each concept is specific and concrete, not vague
✓ RELEVANCE: Directly related to the central topic
✓ DIVERSITY: Covers different aspects, perspectives, and levels
✓ CLARITY: Clear meaning, no ambiguous terms
✓ COMPLETENESS: Comprehensive coverage of the topic domain
✓ BALANCE: Mix of broad categories and specific instances
✓ UNIQUENESS: No duplicate or overly similar concepts
✓ ACTIONABILITY: Concepts that can be meaningfully connected

CONCEPT TYPES TO INCLUDE:
- Core/central concepts (fundamental to the topic)
- Supporting concepts (reinforce or explain core concepts)
- Contextual concepts (environment, conditions, background)
- Process concepts (steps, procedures, methods)
- Outcome concepts (results, effects, consequences)
- Tool concepts (instruments, technologies, resources)
- People concepts (roles, stakeholders, participants)

AVOID THESE COMMON PITFALLS:
- Vague terms like "things", "stuff", "etc."
- Overly broad concepts that are too general
- Concepts that are too specific to be useful
- Concepts that are not directly related to the topic
- Duplicate concepts with different wording
- Concepts that are too similar to each other

Output format:
{{
  "topic": "Central topic",
  "concepts": [
    "Concept 1",
    "Concept 2",
    "Concept 3"
  ]
}}

Rules:
- Generate exactly 20-30 concepts
- Each concept must pass the quality checklist
- Use concise noun phrases (2-4 words maximum)
- Pure JSON only, no code fences or markdown
"""

CONCEPT_MAP_QUALITY_FOCUSED_ZH = """
生成高质量概念并进行质量控制。只输出JSON。

主题：{user_prompt}

质量检查清单 - 生成通过所有检查的概念：

✓ 具体性：每个概念具体明确，不模糊
✓ 相关性：与中心主题直接相关
✓ 多样性：涵盖不同方面、观点和层次
✓ 清晰性：含义清楚，无歧义术语
✓ 完整性：对主题领域的全面覆盖
✓ 平衡性：广泛类别和具体实例的混合
✓ 独特性：无重复或过于相似的概念
✓ 可操作性：可以有意义连接的概念

要包含的概念类型：
- 核心/中心概念（对主题至关重要）
- 支持概念（强化或解释核心概念）
- 背景概念（环境、条件、背景）
- 过程概念（步骤、程序、方法）
- 结果概念（结果、效果、后果）
- 工具概念（工具、技术、资源）
- 人员概念（角色、利益相关者、参与者）

避免这些常见陷阱：
- 模糊术语如"东西"、"物品"、"等等"
- 过于广泛而无法使用的概念
- 过于具体而无法使用的概念
- 与主题不直接相关的概念
- 用不同措辞表达的重复概念
- 彼此过于相似的概念

输出格式：
{{
  "topic": "中心主题",
  "concepts": [
    "概念1",
    "概念2",
    "概念3"
  ]
}}

规则：
- 恰好生成20-30个概念
- 每个概念必须通过质量检查清单
- 使用简洁名词短语（最多2-4个词）
- 纯JSON格式，不要代码块或markdown
"""

# ============================================================================
# TRUE 3-STAGE WORKFLOW PROMPTS (NEW)
# ============================================================================

CONCEPT_MAP_TOPIC_EXTRACTION_EN = """
Extract the central topic from this user prompt. OUTPUT ONLY JSON.

User prompt: {user_prompt}

Instructions:
- Identify the main subject or theme the user wants to explore
- Extract a concise, focused central topic (2-5 words)
- The topic should be clear and specific enough to generate meaningful concepts around

Output format:
{{
  "central_topic": "Extracted central topic"
}}

Rules:
- Pure JSON only, no code fences or markdown
- Topic should be a clear noun phrase
- Focus on the main subject, not secondary details
"""

CONCEPT_MAP_TOPIC_EXTRACTION_ZH = """
从用户提示中提取中心主题。只输出JSON。

用户提示：{user_prompt}

指令：
- 识别用户想要探索的主要主题或话题
- 提取简洁、重点突出的中心主题（2-5个词）
- 主题应该清晰具体，足以围绕其生成有意义的概念

输出格式：
{{
  "central_topic": "提取的中心主题"
}}

规则：
- 纯JSON格式，不要代码块或markdown
- 主题应该是清晰的名词短语
- 专注于主要主题，不是次要细节
"""

CONCEPT_MAP_30_CONCEPTS_EN = """
Generate exactly 30 key concepts related to this central topic. OUTPUT ONLY JSON.

Central topic: {central_topic}

CONCEPT GENERATION STRATEGY:
Think systematically about the topic from multiple perspectives:

1. CORE COMPONENTS: What are the fundamental parts or elements?
2. PROCESSES: What actions, steps, or procedures are involved?
3. CAUSES & EFFECTS: What leads to this topic? What results from it?
4. TYPES & CATEGORIES: What different forms or classifications exist?
5. CONTEXT & ENVIRONMENT: What surrounds or influences this topic?
6. TOOLS & METHODS: What is used to work with or study this topic?
7. PEOPLE & ROLES: Who is involved or affected?
8. TIME & SEQUENCE: What comes before, during, or after?

CONCEPT QUALITY RULES:
- Use concise noun phrases (2-4 words maximum)
- Make each concept distinct and non-overlapping
- Include both broad and specific concepts
- Avoid vague terms like "things" or "stuff"
- Use precise, domain-appropriate terminology
- Ensure concepts are directly related to the central topic

Output format:
{{
  "concepts": [
    "Concept 1",
    "Concept 2",
    "Concept 3"
  ]
}}

CRITICAL REQUIREMENTS:
- Exactly 30 concepts total (no more, no less)
- Pure JSON only - no markdown, no code fences
- Each concept must be a short noun phrase
- No duplicates or overly similar concepts
- Ensure comprehensive coverage of the topic domain
"""

CONCEPT_MAP_30_CONCEPTS_ZH = """
为这个中心主题生成恰好30个关键概念。只输出JSON。

中心主题：{central_topic}

概念生成策略：
从多个角度系统思考主题：

1. 核心组件：有哪些基本部分或元素？
2. 过程：涉及哪些行动、步骤或程序？
3. 因果关系：什么导致这个主题？产生什么结果？
4. 类型分类：存在哪些不同形式或分类？
5. 背景环境：什么围绕或影响这个主题？
6. 工具方法：用什么来研究或处理这个主题？
7. 人员角色：谁参与或受影响？
8. 时间序列：之前、期间、之后发生什么？

概念质量规则：
- 使用简洁名词短语（最多2-4个词）
- 使每个概念独特且不重叠
- 包含广泛和具体的概念
- 避免模糊术语如"东西"或"物品"
- 使用精确、领域适当的术语
- 确保概念与中心主题直接相关

输出格式：
{{
  "concepts": [
    "概念1",
    "概念2",
    "概念3"
  ]
}}

关键要求：
- 恰好30个概念（不多不少）
- 纯JSON格式 - 不要markdown，不要代码块
- 每个概念必须是简短名词短语
- 无重复或过于相似的概念
- 确保对主题领域的全面覆盖
"""

CONCEPT_MAP_3_STAGE_RELATIONSHIPS_EN = """
Generate comprehensive relationships for a concept map. OUTPUT ONLY JSON.

Central topic: {central_topic}
Concepts: {concepts}

RELATIONSHIP STRATEGY:
Create a rich network of meaningful connections:

1. CENTRAL RELATIONSHIPS: Central topic → each concept (required - 30 relationships)
2. HIERARCHICAL: Broader concepts → specific concepts
3. CAUSAL: What causes what? What leads to what?
4. COMPOSITIONAL: What is part of what? What contains what?
5. FUNCTIONAL: What enables what? What supports what?
6. TEMPORAL: What comes before/after what?
7. SPATIAL: What is located where? What surrounds what?
8. LOGICAL: What implies what? What is equivalent to what?

RELATIONSHIP LABELS:
Use precise, action-oriented verbs (1-3 words):
- CAUSAL: causes, triggers, leads to, results in, produces
- COMPOSITIONAL: includes, contains, consists of, is part of, comprises
- FUNCTIONAL: enables, supports, facilitates, requires, depends on
- TEMPORAL: precedes, follows, occurs during, happens before
- SPATIAL: located in, surrounds, adjacent to, within
- LOGICAL: implies, indicates, suggests, corresponds to
- PROCESS: transforms, converts, processes, modifies

Output format:
{{
  "relationships": [
    {{"from": "Source Concept", "to": "Target Concept", "label": "precise verb phrase"}}
  ]
}}

CRITICAL REQUIREMENTS:
- Include ALL central_topic→concept relationships (exactly 30)
- Add 20-30 meaningful concept→concept connections
- Use short verb phrases (1-3 words maximum)
- No self-loops (from ≠ to)
- No duplicate relationships between the same pair
- Ensure logical consistency and meaningful connections
- Pure JSON only - no code fences or markdown
"""

CONCEPT_MAP_3_STAGE_RELATIONSHIPS_ZH = """
为概念图生成综合关系。只输出JSON。

中心主题：{central_topic}
概念：{concepts}

关系策略：
创建有意义连接的丰富网络：

1. 中心关系：中心主题 → 每个概念（必需 - 30个关系）
2. 层次关系：广泛概念 → 具体概念
3. 因果关系：什么导致什么？什么引起什么？
4. 组成关系：什么是什么的一部分？什么包含什么？
5. 功能关系：什么促成什么？什么支持什么？
6. 时间关系：什么在什么之前/之后？
7. 空间关系：什么位于哪里？什么围绕什么？
8. 逻辑关系：什么暗示什么？什么等同于什么？

关系标签：
使用精确、行动导向的动词（1-3个词）：
- 因果：导致、触发、引起、产生、造成
- 组成：包含、由...组成、是...的一部分、构成
- 功能：促成、支持、促进、需要、依赖
- 时间：先于、跟随、在...期间发生、在...之前发生
- 空间：位于、围绕、邻近、在...内
- 逻辑：暗示、表明、建议、对应
- 过程：转换、改变、处理、修改

输出格式：
{{
  "relationships": [
    {{"from": "源概念", "to": "目标概念", "label": "精确动词短语"}}
  ]
}}

关键要求：
- 包含所有中心主题→概念关系（恰好30个）
- 添加20-30个有意义的概念→概念连接
- 使用简短动词短语（最多1-3个词）
- 无自环（from ≠ to）
- 同一对概念间无重复关系
- 确保逻辑一致性和有意义连接
- 纯JSON格式 - 不要代码块或markdown
"""

# ============================================================================
# RELATIONSHIP QUALITY ENHANCEMENT (NEW)
# ============================================================================

CONCEPT_MAP_RELATIONSHIP_QUALITY_EN = """
Generate high-quality relationships with semantic validation. OUTPUT ONLY JSON.

Topic: {topic}
Concepts: {concepts}

RELATIONSHIP QUALITY STANDARDS:
Each relationship must be:
✓ SEMANTICALLY VALID: The connection makes logical sense
✓ SPECIFIC: Clear and precise relationship type
✓ MEANINGFUL: Adds value to understanding the topic
✓ NON-REDUNDANT: No duplicate or overly similar connections
✓ DIRECTIONALLY CORRECT: From source to target makes sense
✓ LABELED APPROPRIATELY: Verb phrase accurately describes the connection

RELATIONSHIP CATEGORIES TO COVER:

1. STRUCTURAL RELATIONSHIPS:
   - Composition: "includes", "contains", "consists of", "is part of"
   - Classification: "is type of", "belongs to", "categorized as"
   - Hierarchy: "subsumes", "encompasses", "broader than"

2. FUNCTIONAL RELATIONSHIPS:
   - Causation: "causes", "leads to", "results in", "triggers"
   - Dependence: "requires", "depends on", "needs", "relies on"
   - Support: "enables", "facilitates", "supports", "assists"

3. TEMPORAL RELATIONSHIPS:
   - Sequence: "precedes", "follows", "comes before", "happens after"
   - Duration: "occurs during", "takes place in", "lasts for"
   - Timing: "synchronizes with", "coincides with"

4. SPATIAL RELATIONSHIPS:
   - Location: "located in", "situated at", "found in", "positioned at"
   - Proximity: "adjacent to", "near", "surrounds", "borders"
   - Containment: "within", "inside", "enclosed by"

5. LOGICAL RELATIONSHIPS:
   - Implication: "implies", "indicates", "suggests", "implies"
   - Equivalence: "equals", "equivalent to", "same as", "identical to"
   - Opposition: "contrasts with", "opposes", "conflicts with"

Output format:
{{
  "relationships": [
    {{"from": "Source Concept", "to": "Target Concept", "label": "precise verb phrase"}}
  ]
}}

CRITICAL REQUIREMENTS:
- Include ALL topic→concept relationships (one per concept)
- Add 15-25 high-quality concept→concept connections
- Use precise verb phrases (1-3 words maximum)
- No self-loops (from ≠ to)
- No duplicate relationships between the same pair
- Each relationship must pass quality standards
- Pure JSON only - no code fences or markdown
"""

CONCEPT_MAP_RELATIONSHIP_QUALITY_ZH = """
生成高质量关系并进行语义验证。只输出JSON。

主题：{topic}
概念：{concepts}

关系质量标准：
每个关系必须：
✓ 语义有效：连接在逻辑上有意义
✓ 具体：清晰精确的关系类型
✓ 有意义：增加对主题的理解价值
✓ 非冗余：无重复或过于相似的连接
✓ 方向正确：从源到目标有意义
✓ 标签适当：动词短语准确描述连接

要涵盖的关系类别：

1. 结构关系：
   - 组成："包含"、"由...组成"、"是...的一部分"
   - 分类："是...的类型"、"属于"、"归类为"
   - 层次："包含"、"涵盖"、"比...更广泛"

2. 功能关系：
   - 因果："导致"、"引起"、"产生"、"触发"
   - 依赖："需要"、"依赖"、"要求"、"依靠"
   - 支持："促成"、"促进"、"支持"、"协助"

3. 时间关系：
   - 顺序："先于"、"跟随"、"在...之前"、"在...之后发生"
   - 持续："在...期间发生"、"在...中发生"、"持续"
   - 时间："与...同步"、"与...同时发生"

4. 空间关系：
   - 位置："位于"、"坐落于"、"发现于"、"定位于"
   - 邻近："邻近"、"靠近"、"围绕"、"毗邻"
   - 包含："在...内"、"在...里面"、"被...包围"

5. 逻辑关系：
   - 暗示："暗示"、"表明"、"建议"、"意味着"
   - 等价："等于"、"等同于"、"与...相同"、"与...一致"
   - 对立："与...对比"、"反对"、"与...冲突"

输出格式：
{{
  "relationships": [
    {{"from": "源概念", "to": "目标概念", "label": "精确动词短语"}}
  ]
}}

关键要求：
- 包含所有主题→概念关系（每个概念一条）
- 添加15-25个高质量概念→概念连接
- 使用精确动词短语（最多1-3个词）
- 无自环（from ≠ to）
- 同一对概念间无重复关系
- 每个关系必须通过质量标准
- 纯JSON格式 - 不要代码块或markdown
"""

# ============================================================================
# PROMPT REGISTRY
# ============================================================================

CONCEPT_MAP_PROMPTS = {
    # Original prompts (kept for backward compatibility)
    "concept_map_generation_en": CONCEPT_MAP_GENERATION_EN,
    "concept_map_generation_zh": CONCEPT_MAP_GENERATION_ZH,
    "concept_map_unified_generation_en": CONCEPT_MAP_UNIFIED_GENERATION_EN,
    "concept_map_unified_generation_zh": CONCEPT_MAP_UNIFIED_GENERATION_ZH,
    "concept_map_keys_generation_en": CONCEPT_MAP_KEYS_GENERATION_EN,
    "concept_map_keys_generation_zh": CONCEPT_MAP_KEYS_GENERATION_ZH,
    "concept_map_parts_generation_en": CONCEPT_MAP_PARTS_GENERATION_EN,
    "concept_map_parts_generation_zh": CONCEPT_MAP_PARTS_GENERATION_ZH,


    # NEW: True 3-stage workflow prompts (RECOMMENDED)
    "concept_map_topic_extraction_en": CONCEPT_MAP_TOPIC_EXTRACTION_EN,
    "concept_map_topic_extraction_zh": CONCEPT_MAP_TOPIC_EXTRACTION_ZH,
    "concept_map_30_concepts_en": CONCEPT_MAP_30_CONCEPTS_EN,
    "concept_map_30_concepts_zh": CONCEPT_MAP_30_CONCEPTS_ZH,
    "concept_map_3_stage_relationships_en": CONCEPT_MAP_3_STAGE_RELATIONSHIPS_EN,
    "concept_map_3_stage_relationships_zh": CONCEPT_MAP_3_STAGE_RELATIONSHIPS_ZH,

    # NEW: Enhanced prompts (RECOMMENDED)
    "concept_map_enhanced_stage1_en": CONCEPT_MAP_ENHANCED_STAGE1_EN,
    "concept_map_enhanced_stage1_zh": CONCEPT_MAP_ENHANCED_STAGE1_ZH,
    "concept_map_enhanced_stage2_en": CONCEPT_MAP_ENHANCED_STAGE2_EN,
    "concept_map_enhanced_stage2_zh": CONCEPT_MAP_ENHANCED_STAGE2_ZH,

    # NEW: Template-based extraction
    "concept_map_template_extraction_en": CONCEPT_MAP_TEMPLATE_EXTRACTION_EN,
    "concept_map_template_extraction_zh": CONCEPT_MAP_TEMPLATE_EXTRACTION_ZH,

    # NEW: Quality-focused generation
    "concept_map_quality_focused_en": CONCEPT_MAP_QUALITY_FOCUSED_EN,
    "concept_map_quality_focused_zh": CONCEPT_MAP_QUALITY_FOCUSED_ZH,


    # NEW: Relationship quality enhancement
    "concept_map_relationship_quality_en": CONCEPT_MAP_RELATIONSHIP_QUALITY_EN,
    "concept_map_relationship_quality_zh": CONCEPT_MAP_RELATIONSHIP_QUALITY_ZH,

    # Simplified two-stage approach (kept for compatibility)
    "concept_map_stage1_concepts_en": CONCEPT_MAP_STAGE1_CONCEPTS_EN,
    "concept_map_stage1_concepts_zh": CONCEPT_MAP_STAGE1_CONCEPTS_ZH,
    "concept_map_stage2_relationships_en": CONCEPT_MAP_STAGE2_RELATIONSHIPS_EN,
    "concept_map_stage2_relationships_zh": CONCEPT_MAP_STAGE2_RELATIONSHIPS_ZH,

    # Hierarchical three-stage approach
    "concept_map_hierarchical_stage1_en": CONCEPT_MAP_HIERARCHICAL_STAGE1_EN,
    "concept_map_hierarchical_stage2_en": CONCEPT_MAP_HIERARCHICAL_STAGE2_EN,
    "concept_map_hierarchical_stage3_en": CONCEPT_MAP_HIERARCHICAL_STAGE3_EN,

    # Network-first approach
    "concept_map_network_stage1_en": CONCEPT_MAP_NETWORK_STAGE1_EN,
    "concept_map_network_stage2_en": CONCEPT_MAP_NETWORK_STAGE2_EN,
    "concept_map_network_stage1_zh": CONCEPT_MAP_NETWORK_STAGE1_ZH,
    "concept_map_network_stage2_zh": CONCEPT_MAP_NETWORK_STAGE2_ZH,

    # Template-based approach
    "concept_map_template_stage1_en": CONCEPT_MAP_TEMPLATE_STAGE1_EN,
    "concept_map_template_stage2_en": CONCEPT_MAP_TEMPLATE_STAGE2_EN,
}