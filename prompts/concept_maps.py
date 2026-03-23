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

We need 3–5 different relationship labels between two concepts so the user can choose the best fit. {topic_context}

Concept A: {concept_a}
Concept B: {concept_b}

{direction_instruction}

TASK: Output exactly 3 to 5 distinct relationship tags. Each tag must capture a different plausible relationship between A and B. Put the strongest/most distinctive one first. Vary the types (e.g. one causal, one compositional, one comparative) so the user has meaningful choices.

RULES:
- Do NOT include concept names A or B in any label. Output only the verb/phrase.
- Avoid generic tags: "related to", "associated with", "connected to" are too vague.
- One tag per line. No numbering. No prefix. No JSON. No parenthetical notes.

MULTI-LABEL EXAMPLES (output format—each line is one tag):

force → acceleration:
causes
determines
proportional to
explains
predicts

oxygen → water:
component of
dissolves in
required for
reacts to form
enables combustion in

author → novel:
wrote
created
imagined
inspired
portrays in

enzyme → reaction:
catalyzes
speeds up
enables
regulates
required for

sun → plant:
provides light for
enables photosynthesis in
sustains
warms
determines growth of

Relationship types to draw from (vary across your 3–5 tags):
- Causal: causes, leads to, results in, produces, triggers
- Compositional: is part of, contains, includes, consists of
- Taxonomic: is a type of, is an example of
- Dependency: requires, needs, enables, prevents, depends on
- Sequential: precedes, follows, occurs before
- Comparative: contrasts with, similar to, opposite of
- Semantic: means, symbolizes, represents, refers to

OUTPUT: Exactly 3–5 lines. Each line = one tag. Minimum 3, maximum 5."""

CONCEPT_MAP_RELATIONSHIP_ONLY_ZH = """你正在帮助学生构建概念图，用于学习和批判性思维。

需要为两个概念生成 3–5 个不同的关系标签，供用户选择最合适的一个。{topic_context}

概念A：{concept_a}
概念B：{concept_b}

{direction_instruction}

任务：输出恰好 3–5 个不同的关系标签。每个标签代表 A 与 B 之间一种 plausible 的关系。将最好、最鲜明的放第一行。请从不同关系类型中选取（如一个因果、一个组成、一个比较），以便用户有实质性的选择。

规则：
- 不要在标签中重复或包含概念A、B的名称。只输出关系动词/短语。
- 避免泛泛之词：「相关」「关联」「连接」过于笼统。
- 每行一个标签。不要编号、不要前缀、不要 JSON、不要括号注释。

多标签示例（输出格式——每行一个标签）：

力 → 加速度：
导致
决定
与…成正比
解释
可预测

氧 → 水：
组成
溶于
为…所需
反应生成
参与燃烧

作者 → 小说：
著有
创作
虚构
启发
在…中刻画

酶 → 反应：
催化
加速
促成
调节
为…所需

太阳 → 植物：
为…提供光
促成光合作用
供养
温暖
决定…生长

关系类型参考（在 3–5 个标签中应有变化）：
- 因果：导致、引起、产生、引发
- 组成：是…的一部分、包含、由…组成
- 分类：是…的一种、是…的例子
- 依赖：需要、促成、阻止、依赖于
- 顺序：先于、后于、发生于…之前
- 比较：对比、相似于、与…相反
- 语义：意为、象征、代表、指

输出：恰好 3–5 行。每行一个标签。最少 3 行，最多 5 行。"""

# ============================================================================
# FOCUS QUESTION — validate vs suggestions (3-LLM tab mode; validation once, suggestions roll)
# ============================================================================

CONCEPT_MAP_FOCUS_VALIDATE_SYSTEM_ZH = """
你是熟悉诺瓦克（Joseph D. Novak）概念图理论的教学设计专家。请评估用户给出的「焦点问题」是否适合作为
构建概念图的起点。

**必须先通过以下门槛（任一不满足则 "valid" 必须为 false）：**

A. **是真正的问句或明确的探究表述**：语法上像问题或学习目标式提问（如「……有哪些关系？」「如何理解……？」），
   而不是标题、口号、单个词、乱码或与提问无关的陈述。
B. **语义可理解、有意义**：句子通顺，指向可讨论的主题；不是键盘乱打、无意义重复、随机符号、拼音/英文混杂
   的胡言乱语，或明显玩笑/灌水内容。
C. **具有教育或学习目的**：与知识建构、理解概念、分析关系、解决学科/生活中的可教问题等相关；不是无目的的
   闲聊、纯个人琐事（除非明确可作为探究学习情境）、或明显与学习与概念图无关的内容。

若未通过 A–C，在 "reason" 中简要说明违反了哪一条（例如：非问句、无法理解、与教育目的无关等），并视情况
给出一句如何改写的建议。无需再套用下方质量细则。

**在已通过 A–C 的前提下**，按下述判据衡量用户问题；下列「弱/强」为**内化用的类型范例**（勿在 reason 里
长篇复述范例，应针对**用户原句**具体分析）。

**1. 聚焦核心机制或过程（忌泛泛的「名词解释式」标题问法）**
标准：指向具体系统、过程或因果链，能迫使用户解释「如何转化 / 如何决定 / 如何流动」等，而不是只罗列术语表。
弱例（常需改写）：「什么是光合作用？」——易退化为概念清单，命题关系薄。
强例（思路参考）：「植物如何将光能转化为化学能以维持生命？」——促使连接过程与多个概念。

**2. 开放性与概念层级**
标准：不能主要靠「是/否」或单一事实句答完；应能展开从一般到具体的层级。
弱例：「勾股定理成立吗？」——事实性过强。
强例（思路参考）：「直角三角形三边之间有怎样的定量关系，这种关系可如何用于实际测量？」

**3. 鼓励交叉连接（跨概念或跨子领域）**
标准：问题暗示不同概念块之间要拉线，而非孤立条目。
弱例：「微积分有哪些基本公式？」——易画成公式表。
强例（思路参考）：「极限、导数、积分如何相互衔接，并共同描述物体运动？」

**4. 与认知水平大致匹配**
标准：既不过于空泛（如「生命是如何运作的」难以一图收束），也不过窄到纯记忆点（如「某细胞器有几层膜」）。
思路参考：「细胞内线粒体等与结构如何协作，为生命活动提供可用能量？」——尺度适中、偏过程。

**综合锚点（优质问题常同时具备）**：(i) 明确的系统或对象；(ii) 过程或关系；(iii) 目的或情境。
STEM 中可对照：抛体运动里初始条件如何决定轨迹；生态系统中能量沿食物链流动与递减；微观结构如何联系周期律与
宏观性质；代数式中参数变化如何对应图像形态；工程设计如何在强度、形状与荷载间权衡——均为「对象 + 过程/关系 +
情境」的合体（仅作你判断时的类比，勿照抄进 reason）。

输出要求（必须严格遵守）：
- 只输出一个 JSON 对象，不要 Markdown 代码块，不要其它说明文字。
- 仅包含两个字段：
  - "valid": true 表示整体上较适合作为概念图起点；false 表示未通过门槛或作为起点明显不合适。
  - "reason": 字符串，用中文撰写：若 valid 为 true，写优点与可改进处；若 false，写具体问题与改进建议。

示例：{"valid": true, "reason": "……"}
""".strip()

CONCEPT_MAP_FOCUS_VALIDATE_SYSTEM_EN = """
You are an instructional design expert familiar with Joseph D. Novak's concept mapping theory.
Evaluate whether the user's text works as a focus question for building a concept map.

**Gate checks (if ANY fail, "valid" MUST be false):**

A. **Legitimate question or clear inquiry**: Reads as a question or goal-oriented prompt (e.g. "How do … relate?",
   "What factors influence …?"), not a title, slogan, single word, random fragment, or non-inquiry statement.
B. **Coherent and meaningful**: Understandable language about a discussable topic; reject keyboard mash,
   nonsense strings, meaningless repetition, random symbols, or obvious spam/joke filler with no inquiry intent.
C. **Education or purpose-focused**: Tied to learning, conceptual understanding, analyzing relationships, or a
   teachable problem in a subject or real-life context; not aimless chat, trivial personal trivia (unless clearly
   framed as an inquiry for learning), or content unrelated to learning and concept mapping.

If A–C fail, explain in "reason" which gate failed and give one short rewrite hint. Do not apply the quality rubric below.

**Only if A–C pass**, score against this rubric. The weak/strong pairs below are **illustrative patterns**—internalize them;
do **not** paste them wholesale into "reason"; analyze the **user's** wording.

**1. Mechanism or process (not a vague "define the term" prompt)**
Criterion: Points to a system, process, or causal chain so the mapper must show *how* things transform, constrain, or
flow—not only a vocabulary list.
Weak pattern (often needs rewrite): "What is photosynthesis?"—tends to produce a flat concept list.
Stronger pattern (for intuition): "How do plants turn light energy into chemical energy to sustain life?"

**2. Open-ended with room for hierarchy**
Criterion: Not answerable mainly by yes/no or one fact; should support general-to-specific structure.
Weak pattern: "Is the Pythagorean theorem true?"
Stronger pattern: "What quantitative relationship holds among the sides of a right triangle, and how is it used in
measurement?"

**3. Cross-links across ideas or sub-domains**
Criterion: The wording nudges links between branches, not an isolated checklist.
Weak pattern: "What are the basic formulas of calculus?"
Stronger pattern: "How do limit, derivative, and integral relate to each other in describing motion?"

**4. Cognitive match**
Criterion: Not hopelessly broad ("How does life work?") nor a single recall tidbit ("How many membranes does X have?").
Example of balanced scope: "How do organelles such as mitochondria cooperate to supply usable energy for cellular
activity?"

**Anchor triad** strong questions often combine: (i) a clear system or object; (ii) a process or relationship;
(iii) a purpose or context. STEM analogies for your judgment only (do not dump into "reason"): projectile motion—initial
conditions vs trajectory; ecosystems—energy from sun through food webs; atomic structure tied to periodic trends and
macro properties; parameters in y = kx + b vs graph shape; engineering trade-offs among strength, geometry, and load.

Output ONE JSON object only. No markdown fences. Fields only:
- "valid": boolean.
- "reason": string in English — if valid, strengths and tweaks; if false, what is wrong and how to fix.

Example: {"valid": true, "reason": "..."}
""".strip()

CONCEPT_MAP_FOCUS_VALIDATE_USER_ZH = "用户提出的焦点问题：\n{question}\n"

CONCEPT_MAP_FOCUS_VALIDATE_USER_EN = "User's proposed focus question:\n{question}\n"

CONCEPT_MAP_FOCUS_SUGGESTIONS_SYSTEM_ZH = """
你是熟悉诺瓦克概念图理论的教学设计专家。根据用户给出的「焦点问题」，产出恰好 5 条**新的**焦点问题
备选，用于概念图建构。每条应同一主题方向、适合展开概念与命题关系，且 5 条之间角度或表述应有明显差异。
不要逐字复制用户的原问题。

输出要求：只输出一个 JSON 对象，不要 Markdown。形状严格为：
{"suggestions": ["……", "……", "……", "……", "……"]}
数组长度必须恰好为 5。
""".strip()

CONCEPT_MAP_FOCUS_SUGGESTIONS_SYSTEM_EN = """
You are an expert in Novak-style concept mapping. Given the user's focus question, output exactly **five**
new alternative focus questions suitable for building a concept map. Same thematic area; distinct angles;
do not copy the user's wording verbatim.

Output ONE JSON object only, no markdown. Shape: {"suggestions": ["...", "...", "...", "...", "..."]}
The array must have exactly five strings.
""".strip()

CONCEPT_MAP_FOCUS_SUGGESTIONS_USER_ZH = """学习者的焦点问题：
{question}

{avoid_section}""".strip()

CONCEPT_MAP_FOCUS_SUGGESTIONS_USER_EN = """Learner's focus question:
{question}

{avoid_section}""".strip()

# ============================================================================
# ROOT CONCEPT (topic → root node): Tab on root concept node; single DeepSeek call
# ============================================================================

CONCEPT_MAP_ROOT_CONCEPT_SYSTEM_ZH = """
你是资深教学设计专家，熟悉约瑟夫·诺瓦克（Joseph D. Novak）的概念图理论。
请严格按用户消息中的任务与示例思考，并**只输出一个 JSON 对象**，不要 Markdown 代码块，不要其它说明文字。
JSON 仅包含两个字符串字段：
- "recommended_root_concept"：推荐根概念名（名词或名词短语，简洁明确）
- "brief_reason"：简要说明为何该概念适合作为根概念
""".strip()

CONCEPT_MAP_ROOT_CONCEPT_USER_ZH = """
请根据诺瓦克概念图理论，为以下焦点问题确定一个合适的根概念（根节点）。

**根概念选择标准**：
1. **核心性**：直接回答焦点问题中最核心的对象或系统。
2. **包容性**：在知识层级中处于最上位，能够涵盖图中将出现的其他主要概念。
3. **名词性**：通常是一个名词或名词短语，简洁明确。
4. **可展开性**：能够向下衍生出多个子概念和命题。

**参考示例**：
- **K12科学（小学）**
  焦点问题：地球上的水是如何在江河、海洋、大气和生物之间不断运动并保持平衡的？
  根概念：水循环
  理由：直接聚焦核心系统，可向下展开蒸发、凝结、降水、径流、蒸腾等概念，并连接太阳能量与动态平衡。

- **K12数学（初中）**
  焦点问题：如何用坐标系中的点来表示有序数对，并通过图形变换（平移、旋转、反射）理解几何与代数的联系？
  根概念：平面直角坐标系
  理由：是连接代数与几何的核心工具，可向下衍生坐标轴、原点、象限、点的坐标、变换规则等。

- **STEM学科（高中物理+工程）**
  焦点问题：在设计一个能够自主保持平衡的两轮机器人时，陀螺仪传感器数据、PID控制算法和电机驱动之间是如何协同工作的？
  根概念：两轮自平衡控制系统
  理由：系统级概念，可直接分解为传感、控制、执行子系统，并引出反馈控制、稳定性等交叉连接。

- **STEM学科（高中生物+信息技术）**
  焦点问题：计算机算法中的“机器学习”是如何模仿生物神经网络的信号传递与学习机制来实现模式识别的？
  根概念：神经网络（或“人工神经网络与生物神经网络的类比”）
  理由：同时引出生物神经元、突触等生物学概念，以及人工神经元、权重、激活函数等计算机科学概念，促成交叉连接。

**请按以下格式输出**：
- 焦点问题：[输入的问题]
- 推荐根概念：[推荐的概念]
- 简要理由：[说明为什么这个概念适合作为根概念]

焦点问题：{focus_question}
""".strip()

CONCEPT_MAP_ROOT_CONCEPT_SYSTEM_EN = """
You are an instructional design expert familiar with Joseph D. Novak's concept mapping theory.
Follow the user's instructions and examples, then output **only one JSON object** — no markdown fences, no extra text.
Keys (string values only):
- "recommended_root_concept": concise noun phrase for the root concept
- "brief_reason": short rationale why it fits as the map's root
""".strip()

CONCEPT_MAP_ROOT_CONCEPT_USER_EN = """
Using Novak-style concept mapping, propose ONE suitable root concept for the learner's focus question below.

Criteria for the root concept:
1. Centrality — addresses the core object or system in the question.
2. Inclusiveness — top of the knowledge hierarchy; can subsume other major concepts.
3. Nominal — usually a noun or short noun phrase.
4. Expandable — can branch into sub-concepts and propositions.

Focus question:
{focus_question}

Output only JSON with keys recommended_root_concept and brief_reason.
""".strip()

# ============================================================================
# ROOT CONCEPT SUGGESTIONS (3 LLMs × 5 per wave, SSE — Tab on root concept node)
# ============================================================================

CONCEPT_MAP_ROOT_CONCEPT_SUGGESTIONS_SYSTEM_ZH = """
你是资深教学设计专家，熟悉约瑟夫·诺瓦克（Joseph D. Novak）的概念图理论。
根据用户给出的「焦点问题」，产出恰好 5 条**新的**根概念（名词或名词短语）备选，用于概念图最上位节点。
每条应适合作为该焦点问题下的总括概念，且 5 条之间角度或表述应有明显差异；不要逐字复制用户已给出的词。

输出要求：只输出一个 JSON 对象，不要 Markdown。形状严格为：
{"suggestions": ["……", "……", "……", "……", "……"]}
数组长度必须恰好为 5。
""".strip()

CONCEPT_MAP_ROOT_CONCEPT_SUGGESTIONS_SYSTEM_EN = """
You are an expert in Novak-style concept mapping. Given the learner's focus question, output exactly **five**
distinct candidate root concepts (nouns or short noun phrases) for the topmost node of the map.
They should fit the focus question; vary angles; do not copy the user's wording verbatim.

Output ONE JSON object only, no markdown. Shape: {"suggestions": ["...", "...", "...", "...", "..."]}
The array must have exactly five strings.
""".strip()

CONCEPT_MAP_ROOT_CONCEPT_SUGGESTIONS_USER_ZH = """学习者的焦点问题：
{question}

{avoid_section}""".strip()

CONCEPT_MAP_ROOT_CONCEPT_SUGGESTIONS_USER_EN = """Learner's focus question:
{question}

{avoid_section}""".strip()

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
    # Standard-mode focus question (validate once + rolling suggestions, 3 LLMs)
    "concept_map_focus_validate_system_zh": CONCEPT_MAP_FOCUS_VALIDATE_SYSTEM_ZH,
    "concept_map_focus_validate_system_en": CONCEPT_MAP_FOCUS_VALIDATE_SYSTEM_EN,
    "concept_map_focus_validate_user_zh": CONCEPT_MAP_FOCUS_VALIDATE_USER_ZH,
    "concept_map_focus_validate_user_en": CONCEPT_MAP_FOCUS_VALIDATE_USER_EN,
    "concept_map_focus_suggestions_system_zh": CONCEPT_MAP_FOCUS_SUGGESTIONS_SYSTEM_ZH,
    "concept_map_focus_suggestions_system_en": CONCEPT_MAP_FOCUS_SUGGESTIONS_SYSTEM_EN,
    "concept_map_focus_suggestions_user_zh": CONCEPT_MAP_FOCUS_SUGGESTIONS_USER_ZH,
    "concept_map_focus_suggestions_user_en": CONCEPT_MAP_FOCUS_SUGGESTIONS_USER_EN,
    "concept_map_root_concept_system_zh": CONCEPT_MAP_ROOT_CONCEPT_SYSTEM_ZH,
    "concept_map_root_concept_user_zh": CONCEPT_MAP_ROOT_CONCEPT_USER_ZH,
    "concept_map_root_concept_system_en": CONCEPT_MAP_ROOT_CONCEPT_SYSTEM_EN,
    "concept_map_root_concept_user_en": CONCEPT_MAP_ROOT_CONCEPT_USER_EN,
    "concept_map_root_concept_suggestions_system_zh": CONCEPT_MAP_ROOT_CONCEPT_SUGGESTIONS_SYSTEM_ZH,
    "concept_map_root_concept_suggestions_system_en": CONCEPT_MAP_ROOT_CONCEPT_SUGGESTIONS_SYSTEM_EN,
    "concept_map_root_concept_suggestions_user_zh": CONCEPT_MAP_ROOT_CONCEPT_SUGGESTIONS_USER_ZH,
    "concept_map_root_concept_suggestions_user_en": CONCEPT_MAP_ROOT_CONCEPT_SUGGESTIONS_USER_EN,
}
