"""
Concept Maps Prompts

This module contains prompts for concept maps. Concept maps use real-time
relationship generation only (when user creates links between concepts).
Multi-stage full-diagram generation has been removed.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

# ============================================================================
# CONCEPT MAP SPEC (for diagram type detection / prompt_to_diagram_agent)
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
你要生成"概念图"。按两个内部步骤思考，但最终只输出 JSON 对象。

需求：{user_prompt}

步骤 1（扩展概念）：列出 14–24 个与中心主题强相关的概念，使用简短名词/名词短语（≤4 个词），避免重复与长句。

步骤 2（关系）：
  2a. 对步骤 1 的每个概念，生成且仅生成 1 条"主题 与 该概念"之间的有向关系，使用 1–3 个词的动词/动词短语作为标签；根据含义选择方向（概念 -> 主题 或 主题 -> 概念）。
  2b. 另外补充若干概念–概念关系（每个概念 0–2 条，总计约 6–18 条），每条为单一有向边并使用简短动词/动词短语标签。
  示例标签：导致、引起、属于、包含、需要、产生、调节、是…的一种、由…组成、连接到、位于。

唯一性约束（非常重要）：
- "主题 与 任一概念"之间必须且仅能有 1 条关系（方向任选，但不得重复）。
- "任意两个概念"之间至多 1 条关系（同一无序对不得出现重复或反向重复）。
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
# RELATIONSHIP ONLY - for real-time link creation (concept map auto-complete)
# ============================================================================

CONCEPT_MAP_RELATIONSHIP_ONLY_EN = """You are helping students build concept maps for learning and critical thinking.

We are generating a relationship between two concepts in this concept map. {topic_context}

Concept A: {concept_a}
Concept B: {concept_b}

{direction_instruction}

Output exactly ONE relationship tag—the most distinctive, specific relationship between A and B in the context of this topic. Avoid generic tags like "related to"; choose the tag that best captures this unique pair.

Do NOT repeat or include the concept names (A or B) in the label. Output only the relationship verb/phrase. Example: 养分–泥土 → 提供 (not 提供养分).

Examples of distinctive tags:
- dad–mom: husband and wife
- grandma–mom: mother and child
- oxygen–water: component of
- force–acceleration: causes
- author–novel: wrote
- sun–plant: provides
- reactant–product: yields

Most common relationship types (use or adapt as needed):
- Causal: causes, leads to, results in, produces, triggers
- Compositional: is part of, contains, includes, consists of
- Taxonomic: is a type of, is an example of
- Dependency: requires, needs, enables, prevents, depends on
- Sequential: precedes, follows, occurs before
- Comparative: contrasts with, similar to, opposite of
- Semantic: means, symbolizes, represents, refers to
- Association: influences, affects, related to, connected to

STEM examples: catalyzes, oxidizes, accelerates, regulates, equals, derives from
Literature examples: symbolizes, foreshadows, alludes to, parodies

CRITICAL: Output ONLY the single relationship tag. Nothing else. Never include concept A or B in the label.
- No prefix (e.g. "The relationship is:", "Answer:", "Tag:")
- No parenthetical notes or explanations (e.g. "Note: ...")
- No explanation, no JSON, no punctuation, no period at the end
- Literally just the tag—one word or short phrase"""

CONCEPT_MAP_RELATIONSHIP_ONLY_ZH = """你正在帮助学生构建概念图，用于学习和批判性思维。

我们正在生成此概念图中两个概念之间的关系。{topic_context}

概念A：{concept_a}
概念B：{concept_b}

{direction_instruction}

请输出恰好一个关系标签——在主题背景下最能体现 A 与 B 之间最鲜明、最具体关系的标签。避免"相关"等泛泛之词；选择最能概括这对概念独特关系的标签。

不要在标签中重复或包含概念A、B的名称。只输出关系动词/短语。例：养分–泥土 → 提供（不要 提供养分）。

鲜明标签示例：
- 爸爸–妈妈：夫妻
- 奶奶–妈妈：母子
- 氧–水：组成
- 力–加速度：导致
- 作者–小说：著有
- 太阳–植物：提供
- 反应物–产物：生成

最常见的关系类型（可选用或改编）：
- 因果：导致、引起、产生、引发
- 组成：是…的一部分、包含、由…组成
- 分类：是…的一种、是…的例子
- 依赖：需要、促成、阻止、依赖于
- 顺序：先于、后于、发生于…之前
- 比较：对比、相似于、与…相反
- 语义：意为、象征、代表、指
- 关联：影响、相关、连接

STEM示例：催化、氧化、加速、调节、等于、源于
文学示例：象征、预示、影射、戏仿

重要：只输出一个关系标签，不要输出任何其他内容。标签中不得包含概念A或B的名称。
- 不要前缀（如「关系是：」「答案是：」「标签：」）
- 不要括号内的解释或注释（如「注：...」）
- 不要解释、JSON、标点或句号
- 仅输出标签本身——一个词或短语"""

# ============================================================================
# PROMPT REGISTRY
# ============================================================================

CONCEPT_MAP_PROMPTS = {
    # For diagram type detection (prompt_to_diagram_agent)
    "concept_map_generation_en": CONCEPT_MAP_GENERATION_EN,
    "concept_map_generation_zh": CONCEPT_MAP_GENERATION_ZH,
    # Real-time relationship generation (link creation)
    "concept_map_relationship_only_en": CONCEPT_MAP_RELATIONSHIP_ONLY_EN,
    "concept_map_relationship_only_zh": CONCEPT_MAP_RELATIONSHIP_ONLY_ZH,
}
