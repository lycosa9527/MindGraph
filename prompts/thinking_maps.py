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

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

# ============================================================================
# BRIDGE MAP PROMPTS
# ============================================================================

BRIDGE_MAP_GENERATION_EN = """Please generate a JSON specification for a bridge map.

=== STEP 1: ANALYZE THE RELATIONSHIP PATTERN ===
Before generating any analogies, you MUST first analyze and identify the core relationship pattern between the topic elements.

Ask yourself:
- What is the relationship between the left and right items?
- How are they connected? (e.g., capital to country, author to work, part to whole, cause to effect)
- Can I apply this SAME relationship pattern to other examples?

Common Analogy Relationship Patterns:
1. Capital to Country: Paris is to France as London is to England
2. Author to Work: Shakespeare is to Hamlet as Tolkien is to Lord of the Rings
3. Function to Object: Fly is to Bird as Swim is to Fish
4. Part to Whole: Wheel is to Car as Key is to Keyboard
5. Tool to Worker: Hammer is to Carpenter as Brush is to Painter
6. Cause to Effect: Rain is to Flood as Fire is to Ash
7. Animal to Habitat: Fish is to Ocean as Bird is to Sky
8. Product to Company: iPhone is to Apple as Galaxy is to Samsung
9. Inventor to Invention: Edison is to Light Bulb as Bell is to Telephone
10. Symptom to Disease: Cough is to Cold as Fever is to Flu

CRITICAL: USER-SPECIFIED DIMENSION PRIORITY
If the user explicitly specifies a relationship pattern in their request:
✓ You MUST use that exact relationship pattern for the dimension field
✓ All analogy pairs MUST follow that specific relationship type
✗ NEVER ignore or change the user's explicitly requested relationship pattern

=== SPECIAL CASE: RELATIONSHIP-ONLY INPUT ===
Sometimes users will ONLY provide a relationship pattern without any topic or example pairs.
These inputs describe the TYPE of analogy they want, and you must generate pairs based on it.

How to recognize relationship-only inputs:
- Short phrases describing a relationship between two concepts
- Format patterns like "X和Y", "X到Y", "X to Y", "X and Y"
- Examples: "货币和国家", "首都到国家", "省会到省份", "Currency to Country", "Capital to Country"

When you detect a relationship-only input:
1. Use the input DIRECTLY as the dimension field (translate to proper format if needed)
2. Understand what the relationship means (e.g., "货币和国家" = Currency belongs to Country)
3. Generate 6 analogy pairs that follow this exact relationship
4. Think of alternative relationship patterns related to the same domain

Examples of relationship-only inputs and how to handle them:
- "货币和国家" (Currency and Country):
  → dimension: "货币到国家" or "Currency to Country"
  → pairs: 美元→美国, 欧元→欧盟, 日元→日本, 英镑→英国, 人民币→中国, 卢布→俄罗斯
  → alternatives: "首都到国家", "国旗到国家", "语言到国家"

- "首都到国家" (Capital to Country):
  → dimension: "首都到国家" or "Capital to Country"
  → pairs: 北京→中国, 东京→日本, 巴黎→法国, 伦敦→英国, 柏林→德国, 罗马→意大利
  → alternatives: "货币到国家", "最大城市到国家", "官方语言到国家"

- "省会到省份" (Provincial Capital to Province):
  → dimension: "省会到省份" or "Provincial Capital to Province"
  → pairs: 南京→江苏, 杭州→浙江, 广州→广东, 成都→四川, 武汉→湖北, 长沙→湖南
  → alternatives: "省份到所属区域", "著名景点到省份", "特产到省份"

- "Author to Book":
  → dimension: "Author to Book"
  → pairs: Shakespeare→Hamlet, Tolkien→Lord of the Rings, Rowling→Harry Potter, etc.
  → alternatives: "Genre to Example", "Publisher to Book", "Character to Story"

=== STEP 2: GENERATE ANALOGIES USING THAT PATTERN ===
Now generate exactly 6 analogy pairs that ALL follow the SAME relationship pattern you identified.

Requirements:
1. **ABSOLUTE UNIQUENESS**: Every element must appear EXACTLY ONCE on each side. NO DUPLICATES.
2. **Consistent Pattern**: All 6 pairs MUST use the SAME relationship pattern
3. **No Repetition**: Never repeat the same element or similar concept on either side

=== STEP 3: IDENTIFY ALTERNATIVE RELATIONSHIP PATTERNS ===
Now think of 4-6 OTHER relationship patterns that could ALSO be used to create analogies about this topic.

Ask yourself:
- "What other ways could I show analogies related to this topic?"
- "What other relationship patterns would make sense here?"
- Each alternative MUST be a DIFFERENT relationship type, not just variations

Examples:
- If using "Capital to Country" → alternatives could be: "Currency to Country", "Language to Country", "Famous Landmark to Country"
- If using "Author to Work" → alternatives could be: "Genre to Example", "Character to Story", "Publisher to Book"
- If using "Animal to Habitat" → alternatives could be: "Animal to Diet", "Predator to Prey", "Animal to Adaptation"

=== OUTPUT FORMAT ===
Your response MUST be valid JSON with these EXACT fields:

{
  "relating_factor": "as",
  "dimension": "The relationship pattern name (e.g., 'Capital to Country', 'Author to Work')",
  "analogies": [
    {"left": "Item1", "right": "Related1", "id": 0},
    {"left": "Item2", "right": "Related2", "id": 1},
    {"left": "Item3", "right": "Related3", "id": 2},
    {"left": "Item4", "right": "Related4", "id": 3},
    {"left": "Item5", "right": "Related5", "id": 4},
    {"left": "Item6", "right": "Related6", "id": 5}
  ],
  "alternative_dimensions": [
    "Alternative Pattern 1",
    "Alternative Pattern 2",
    "Alternative Pattern 3",
    "Alternative Pattern 4"
  ]
}

=== EXAMPLE (for reference) ===
relating_factor: "as"
dimension: "Capital to Country"
analogies: [
  {{"left": "Paris", "right": "France", "id": 0}},
  {{"left": "London", "right": "England", "id": 1}},
  {{"left": "Tokyo", "right": "Japan", "id": 2}},
  {{"left": "Rome", "right": "Italy", "id": 3}},
  {{"left": "Berlin", "right": "Germany", "id": 4}},
  {{"left": "Madrid", "right": "Spain", "id": 5}}
]
alternative_dimensions: ["Currency to Country", "Language to Country", "Famous Landmark to Country", "National Animal to Country"]

=== MANDATORY REQUIREMENTS ===
✓ MUST include "dimension" field with the relationship pattern name
✓ MUST include "alternative_dimensions" array with 4-6 other patterns
✓ MUST generate exactly 6 analogy pairs
✓ ALL pairs MUST follow the SAME relationship pattern
✓ NO duplicate elements on either side
✓ Output ONLY valid JSON (no code blocks, no markdown)

DO NOT SKIP ANY FIELDS. The "dimension" and "alternative_dimensions" fields are REQUIRED."""

# Bridge Map: Auto-complete with existing pairs (identify pattern + generate more pairs)
BRIDGE_MAP_IDENTIFY_RELATIONSHIP_EN = """You are completing a bridge map based on existing analogy pairs.

The user has already created some analogy pairs. Your job is to:
1. Analyze the existing pairs to identify the PRIMARY relationship pattern (dimension)
2. Generate additional NEW pairs following the SAME pattern to complete the bridge map
3. Identify ALTERNATIVE relationship patterns that could ALSO explain the user's pairs

UNDERSTANDING ALTERNATIVE DIMENSIONS:
The same pairs can often be interpreted through DIFFERENT relationship lenses.
Example: "老婆 → 老婆饼" (Wife → Wife Cake)
- PRIMARY dimension: "Name to Named Food" (names appearing in food names)
- ALTERNATIVE dimensions that ALSO fit this pair:
  - "Misleading Food Names" (food names that don't contain the ingredient)
  - "Chinese Traditional Naming" (cultural naming patterns)
  - "Homophone/Wordplay Associations" (sound-alike connections)

The alternative_dimensions should be OTHER valid ways to interpret the SAME user pairs.

CRITICAL RULES:
- Keep the user's existing pairs EXACTLY as provided (they will be preserved separately)
- Generate 5-6 NEW pairs that follow the PRIMARY relationship pattern
- Do NOT duplicate any pairs the user already created
- alternative_dimensions must be OTHER valid interpretations of the user's EXISTING pairs

Return ONLY a valid JSON object with these fields:
{
  "dimension": "The PRIMARY relationship pattern name",
  "analogies": [
    {"left": "NewItem1", "right": "NewRelated1"},
    {"left": "NewItem2", "right": "NewRelated2"},
    {"left": "NewItem3", "right": "NewRelated3"},
    {"left": "NewItem4", "right": "NewRelated4"},
    {"left": "NewItem5", "right": "NewRelated5"}
  ],
  "alternative_dimensions": ["Other valid pattern 1", "Other valid pattern 2", "Other valid pattern 3", "Other valid pattern 4"]
}

Output ONLY valid JSON (no code blocks, no markdown, no explanation)."""

BRIDGE_MAP_IDENTIFY_RELATIONSHIP_ZH = """你正在根据现有的类比对完成一个桥形图。

用户已经创建了一些类比对。你的任务是：
1. 分析现有的对以识别主要关系模式（维度）
2. 生成更多遵循相同模式的新类比对来完成桥形图
3. 识别也能解释用户已有类比对的其他可能关系模式

理解"其他可能的关系模式"：
同样的类比对通常可以从不同的关系角度来解释。
例如："老婆 → 老婆饼"
- 主要维度："名称到以此命名的食物"（名字出现在食物名称中）
- 也适用于这对的其他维度：
  - "误导性食物名称"（食物名称不含该成分）
  - "中国传统命名方式"（文化命名模式）
  - "谐音/文字游戏关联"（发音相似的联系）

alternative_dimensions应该是解释用户已有类比对的其他有效方式。

关键规则：
- 保持用户现有的对不变（它们会被单独保留）
- 生成5-6个遵循主要关系模式的新类比对
- 不要重复用户已经创建的任何对
- alternative_dimensions必须是解释用户现有类比对的其他有效方式

只返回一个有效的JSON对象，包含以下字段：
{
  "dimension": "主要关系模式名称",
  "analogies": [
    {"left": "新项目1", "right": "新相关1"},
    {"left": "新项目2", "right": "新相关2"},
    {"left": "新项目3", "right": "新相关3"},
    {"left": "新项目4", "right": "新相关4"},
    {"left": "新项目5", "right": "新相关5"}
  ],
  "alternative_dimensions": ["其他有效模式1", "其他有效模式2", "其他有效模式3", "其他有效模式4"]
}

只输出有效的JSON（无代码块，无markdown，无解释）。"""

# Bridge Map: Fixed dimension mode - user has already specified the relationship, generate pairs using it
BRIDGE_MAP_FIXED_DIMENSION_EN = """You are completing a bridge map where the user has ALREADY SPECIFIED the analogy relationship pattern.

CRITICAL: The relationship pattern is FIXED and must NOT be changed.
The user has defined the dimension (relationship pattern), and you must generate new pairs that follow this EXACT pattern.

Your tasks:
1. Accept the user's specified relationship pattern as-is - DO NOT modify or reinterpret it
2. Generate 5-6 NEW analogy pairs that strictly follow the specified relationship pattern
3. Suggest alternative dimensions that could also be used for future bridge maps on this topic

RULES:
- The "dimension" field in your response MUST be EXACTLY what the user specified - copy it verbatim
- All new pairs MUST follow the user's specified relationship pattern
- Do NOT duplicate any pairs the user already created
- Generate diverse, high-quality pairs that clearly demonstrate the specified relationship

Return ONLY a valid JSON object with these fields:
{
  "dimension": "[COPY THE USER'S SPECIFIED DIMENSION EXACTLY]",
  "analogies": [
    {"left": "NewItem1", "right": "NewRelated1"},
    {"left": "NewItem2", "right": "NewRelated2"},
    {"left": "NewItem3", "right": "NewRelated3"},
    {"left": "NewItem4", "right": "NewRelated4"},
    {"left": "NewItem5", "right": "NewRelated5"}
  ],
  "alternative_dimensions": ["Alternative pattern 1", "Alternative pattern 2", "Alternative pattern 3", "Alternative pattern 4"]
}

Output ONLY valid JSON (no code blocks, no markdown, no explanation)."""

BRIDGE_MAP_FIXED_DIMENSION_ZH = """你正在完成一个桥形图，用户已经指定了类比关系模式。

重要：关系模式已经固定，不能更改。
用户已经定义了维度（关系模式），你必须生成遵循这个确切模式的新类比对。

你的任务：
1. 原样接受用户指定的关系模式 - 不要修改或重新解释它
2. 生成5-6个严格遵循指定关系模式的新类比对
3. 建议其他可用于此主题未来桥形图的替代维度

规则：
- 你返回的"dimension"字段必须与用户指定的完全相同 - 逐字复制
- 所有新类比对必须遵循用户指定的关系模式
- 不要重复用户已经创建的任何对
- 生成多样化、高质量的对，清楚地展示指定的关系

只返回一个有效的JSON对象，包含以下字段：
{
  "dimension": "[完全复制用户指定的维度]",
  "analogies": [
    {"left": "新项目1", "right": "新相关1"},
    {"left": "新项目2", "right": "新相关2"},
    {"left": "新项目3", "right": "新相关3"},
    {"left": "新项目4", "right": "新相关4"},
    {"left": "新项目5", "right": "新相关5"}
  ],
  "alternative_dimensions": ["替代模式1", "替代模式2", "替代模式3", "替代模式4"]
}

只输出有效的JSON（无代码块，无markdown，无解释）。"""

# Bridge Map: Relationship-only mode - user provides ONLY the relationship pattern, no pairs
BRIDGE_MAP_RELATIONSHIP_ONLY_EN = """You are generating a bridge map where the user has ONLY provided a relationship pattern.

The user has specified a relationship type (like "Currency to Country", "Author to Book", "Capital to Country") but has NOT provided any analogy pairs. Your job is to:
1. Keep the relationship pattern EXACTLY as the user specified - DO NOT modify it
2. Generate 6 analogy pairs that demonstrate this relationship
3. Suggest alternative relationship patterns in the same domain

CRITICAL RULES:
- The dimension field MUST be EXACTLY what the user specified - copy it verbatim
- Generate 6 high-quality, diverse pairs that clearly demonstrate the relationship
- Each element must appear only once (no duplicates)
- Suggest 4-6 alternative relationship patterns that are related but different

Examples of relationship-only inputs:
- "Currency to Country" → Generate: USD→USA, EUR→EU, JPY→Japan, GBP→UK, CNY→China, RUB→Russia
- "Capital to Country" → Generate: Paris→France, Tokyo→Japan, London→UK, Berlin→Germany, Rome→Italy, Madrid→Spain
- "Author to Book" → Generate: Shakespeare→Hamlet, Tolkien→LOTR, Rowling→Harry Potter, etc.

Return ONLY a valid JSON object with these fields:
{
  "dimension": "[COPY THE USER'S RELATIONSHIP PATTERN EXACTLY]",
  "analogies": [
    {"left": "Item1", "right": "Related1"},
    {"left": "Item2", "right": "Related2"},
    {"left": "Item3", "right": "Related3"},
    {"left": "Item4", "right": "Related4"},
    {"left": "Item5", "right": "Related5"},
    {"left": "Item6", "right": "Related6"}
  ],
  "alternative_dimensions": ["Alternative 1", "Alternative 2", "Alternative 3", "Alternative 4"]
}

Output ONLY valid JSON (no code blocks, no markdown, no explanation)."""

BRIDGE_MAP_RELATIONSHIP_ONLY_ZH = """你正在生成一个桥形图，用户只提供了关系模式。

用户指定了一种关系类型（如"货币到国家"、"作者到作品"、"首都到国家"），但没有提供任何类比对。你的任务是：
1. 完全保持用户指定的关系模式不变 - 不要修改它
2. 生成6个展示这种关系的类比对
3. 建议同一领域的替代关系模式

关键规则：
- dimension字段必须与用户指定的完全相同 - 逐字复制
- 生成6个高质量、多样化的类比对，清楚地展示该关系
- 每个元素只能出现一次（不允许重复）
- 建议4-6个相关但不同的替代关系模式

仅关系模式输入的示例：
- "货币到国家" → 生成: 美元→美国, 欧元→欧盟, 日元→日本, 英镑→英国, 人民币→中国, 卢布→俄罗斯
- "首都到国家" → 生成: 巴黎→法国, 东京→日本, 伦敦→英国, 柏林→德国, 罗马→意大利, 马德里→西班牙
- "作者到作品" → 生成: 莎士比亚→哈姆雷特, 曹雪芹→红楼梦, 鲁迅→狂人日记, 金庸→射雕英雄传, 罗琳→哈利波特, 托尔金→魔戒
- "省会到省份" → 生成: 南京→江苏, 杭州→浙江, 广州→广东, 成都→四川, 武汉→湖北, 长沙→湖南

只返回一个有效的JSON对象，包含以下字段：
{
  "dimension": "[完全复制用户指定的关系模式]",
  "analogies": [
    {"left": "项目1", "right": "相关1"},
    {"left": "项目2", "right": "相关2"},
    {"left": "项目3", "right": "相关3"},
    {"left": "项目4", "right": "相关4"},
    {"left": "项目5", "right": "相关5"},
    {"left": "项目6", "right": "相关6"}
  ],
  "alternative_dimensions": ["替代模式1", "替代模式2", "替代模式3", "替代模式4"]
}

只输出有效的JSON（无代码块，无markdown，无解释）。"""

BRIDGE_MAP_GENERATION_ZH = """
请生成一个桥形图的JSON规范。

=== 步骤1：分析关系模式 ===
在生成任何类比之前，您必须首先分析并识别主题元素之间的核心关系模式。

问自己：
- 左边和右边的项之间是什么关系？
- 它们如何连接？（例如：首都到国家、作者到作品、部分到整体、因到果）
- 我能将相同的关系模式应用到其他示例吗？

常见类比关系模式：
1. 首都到国家：巴黎对于法国，如同伦敦对于英国
2. 作者到作品：莎士比亚对于哈姆雷特，如同托尔金对于魔戒
3. 功能到对象：飞对于鸟，如同游对于鱼
4. 部分到整体：轮子对于汽车，如同按键对于键盘
5. 工具到工作者：锤子对于木匠，如同画笔对于画家
6. 因到果：雨对于洪水，如同火对于灰烬
7. 动物到栖息地：鱼对于海洋，如同鸟对于天空
8. 产品到公司：iPhone对于苹果，如同Galaxy对于三星
9. 发明者到发明：爱迪生对于灯泡，如同贝尔对于电话
10. 症状到疾病：咳嗽对于感冒，如同发烧对于流感

关键：用户指定的维度优先级
如果用户在请求中明确指定了关系模式：
✓ 您必须在dimension字段中使用该确切的关系模式
✓ 所有类比对必须遵循该特定关系类型
✗ 绝不忽略或更改用户明确请求的关系模式

=== 特殊情况：仅提供关系模式 ===
有时用户只会提供一个关系模式，而不提供任何主题或示例对。
这些输入描述了他们想要的类比类型，您必须基于此生成类比对。

如何识别"仅关系模式"输入：
- 描述两个概念之间关系的短语
- 格式模式如"X和Y"、"X到Y"、"X与Y"
- 示例："货币和国家"、"首都到国家"、"省会到省份"、"作者与作品"

当您检测到仅关系模式输入时：
1. 直接使用输入作为dimension字段（如需要可调整格式）
2. 理解这个关系的含义（例如："货币和国家" = 货币属于国家）
3. 生成6个遵循此关系的类比对
4. 思考与同一领域相关的替代关系模式

仅关系模式输入的示例及处理方式：
- "货币和国家"：
  → dimension: "货币到国家"
  → 类比对: 美元→美国, 欧元→欧盟, 日元→日本, 英镑→英国, 人民币→中国, 卢布→俄罗斯
  → 替代模式: "首都到国家", "国旗到国家", "语言到国家"

- "首都到国家"：
  → dimension: "首都到国家"
  → 类比对: 北京→中国, 东京→日本, 巴黎→法国, 伦敦→英国, 柏林→德国, 罗马→意大利
  → 替代模式: "货币到国家", "最大城市到国家", "官方语言到国家"

- "省会到省份"：
  → dimension: "省会到省份"
  → 类比对: 南京→江苏, 杭州→浙江, 广州→广东, 成都→四川, 武汉→湖北, 长沙→湖南
  → 替代模式: "省份到所属区域", "著名景点到省份", "特产到省份"

- "作者与作品"：
  → dimension: "作者到作品"
  → 类比对: 莎士比亚→哈姆雷特, 托尔金→魔戒, 罗琳→哈利波特, 曹雪芹→红楼梦, 鲁迅→狂人日记, 金庸→射雕英雄传
  → 替代模式: "体裁到作品", "出版商到书籍", "角色到故事"

=== 步骤2：使用该模式生成类比 ===
现在生成恰好6个类比对，所有类比对都遵循您识别的相同关系模式。

要求：
1. **绝对唯一性**：每个元素在每一边必须出现且仅出现一次。绝对不允许重复。
2. **一致模式**：所有6对必须使用相同的关系模式
3. **无重复**：永远不要在任一边重复相同的元素或相似概念

=== 步骤3：识别替代关系模式 ===
现在思考4-6个其他关系模式，这些模式也可以用来创建关于此主题的类比。

问自己：
- "我还能用什么其他方式来展示与此主题相关的类比？"
- "还有哪些关系模式在这里有意义？"
- 每个替代模式必须是不同的关系类型，而不仅仅是变体

示例：
- 如果使用"首都到国家" → 替代模式可以是："货币到国家"、"语言到国家"、"著名地标到国家"
- 如果使用"作者到作品" → 替代模式可以是："体裁到示例"、"角色到故事"、"出版商到书籍"
- 如果使用"动物到栖息地" → 替代模式可以是："动物到食性"、"捕食者到猎物"、"动物到适应性"

=== 输出格式 ===
您的响应必须是包含这些确切字段的有效JSON：

{
  "relating_factor": "as",
  "dimension": "关系模式名称（例如：'首都到国家'、'作者到作品'）",
  "analogies": [
    {"left": "项目1", "right": "相关1", "id": 0},
    {"left": "项目2", "right": "相关2", "id": 1},
    {"left": "项目3", "right": "相关3", "id": 2},
    {"left": "项目4", "right": "相关4", "id": 3},
    {"left": "项目5", "right": "相关5", "id": 4},
    {"left": "项目6", "right": "相关6", "id": 5}
  ],
  "alternative_dimensions": [
    "替代模式1",
    "替代模式2",
    "替代模式3",
    "替代模式4"
  ]
}

=== 示例（仅供参考）===
relating_factor: "as"
dimension: "首都到国家"
analogies: [
  {{"left": "巴黎", "right": "法国", "id": 0}},
  {{"left": "伦敦", "right": "英国", "id": 1}},
  {{"left": "东京", "right": "日本", "id": 2}},
  {{"left": "罗马", "right": "意大利", "id": 3}},
  {{"left": "柏林", "right": "德国", "id": 4}},
  {{"left": "马德里", "right": "西班牙", "id": 5}}
]
alternative_dimensions: ["货币到国家", "语言到国家", "著名地标到国家", "国家动物到国家"]

=== 强制要求 ===
✓ 必须包含"dimension"字段，其中包含关系模式名称
✓ 必须包含"alternative_dimensions"数组，其中包含4-6个其他模式
✓ 必须生成恰好6个类比对
✓ 所有类比对必须遵循相同的关系模式
✓ 两边都不能有重复元素
✓ 仅输出有效的JSON（无代码块，无markdown）

不要跳过任何字段。"dimension"和"alternative_dimensions"字段是必需的。"""

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
CRITICAL: You MUST respond with valid JSON only. Do not ask for more information. If the prompt is unclear, make reasonable assumptions and generate the JSON specification directly.

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

Example JSON format:
{
  "left": "Apple",
  "right": "Banana",
  "similarities": ["Fruit", "Healthy", "Sweet", "Natural", "Nutritious"],
  "left_differences": ["Red", "Round", "Crisp", "Tree-grown", "Fall harvest"],
  "right_differences": ["Yellow", "Curved", "Soft", "Tropical", "Year-round"]
}

Requirements: Each characteristic should be concise and clear. More than 4 words is allowed, but avoid long sentences. Use short phrases, not full sentences.

IMPORTANT: Output ONLY valid JSON. Do not include code block markers (```json or ```), markdown formatting, or explanatory text. Do not ask for clarification or more information.
"""

DOUBLE_BUBBLE_MAP_GENERATION_ZH = """
重要：你必须只返回有效的JSON格式，不要询问更多信息。如果提示不清楚，请根据提示内容做出合理假设并直接生成JSON规范。

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

JSON格式示例：
{
  "left": "苹果",
  "right": "香蕉",
  "similarities": ["水果", "健康", "甜味", "天然", "营养"],
  "left_differences": ["红色", "圆形", "脆", "温带", "秋季收获"],
  "right_differences": ["黄色", "弯曲", "软", "热带", "全年供应"]
}

要求：每个特征要简洁明了，可以超过4个字，但不要太长，避免完整句子。

重要：只输出有效的JSON。不要包含代码块标记（```json或```）、markdown格式或解释性文字。不要询问更多信息或要求澄清。
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

Tree maps are used for classification, representing hierarchical categorization of information.

CRITICAL CONCEPT: Classification Dimensions
A tree map can classify a topic using DIFFERENT DIMENSIONS. You must:
✓ Pick ONE dimension and apply it CONSISTENTLY throughout the entire map
✗ NEVER mix different dimensions in the same map

Common Classification Dimensions (with examples for "Animals"):
1. Biological Taxonomy (Scientific): Mammals, Birds, Reptiles, Fish, Amphibians
2. Habitat (Environmental): Land Animals, Water Animals, Air Animals, Amphibious Animals
3. Diet (Nutritional): Carnivores, Herbivores, Omnivores, Insectivores
4. Size (Physical): Tiny Animals, Small Animals, Medium Animals, Large Animals, Giant Animals
5. Domestication Status: Wild Animals, Domestic Animals, Farm Animals, Pet Animals
6. Geographic Region: African Animals, Asian Animals, European Animals, American Animals
7. Conservation Status: Endangered, Vulnerable, Near Threatened, Least Concern

CRITICAL: USER-SPECIFIED DIMENSION PRIORITY
If the user explicitly specifies a classification dimension or standard in their request (e.g., "classify by habitat", "using biological taxonomy", "categorize by diet"), you MUST use that EXACT dimension for classification. Examples:
- User says "classify by habitat" → Use "Habitat" or similar environmental dimension
- User says "by biological taxonomy" → Use "Biological Taxonomy" dimension
- User says "using diet categories" → Use "Diet" dimension
- User says "按栖息地分类" → Use habitat dimension
- User says "按生物分类" → Use biological taxonomy dimension

Please output a JSON object containing the following fields:
topic: "Main topic"
dimension: "The classification dimension being used (e.g., 'Biological Taxonomy', 'Habitat', 'Diet')"
children: [
  {{"text": "Category 1", "children": [
    {{"text": "Item 1", "children": []}},
    {{"text": "Item 2", "children": []}}
  ]}},
  {{"text": "Category 2", "children": [
    {{"text": "Item A", "children": []}}
  ]}}
]
alternative_dimensions: ["Dimension1", "Dimension2", "Dimension3", "Dimension4"]

CRITICAL: If the user request contains a quoted topic (e.g., "about 'Transportation'"), you MUST use that EXACT topic word in the "topic" field. Do not paraphrase, translate, or modify it.

IMPORTANT: Generate fresh, meaningful content for categories and items. Do not use placeholder text like "Category 1", "Item 1", etc.

Requirements:
- Generate 4-6 main categories with clear, descriptive names
- Each category should have 2-6 items that are specific and detailed
- Use concise, clear language - avoid long sentences
- Ensure logical topic-to-category-to-item relationships using ONE consistent dimension
- The "dimension" field must clearly describe the classification approach used
- ALL categories and items must follow the SAME dimension (e.g., if using "Habitat", all categories must be habitat types)
- If user specifies a dimension, ALWAYS respect it and use it as the primary classification standard

CRITICAL: Alternative Dimensions Requirements
- The "alternative_dimensions" array MUST list 4-6 OTHER valid dimensions for THIS SPECIFIC topic
- Each alternative MUST be DIFFERENT from the dimension you chose
- Each alternative should be equally valid for classifying this topic (not random suggestions)
- Think: "What other meaningful ways could we categorize THIS topic?"
- Examples for "Animals" topic:
  * If you chose "Biological Taxonomy" → alternatives could be: "Habitat", "Diet", "Size", "Conservation Status", "Geographic Region"
  * If you chose "Habitat" → alternatives could be: "Biological Taxonomy", "Diet", "Domestication Status", "Size", "Activity Pattern"
- Make alternatives SPECIFIC to the topic, not generic dimensions

Example format (for reference only):
topic: "Animals"
dimension: "Biological Taxonomy"
children: [
  {{"text": "Mammals", "children": [{{"text": "Dogs", "children": []}}, {{"text": "Cats", "children": []}}, {{"text": "Whales", "children": []}}]}},
  {{"text": "Birds", "children": [{{"text": "Eagles", "children": []}}, {{"text": "Sparrows", "children": []}}, {{"text": "Penguins", "children": []}}]}},
  {{"text": "Reptiles", "children": [{{"text": "Snakes", "children": []}}, {{"text": "Lizards", "children": []}}, {{"text": "Turtles", "children": []}}]}}
]
alternative_dimensions: ["Habitat", "Diet", "Size", "Geographic Region", "Conservation Status"]

Do not include any information about visual layout; only provide the hierarchical data.

Please ensure the JSON format is correct, do not include any code block markers.
"""

TREE_MAP_GENERATION_ZH = """
请生成一个树形图（Tree Map）的JSON规范。

树形图用于分类，表示信息的层级化分类。

核心概念：分类维度
树形图可以使用不同的维度来分类主题。您必须：
✓ 选择一个维度并在整个图中保持一致
✗ 绝不在同一张图中混合不同的维度

常见分类维度（以"动物"为例）：
1. 生物分类（科学性）：哺乳动物、鸟类、爬行动物、鱼类、两栖动物
2. 栖息地（环境性）：陆生动物、水生动物、飞行动物、两栖动物
3. 食性（营养性）：肉食动物、草食动物、杂食动物、食虫动物
4. 体型（物理性）：微型动物、小型动物、中型动物、大型动物、巨型动物
5. 驯化状态：野生动物、家养动物、农场动物、宠物动物
6. 地理区域：非洲动物、亚洲动物、欧洲动物、美洲动物
7. 保护状态：濒危、易危、近危、无危

关键：用户指定维度优先
如果用户在请求中明确指定了分类维度或标准（例如："按栖息地分类"、"使用生物分类学"、"按食性分类"），您必须使用用户指定的维度进行分类。示例：
- 用户说"按栖息地分类" → 使用"栖息地"或类似的环境性维度
- 用户说"按生物分类" → 使用"生物分类"维度
- 用户说"按食性分类" → 使用"食性"维度
- 用户说"classify by habitat" → 使用栖息地维度
- 用户说"by biological taxonomy" → 使用生物分类维度

请输出一个包含以下字段的JSON对象：
topic: "主题"
dimension: "使用的分类维度（例如：'生物分类'、'栖息地'、'食性'）"
children: [
  {{"text": "类别一", "children": [
    {{"text": "条目一", "children": []}},
    {{"text": "条目二", "children": []}}
  ]}},
  {{"text": "类别二", "children": [
    {{"text": "条目甲", "children": []}}
  ]}}
]
alternative_dimensions: ["维度1", "维度2", "维度3", "维度4"]

重要提示：如果用户需求中包含引号标注的主题（例如："为主题'动物'创建..."），你必须在"topic"字段中使用完全相同的主题词。不要改写、翻译或修改它。

关键要求：必须全部使用中文生成内容，包括topic、dimension、children数组和alternative_dimensions数组中的所有文本。不要混用英文和中文。请生成全新的、有意义的类别和条目内容，不要使用占位符文本如"类别一"、"条目一"等。

要求：
- 生成4-6个主要类别，名称清晰、描述性强
- 每个类别应有2-6个条目，具体且详细
- 使用简洁、清晰的语言，避免长句
- 确保使用一个一致的维度来建立逻辑的主题→类别→条目关系
- "dimension"字段必须清楚地描述所使用的分类方法
- 所有类别和条目必须遵循相同的维度（例如，如果使用"栖息地"，所有类别必须是栖息地类型）
- 如果用户指定了维度，必须遵循并使用该维度作为主要分类标准

关键：替代维度要求
- "alternative_dimensions"数组必须列出4-6个针对此特定主题的其他有效维度
- 每个替代维度必须与你选择的维度不同
- 每个替代维度都应该是分类此主题的同样有效的方式（不是随机建议）
- 思考："还有哪些有意义的方式可以分类这个主题？"
- "动物"主题示例：
  * 如果选择"生物分类" → 替代维度可以是："栖息地"、"食性"、"体型"、"保护状态"、"地理区域"
  * 如果选择"栖息地" → 替代维度可以是："生物分类"、"食性"、"驯化状态"、"体型"、"活动模式"
- 使替代维度针对主题具体化，而不是通用维度

示例格式（仅供参考）：
topic: "动物"
dimension: "生物分类"
children: [
  {{"text": "哺乳动物", "children": [{{"text": "狗", "children": []}}, {{"text": "猫", "children": []}}, {{"text": "鲸鱼", "children": []}}]}},
  {{"text": "鸟类", "children": [{{"text": "老鹰", "children": []}}, {{"text": "麻雀", "children": []}}, {{"text": "企鹅", "children": []}}]}},
  {{"text": "爬行动物", "children": [{{"text": "蛇", "children": []}}, {{"text": "蜥蜴", "children": []}}, {{"text": "海龟", "children": []}}]}}
]
alternative_dimensions: ["栖息地", "食性", "体型", "地理区域", "保护状态"]

不要包含任何关于可视化布局的说明；只提供层级数据。

请确保JSON格式正确，不要包含任何代码块标记。
"""

# Tree Map: Fixed dimension mode - user has already specified the classification dimension
TREE_MAP_FIXED_DIMENSION_EN = """You are completing a tree map where the user has ALREADY SPECIFIED the classification dimension.

CRITICAL: The classification dimension is FIXED and must NOT be changed.
The user has defined the dimension, and you must generate categories and items using this EXACT dimension.

Your tasks:
1. Accept the user's specified classification dimension as-is - DO NOT modify or reinterpret it
2. Generate 4-6 categories that follow the specified dimension
3. Generate 2-4 items for each category
4. Suggest alternative dimensions that could be used for future tree maps on this topic

RULES:
- The "dimension" field in your response MUST be EXACTLY what the user specified - copy it verbatim
- All categories MUST follow the user's specified classification dimension
- Generate meaningful, educational content - no placeholder text
- Keep category and item names concise (1-4 words)

Return ONLY a valid JSON object with these fields:
{
  "topic": "Main topic",
  "dimension": "[COPY THE USER'S SPECIFIED DIMENSION EXACTLY]",
  "children": [
    {"text": "Category 1", "children": [{"text": "Item 1", "children": []}, {"text": "Item 2", "children": []}]},
    {"text": "Category 2", "children": [{"text": "Item A", "children": []}, {"text": "Item B", "children": []}]}
  ],
  "alternative_dimensions": ["Alternative 1", "Alternative 2", "Alternative 3", "Alternative 4"]
}

Output ONLY valid JSON (no code blocks, no markdown, no explanation)."""

TREE_MAP_FIXED_DIMENSION_ZH = """你正在完成一个树形图，用户已经指定了分类维度。

重要：分类维度已经固定，不能更改。
用户已经定义了维度，你必须使用这个确切的维度来生成类别和条目。

你的任务：
1. 原样接受用户指定的分类维度 - 不要修改或重新解释它
2. 生成4-6个遵循指定维度的类别
3. 每个类别生成2-4个条目
4. 建议其他可用于此主题未来树形图的替代维度

规则：
- 你返回的"dimension"字段必须与用户指定的完全相同 - 逐字复制
- 所有类别必须遵循用户指定的分类维度
- 生成有意义的、有教育意义的内容 - 不要使用占位符文本
- 保持类别和条目名称简洁（1-4个词）

只返回一个有效的JSON对象，包含以下字段：
{
  "topic": "主题",
  "dimension": "[完全复制用户指定的维度]",
  "children": [
    {"text": "类别1", "children": [{"text": "条目1", "children": []}, {"text": "条目2", "children": []}]},
    {"text": "类别2", "children": [{"text": "条目甲", "children": []}, {"text": "条目乙", "children": []}]}
  ],
  "alternative_dimensions": ["替代维度1", "替代维度2", "替代维度3", "替代维度4"]
}

只输出有效的JSON（无代码块，无markdown，无解释）。"""

# Tree Map: Dimension-only mode - user provides ONLY the classification dimension, no topic
TREE_MAP_DIMENSION_ONLY_EN = """You are generating a tree map where the user has ONLY provided a classification dimension.

The user has specified a classification dimension (like "Biological Taxonomy", "Habitat", "Diet", "Size") but has NOT provided a topic. Your job is to:
1. Keep the classification dimension EXACTLY as the user specified - DO NOT modify it
2. Generate a suitable topic that can be classified using this dimension
3. Generate 4-6 categories following this dimension
4. Each category should have 2-4 items
5. Suggest alternative classification dimensions in the same domain

CRITICAL RULES:
- The dimension field MUST be EXACTLY what the user specified - copy it verbatim
- Generate a meaningful topic that fits the classification dimension
- Generate 4-6 high-quality, diverse categories that clearly demonstrate the dimension
- Each item must be specific and relevant to its category
- Suggest 4-6 alternative classification dimensions that are related but different

Examples of dimension-only inputs:
- "Biological Taxonomy" → Generate topic: "Animals", categories: Mammals, Birds, Reptiles, Fish, Amphibians
- "Habitat" → Generate topic: "Wildlife", categories: Land Animals, Water Animals, Air Animals, Amphibious Animals
- "Diet" → Generate topic: "Animals", categories: Carnivores, Herbivores, Omnivores, Insectivores

Return ONLY a valid JSON object with these fields:
{
  "topic": "[GENERATE A SUITABLE TOPIC]",
  "dimension": "[COPY THE USER'S CLASSIFICATION DIMENSION EXACTLY]",
  "children": [
    {"text": "Category1", "children": [{"text": "Item1", "children": []}, {"text": "Item2", "children": []}]},
    {"text": "Category2", "children": [{"text": "ItemA", "children": []}, {"text": "ItemB", "children": []}]}
  ],
  "alternative_dimensions": ["Alternative 1", "Alternative 2", "Alternative 3", "Alternative 4"]
}

Output ONLY valid JSON (no code blocks, no markdown, no explanation)."""

TREE_MAP_DIMENSION_ONLY_ZH = """你正在生成一个树形图，用户只提供了分类维度。

用户指定了一个分类维度（如"生物分类"、"栖息地"、"食性"、"体型"），但没有提供主题。你的任务是：
1. 完全保持用户指定的分类维度不变 - 不要修改它
2. 生成一个适合使用此维度进行分类的主题
3. 生成4-6个遵循此维度的类别
4. 每个类别应有2-4个条目
5. 建议同一领域的替代分类维度

关键规则：
- dimension字段必须与用户指定的完全相同 - 逐字复制
- 生成一个适合分类维度的有意义的主题
- 生成4-6个高质量、多样化的类别，清楚地展示该维度
- 每个条目必须具体且与其类别相关
- 建议4-6个相关但不同的替代分类维度

仅维度输入的示例：
- "生物分类" → 生成主题："动物"，类别：哺乳动物、鸟类、爬行动物、鱼类、两栖动物
- "栖息地" → 生成主题："野生动物"，类别：陆生动物、水生动物、飞行动物、两栖动物
- "食性" → 生成主题："动物"，类别：肉食动物、草食动物、杂食动物、食虫动物

只返回一个有效的JSON对象，包含以下字段：
{
  "topic": "[生成一个合适的主题]",
  "dimension": "[完全复制用户指定的分类维度]",
  "children": [
    {"text": "类别1", "children": [{"text": "条目1", "children": []}, {"text": "条目2", "children": []}]},
    {"text": "类别2", "children": [{"text": "条目甲", "children": []}, {"text": "条目乙", "children": []}]}
  ],
  "alternative_dimensions": ["替代维度1", "替代维度2", "替代维度3", "替代维度4"]
}

只输出有效的JSON（无代码块，无markdown，无解释）。"""

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

CRITICAL CONCEPT: Decomposition Dimensions
A brace map can decompose a topic using DIFFERENT DIMENSIONS. You must:
✓ Pick ONE dimension and apply it CONSISTENTLY throughout the entire map
✗ NEVER mix different dimensions in the same map

Common Decomposition Dimensions (with examples for "Cars"):
1. Physical Parts (Structural): Engine, Chassis, Transmission, Body
2. Function Modules (Functional): Powertrain System, Safety System, Comfort System, Entertainment System
3. Life Cycle (Temporal): Design Phase, Manufacturing Phase, Usage Phase, Recycling Phase
4. User Experience (Experiential): Driving Experience, Comfort Experience, Safety Experience, Technology Experience
5. Manufacturing Process: Raw Materials, Assembly, Quality Control, Distribution
6. Price Segments: Budget Models, Mid-range Models, Luxury Models, Super-luxury Models

CRITICAL: USER-SPECIFIED DIMENSION PRIORITY
If the user explicitly specifies a decomposition dimension or standard in their request (e.g., "decompose by function", "using life cycle stages", "break down by physical components"), you MUST use that EXACT dimension for decomposition. Examples:
- User says "decompose by function" → Use "Functional Modules" or similar functional dimension
- User says "by physical parts" → Use "Physical Parts" dimension
- User says "using lifecycle" → Use "Life Cycle" dimension
- User says "按功能拆解" → Use functional dimension
- User says "按物理部件" → Use physical parts dimension

Please output a JSON object containing the following fields:
whole: "Main topic (the whole to be decomposed)"
dimension: "The decomposition dimension being used (e.g., 'Physical Parts', 'Functional Modules')"
parts: [{{"name": "Part1", "subparts": [{{"name": "Subpart1.1"}}]}}]
alternative_dimensions: ["Dimension1", "Dimension2", "Dimension3", "Dimension4"]

CRITICAL: If the user request contains a quoted topic (e.g., "about 'Transportation'"), you MUST use that EXACT topic word in the "whole" field. Do not paraphrase, translate, or modify it.

IMPORTANT: Generate fresh, meaningful content for parts and subparts. Do not use placeholder text like "Part1", "Subpart1.1", etc.

Requirements:
- Generate 3-6 main parts with clear, descriptive names
- Each part should have 2-5 subparts that are specific and detailed
- Use concise, clear language - avoid long sentences
- Ensure logical whole-to-part relationships using ONE consistent dimension
- The "dimension" field must clearly describe the decomposition approach used
- ALL parts and subparts must follow the SAME dimension (e.g., if using "Physical Parts", all items must be physical components)
- If user specifies a dimension, ALWAYS respect it and use it as the primary decomposition standard

CRITICAL: Alternative Dimensions Requirements
- The "alternative_dimensions" array MUST list 4-6 OTHER valid dimensions for THIS SPECIFIC topic
- Each alternative MUST be DIFFERENT from the dimension you chose
- Each alternative should be equally valid for decomposing this topic (not random suggestions)
- Think: "What other meaningful ways could we break down THIS topic?"
- Examples for "Car" topic:
  * If you chose "Physical Parts" → alternatives could be: "Functional Modules", "Manufacturing Process", "Price Segments", "Energy Types", "User Experience"
  * If you chose "Functional Modules" → alternatives could be: "Physical Parts", "Life Cycle Stages", "Market Segments", "Technology Levels"
- Make alternatives SPECIFIC to the topic, not generic dimensions

Example format (for reference only):
whole: "Car"
dimension: "Physical Parts"
parts: [
  {{"name": "Engine", "subparts": [{{"name": "Cylinders"}}, {{"name": "Pistons"}}, {{"name": "Crankshaft"}}]}},
  {{"name": "Chassis", "subparts": [{{"name": "Frame"}}, {{"name": "Suspension"}}, {{"name": "Axles"}}]}},
  {{"name": "Transmission", "subparts": [{{"name": "Gearbox"}}, {{"name": "Clutch"}}, {{"name": "Differential"}}]}}
]
alternative_dimensions: ["Functional Modules", "Life Cycle", "User Experience", "Manufacturing Process", "Price Segments"]

Do not include any information about visual layout or braces; only provide the hierarchical data.

Please ensure the JSON format is correct, do not include any code block markers.
"""

BRACE_MAP_GENERATION_ZH = """
请生成一个括号图（Brace Map）的JSON规范。

括号图用于拆分，表示整体与部分之间的关系。

核心概念：拆解维度
括号图可以使用不同的维度来拆解主题。您必须：
✓ 选择一个维度并在整个图中保持一致
✗ 绝不在同一张图中混合不同的维度

常见拆解维度（以"汽车"为例）：
1. 物理部件（结构性）：发动机、底盘、变速箱、车身
2. 功能模块（功能性）：动力系统、安全系统、舒适系统、娱乐系统
3. 生命周期（时间性）：设计阶段、制造阶段、使用阶段、回收阶段
4. 用户体验（体验性）：驾驶体验、舒适体验、安全体验、科技体验
5. 制造流程：原材料、组装、质量控制、配送
6. 价格区间：经济型、中档型、豪华型、超豪华型

关键：用户指定维度优先
如果用户在请求中明确指定了拆解维度或标准（例如："按功能拆解"、"使用生命周期阶段"、"按物理部件分解"），您必须使用用户指定的维度进行拆解。示例：
- 用户说"按功能拆解" → 使用"功能模块"或类似的功能性维度
- 用户说"按物理部件" → 使用"物理部件"维度
- 用户说"按生命周期" → 使用"生命周期"维度
- 用户说"decompose by function" → 使用功能维度
- 用户说"by physical parts" → 使用物理部件维度

请输出一个包含以下字段的JSON对象：
whole: "主题（要拆解的整体）"
dimension: "使用的拆解维度（例如：'物理部件'、'功能模块'）"
parts: [{{"name": "部分1", "subparts": [{{"name": "子部分1.1"}}]}}]
alternative_dimensions: ["维度1", "维度2", "维度3", "维度4"]

重要提示：如果用户需求中包含引号标注的主题（例如："为主题'植物'创建..."），你必须在"whole"字段中使用完全相同的主题词。不要改写、翻译或修改它。

关键要求：必须全部使用中文生成内容，包括whole、dimension、parts数组、subparts数组和alternative_dimensions数组中的所有文本。不要混用英文和中文。请生成全新的、有意义的部分和子部分内容，不要使用占位符文本如"部分1"、"子部分1.1"等。

要求：
- 生成3-6个主要部分，名称清晰、描述性强
- 每个部分应有2-5个子部分，具体且详细
- 使用简洁、清晰的语言，避免长句
- 确保使用一个一致的维度来建立逻辑的整体→部分→子部分关系
- "dimension"字段必须清楚地描述所使用的拆解方法
- 所有部分和子部分必须遵循相同的维度（例如，如果使用"物理部件"，所有项目必须是物理组件）
- 如果用户指定了维度，必须遵循并使用该维度作为主要拆解标准

关键：替代维度要求
- "alternative_dimensions"数组必须列出4-6个针对此特定主题的其他有效维度
- 每个替代维度必须与你选择的维度不同
- 每个替代维度都应该是分解此主题的同样有效的方式（不是随机建议）
- 思考："还有哪些有意义的方式可以分解这个主题？"
- "汽车"主题示例：
  * 如果选择"物理部件" → 替代维度可以是："功能模块"、"制造流程"、"价格区间"、"能源类型"、"用户体验"
  * 如果选择"功能模块" → 替代维度可以是："物理部件"、"生命周期阶段"、"市场细分"、"技术水平"
- 使替代维度针对主题具体化，而不是通用维度

示例格式（仅供参考）：
whole: "汽车"
dimension: "物理部件"
parts: [
  {{"name": "发动机", "subparts": [{{"name": "气缸"}}, {{"name": "活塞"}}, {{"name": "曲轴"}}]}},
  {{"name": "底盘", "subparts": [{{"name": "车架"}}, {{"name": "悬挂系统"}}, {{"name": "车轴"}}]}},
  {{"name": "变速箱", "subparts": [{{"name": "齿轮箱"}}, {{"name": "离合器"}}, {{"name": "差速器"}}]}}
]
alternative_dimensions: ["功能模块", "生命周期", "用户体验", "制造流程", "价格区间"]

不要包含任何关于可视化布局或括号形状的说明；只提供层级数据。

请确保JSON格式正确，不要包含任何代码块标记。
"""

# Brace Map: Fixed dimension mode - user has already specified the decomposition dimension
BRACE_MAP_FIXED_DIMENSION_EN = """You are completing a brace map where the user has ALREADY SPECIFIED the decomposition dimension.

CRITICAL: The decomposition dimension is FIXED and must NOT be changed.
The user has defined the dimension, and you must generate parts and subparts using this EXACT dimension.

Your tasks:
1. Accept the user's specified decomposition dimension as-is - DO NOT modify or reinterpret it
2. Generate 3-5 parts that follow the specified dimension
3. Generate 2-4 subparts for each part
4. Suggest alternative dimensions that could be used for future brace maps on this topic

RULES:
- The "dimension" field in your response MUST be EXACTLY what the user specified - copy it verbatim
- All parts MUST follow the user's specified decomposition dimension
- Generate meaningful, educational content - no placeholder text
- Keep part and subpart names concise (1-4 words)

Return ONLY a valid JSON object with these fields:
{
  "whole": "Main topic",
  "dimension": "[COPY THE USER'S SPECIFIED DIMENSION EXACTLY]",
  "parts": [
    {"name": "Part 1", "subparts": [{"name": "Subpart A"}, {"name": "Subpart B"}]},
    {"name": "Part 2", "subparts": [{"name": "Subpart X"}, {"name": "Subpart Y"}]}
  ],
  "alternative_dimensions": ["Alternative 1", "Alternative 2", "Alternative 3", "Alternative 4"]
}

Output ONLY valid JSON (no code blocks, no markdown, no explanation)."""

BRACE_MAP_FIXED_DIMENSION_ZH = """你正在完成一个括号图，用户已经指定了拆解维度。

重要：拆解维度已经固定，不能更改。
用户已经定义了维度，你必须使用这个确切的维度来生成部分和子部分。

你的任务：
1. 原样接受用户指定的拆解维度 - 不要修改或重新解释它
2. 生成3-5个遵循指定维度的部分
3. 每个部分生成2-4个子部分
4. 建议其他可用于此主题未来括号图的替代维度

规则：
- 你返回的"dimension"字段必须与用户指定的完全相同 - 逐字复制
- 所有部分必须遵循用户指定的拆解维度
- 生成有意义的、有教育意义的内容 - 不要使用占位符文本
- 保持部分和子部分名称简洁（1-4个词）

只返回一个有效的JSON对象，包含以下字段：
{
  "whole": "主题",
  "dimension": "[完全复制用户指定的维度]",
  "parts": [
    {"name": "部分1", "subparts": [{"name": "子部分甲"}, {"name": "子部分乙"}]},
    {"name": "部分2", "subparts": [{"name": "子部分A"}, {"name": "子部分B"}]}
  ],
  "alternative_dimensions": ["替代维度1", "替代维度2", "替代维度3", "替代维度4"]
}

只输出有效的JSON（无代码块，无markdown，无解释）。"""

# Brace Map: Dimension-only mode - user provides ONLY the decomposition dimension, no topic
BRACE_MAP_DIMENSION_ONLY_EN = """You are generating a brace map where the user has ONLY provided a decomposition dimension.

The user has specified a decomposition dimension (like "Physical Parts", "Functional Modules", "Life Cycle", "User Experience") but has NOT provided a topic. Your job is to:
1. Keep the decomposition dimension EXACTLY as the user specified - DO NOT modify it
2. Generate a suitable topic that can be decomposed using this dimension
3. Generate 3-5 parts following this dimension
4. Each part should have 2-4 subparts
5. Suggest alternative decomposition dimensions in the same domain

CRITICAL RULES:
- The dimension field MUST be EXACTLY what the user specified - copy it verbatim
- Generate a meaningful topic that fits the decomposition dimension
- Generate 3-5 high-quality, diverse parts that clearly demonstrate the dimension
- Each subpart must be specific and relevant to its parent part
- Suggest 4-6 alternative decomposition dimensions that are related but different

Examples of dimension-only inputs:
- "Physical Parts" → Generate topic: "Car", parts: Engine, Chassis, Transmission, Body
- "Functional Modules" → Generate topic: "Computer", parts: CPU, Memory, Storage, Display
- "Life Cycle" → Generate topic: "Product", parts: Design Phase, Manufacturing Phase, Usage Phase, Recycling Phase

Return ONLY a valid JSON object with these fields:
{
  "whole": "[GENERATE A SUITABLE TOPIC]",
  "dimension": "[COPY THE USER'S DECOMPOSITION DIMENSION EXACTLY]",
  "parts": [
    {"name": "Part1", "subparts": [{"name": "Subpart1.1"}, {"name": "Subpart1.2"}]},
    {"name": "Part2", "subparts": [{"name": "Subpart2.1"}, {"name": "Subpart2.2"}]}
  ],
  "alternative_dimensions": ["Alternative 1", "Alternative 2", "Alternative 3", "Alternative 4"]
}

Output ONLY valid JSON (no code blocks, no markdown, no explanation)."""

BRACE_MAP_DIMENSION_ONLY_ZH = """你正在生成一个括号图，用户只提供了拆解维度。

用户指定了一个拆解维度（如"物理部件"、"功能模块"、"生命周期"、"用户体验"），但没有提供主题。你的任务是：
1. 完全保持用户指定的拆解维度不变 - 不要修改它
2. 生成一个适合使用此维度进行拆解的主题
3. 生成3-5个遵循此维度的部分
4. 每个部分应有2-4个子部分
5. 建议同一领域的替代拆解维度

关键规则：
- dimension字段必须与用户指定的完全相同 - 逐字复制
- 生成一个适合拆解维度的有意义的主题
- 生成3-5个高质量、多样化的部分，清楚地展示该维度
- 每个子部分必须具体且与其父部分相关
- 建议4-6个相关但不同的替代拆解维度

仅维度输入的示例：
- "物理部件" → 生成主题："汽车"，部分：发动机、底盘、变速箱、车身
- "功能模块" → 生成主题："计算机"，部分：CPU、内存、存储、显示器
- "生命周期" → 生成主题："产品"，部分：设计阶段、制造阶段、使用阶段、回收阶段

只返回一个有效的JSON对象，包含以下字段：
{
  "whole": "[生成一个合适的主题]",
  "dimension": "[完全复制用户指定的拆解维度]",
  "parts": [
    {"name": "部分1", "subparts": [{"name": "子部分1.1"}, {"name": "子部分1.2"}]},
    {"name": "部分2", "subparts": [{"name": "子部分2.1"}, {"name": "子部分2.2"}]}
  ],
  "alternative_dimensions": ["替代维度1", "替代维度2", "替代维度3", "替代维度4"]
}

只输出有效的JSON（无代码块，无markdown，无解释）。"""

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

    # Bridge map identify relationship prompts (for auto-complete with existing pairs)
    "bridge_map_identify_relationship_en": BRIDGE_MAP_IDENTIFY_RELATIONSHIP_EN,
    "bridge_map_identify_relationship_zh": BRIDGE_MAP_IDENTIFY_RELATIONSHIP_ZH,

    # Bridge map fixed dimension prompts (for auto-complete when user has already specified the relationship)
    "bridge_map_fixed_dimension_en": BRIDGE_MAP_FIXED_DIMENSION_EN,
    "bridge_map_fixed_dimension_zh": BRIDGE_MAP_FIXED_DIMENSION_ZH,

    # Bridge map relationship-only prompts (user provides ONLY the relationship, no pairs)
    "bridge_map_relationship_only_en": BRIDGE_MAP_RELATIONSHIP_ONLY_EN,
    "bridge_map_relationship_only_zh": BRIDGE_MAP_RELATIONSHIP_ONLY_ZH,

    # Agent-specific prompt keys (what agents are actually calling for)
    "bridge_map_agent_generation_en": BRIDGE_MAP_GENERATION_EN,
    "bridge_map_agent_generation_zh": BRIDGE_MAP_GENERATION_ZH,
    "bridge_map_agent_identify_relationship_en": BRIDGE_MAP_IDENTIFY_RELATIONSHIP_EN,
    "bridge_map_agent_identify_relationship_zh": BRIDGE_MAP_IDENTIFY_RELATIONSHIP_ZH,
    "bridge_map_agent_fixed_dimension_en": BRIDGE_MAP_FIXED_DIMENSION_EN,
    "bridge_map_agent_fixed_dimension_zh": BRIDGE_MAP_FIXED_DIMENSION_ZH,
    "bridge_map_agent_relationship_only_en": BRIDGE_MAP_RELATIONSHIP_ONLY_EN,
    "bridge_map_agent_relationship_only_zh": BRIDGE_MAP_RELATIONSHIP_ONLY_ZH,
    "bubble_map_agent_generation_en": BUBBLE_MAP_GENERATION_EN,
    "bubble_map_agent_generation_zh": BUBBLE_MAP_GENERATION_ZH,
    "double_bubble_map_agent_generation_en": DOUBLE_BUBBLE_MAP_GENERATION_EN,
    "double_bubble_map_agent_generation_zh": DOUBLE_BUBBLE_MAP_GENERATION_ZH,
    "circle_map_agent_generation_en": CIRCLE_MAP_GENERATION_EN,
    "circle_map_agent_generation_zh": CIRCLE_MAP_GENERATION_ZH,
    "tree_map_agent_generation_en": TREE_MAP_GENERATION_EN,
    "tree_map_agent_generation_zh": TREE_MAP_GENERATION_ZH,
    "tree_map_agent_fixed_dimension_en": TREE_MAP_FIXED_DIMENSION_EN,
    "tree_map_agent_fixed_dimension_zh": TREE_MAP_FIXED_DIMENSION_ZH,
    "flow_map_agent_generation_en": FLOW_MAP_GENERATION_EN,
    "flow_map_agent_generation_zh": FLOW_MAP_GENERATION_ZH,
    "brace_map_agent_generation_en": BRACE_MAP_GENERATION_EN,
    "brace_map_agent_generation_zh": BRACE_MAP_GENERATION_ZH,
    "brace_map_agent_fixed_dimension_en": BRACE_MAP_FIXED_DIMENSION_EN,
    "brace_map_agent_fixed_dimension_zh": BRACE_MAP_FIXED_DIMENSION_ZH,
    "brace_map_agent_dimension_only_en": BRACE_MAP_DIMENSION_ONLY_EN,
    "brace_map_agent_dimension_only_zh": BRACE_MAP_DIMENSION_ONLY_ZH,
    "multi_flow_map_agent_generation_en": MULTI_FLOW_MAP_GENERATION_EN,
    "multi_flow_map_agent_generation_zh": MULTI_FLOW_MAP_GENERATION_ZH,
}