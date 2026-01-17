"""
Main Agent Prompts

This module contains prompts used by the main agent for:
- Concept generation for various diagram types

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

# Concept generation prompts
CONCEPT_30_EN = """Please generate exactly 30 specific and meaningful concepts related to the topic: {central_topic}

Requirements:
1. Each concept should be 1-3 words maximum
2. Concepts should be diverse and cover different aspects of the topic
3. Include both concrete and abstract concepts where applicable
4. Ensure concepts are relevant and directly related to the central topic
5. Output as a JSON array of strings

Example format:
["concept1", "concept2", "concept3", ...]

Generate exactly 30 concepts, no more, no less."""

CONCEPT_30_ZH = """请为主题"{central_topic}"生成恰好30个相关的关键概念。

要求：
1. 每个概念最多1-3个词
2. 概念应该多样化，涵盖主题的不同方面
3. 在适用的情况下包括具体和抽象概念
4. 确保概念相关并与中心主题直接相关
5. 以JSON字符串数组格式输出

示例格式：
["概念1", "概念2", "概念3", ...]

生成恰好30个概念，不多不少。"""

# Classification prompts
CLASSIFICATION_EN = """Analyze the following user input and determine what type of diagram the user wants to CREATE.

Important: Distinguish between the diagram type the user wants vs the topic content
- "generate a bubble map about double bubble maps" → user wants bubble_map, topic is about double bubble maps → bubble_map
- "generate a bubble map about mind maps" → user wants bubble_map, topic is about mind maps → bubble_map
- "generate a mind map about thinking maps" → user wants mind_map, topic is about thinking maps → mind_map
- "generate a circle map defining climate change" → user wants circle_map → circle_map
- "generate a double bubble map comparing apples and oranges" → user wants double_bubble_map → double_bubble_map
- "generate a brace map breaking down computer parts" → user wants brace_map → brace_map
- "generate a bridge map showing learning is like building" → user wants bridge_map → bridge_map
- "generate a tree map for animal classification" → user wants tree_map → tree_map
- "generate a flow map showing coffee making steps" → user wants flow_map → flow_map
- "generate a multi-flow map analyzing lamp explosion" → user wants multi_flow_map → multi_flow_map

User input: "{user_prompt}"

Based on user intent and content analysis, select the most appropriate diagram type:

1. circle_map (Circle Map) - association, generating related information around the central topic
2. bubble_map (Bubble Map) - describing attributes, characteristics, features
3. double_bubble_map (Double Bubble Map) - comparing and contrasting two things
4. brace_map (Brace Map) - decomposing the central topic, whole-to-part relationships
5. bridge_map (Bridge Map) - analogies, comparing similarities between concepts
6. tree_map (Tree Map) - classification, hierarchy, organizational structure
7. flow_map (Flow Map) - step sequences, process flows
8. multi_flow_map (Multi-Flow Map) - cause-effect relationships, multiple causes and effects
9. mind_map (Mind Map) - divergent thinking, brainstorming

Edge Cases and Decision Logic:
- If user intent is unclear or ambiguous, prefer mind_map (most versatile)
- If multiple types could fit, choose the most specific one
- If user mentions "chart", "graph", or "diagram" without specifics, analyze the content intent
- If user wants to compare/contrast two things, use double_bubble_map
- If user wants to show causes and effects, use multi_flow_map
- If user wants to show steps or processes, use flow_map

IMPORTANT: Only return one of the valid diagram types listed above. If the prompt is too vague,
too complex, or you cannot determine the user's intent, return "unclear" instead.

Return only the diagram type name (e.g., bubble_map) or "unclear", no other content."""

CLASSIFICATION_ZH = """分析以下用户输入，判断用户想要创建的图表类型。

重要：区分用户想要创建的图表类型 vs 图表内容主题
- "生成一个关于双气泡图的气泡图" → 用户要创建气泡图，主题是双气泡图 → bubble_map
- "生成一个关于思维导图的气泡图" → 用户要创建气泡图，主题是思维导图 → bubble_map
- "生成一个关于思维导图的思维导图" → 用户要创建思维导图，主题是思维导图 → mind_map
- "生成一个圆圈图定义气候变化" → 用户要创建圆圈图 → circle_map
- "生成一个双气泡图比较苹果和橙子" → 用户要创建双气泡图 → double_bubble_map
- "生成一个括号图分解电脑组成部分" → 用户要创建括号图 → brace_map
- "生成一个桥形图说明学习像建筑" → 用户要创建桥形图 → bridge_map
- "生成一个树形图展示动物分类" → 用户要创建树形图 → tree_map
- "生成一个流程图展示制作咖啡步骤" → 用户要创建流程图 → flow_map
- "生成一个复流程图分析酒精灯爆炸" → 用户要创建复流程图 → multi_flow_map

用户输入："{user_prompt}"

基于用户意图和内容分析，选择最合适的图表类型：

1. circle_map (圆圈图) - 联想，围绕中心主题生成相关的信息
2. bubble_map (气泡图) - 描述事物的属性、特征、特点
3. double_bubble_map (双气泡图) - 对比两个事物的异同
4. brace_map (括号图) - 对中心词进行拆分，整体与部分的关系
5. bridge_map (桥形图) - 通过类比来理解新概念
6. tree_map (树形图) - 分类、层次结构、组织架构
7. flow_map (流程图) - 步骤序列、过程流程
8. multi_flow_map (复流程图) - 因果关系、事件的多重原因和结果
9. mind_map (思维导图) - 发散思维、头脑风暴

边缘情况和决策逻辑：
- 如果用户意图不明确或模糊，优先选择 mind_map（最通用）
- 如果多个类型都适用，选择最具体的那个
- 如果用户提到"图表"、"图形"或"图"但没有具体说明，分析内容意图
- 如果用户想要对比两个事物，使用 double_bubble_map
- 如果用户想要显示因果关系，使用 multi_flow_map
- 如果用户想要显示步骤或流程，使用 flow_map

重要提示：只能返回上述列出的有效图表类型之一。如果提示过于模糊、过于复杂或无法确定用户意图，
请返回"unclear"而不是猜测。

请只返回图表类型的英文名称（如：bubble_map）或"unclear"，不要返回其他内容。"""

# Topic extraction prompts
TOPIC_EXTRACTION_EN = """Extract ONLY the main topic/subject from this user input.

Critical: The topic is what the diagram is ABOUT, not the diagram type itself.

Examples:
- "generate a bubble map about mind maps" → "mind maps"
- "create a mind map about photosynthesis" → "photosynthesis"
- "make a circle map defining climate change" → "climate change"
- "compare cats and dogs" → "cats and dogs"
- "solar system" → "solar system"

Rules:
1. Extract what the diagram describes/explains/analyzes (the subject matter)
2. Ignore diagram type words (bubble map, mind map, circle map, etc.)
3. Ignore action words (generate, create, make, compare, analyze, etc.)
4. Remove possessive markers and prepositions (about, of, for, 的, 关于)
5. Keep it concise (1-4 words ideal)

User input: "{user_prompt}"

Return ONLY the topic, nothing else:"""

TOPIC_EXTRACTION_ZH = """从用户输入中提取核心主题词。

**核心原则：主题是图表的内容，不是图表本身的类型！**

正确示例：
输入："生成一个关于树形图的气泡图"
分析：用户要创建气泡图（图表类型），内容是关于"树形图"（主题）
输出："树形图"

输入："生成一个关于思维导图的气泡图"
分析：用户要创建气泡图（图表类型），内容是关于"思维导图"（主题）
输出："思维导图"

输入："生成关于华为的气泡图"
分析：用户要创建气泡图（图表类型），内容是关于"华为"（主题）
输出："华为"

输入："创建光合作用的思维导图"
分析：用户要创建思维导图（图表类型），内容是关于"光合作用"（主题）
输出："光合作用"

错误示例（切勿模仿）：
❌ "树形图的气泡图" - 错误！包含了图表类型
❌ "关于华为" - 错误！包含了介词
✓ "树形图" - 正确！纯净的主题词
✓ "华为" - 正确！纯净的主题词

用户输入："{user_prompt}"

请只返回纯净的主题词（不要包含：的、气泡图、思维导图、圆圈图、树形图、等图表类型词）："""

# Main agent prompt registry
MAIN_AGENT_PROMPTS = {
    # Concept generation
    "concept_30_generation_en": CONCEPT_30_EN,
    "concept_30_generation_zh": CONCEPT_30_ZH,
    # Classification
    "classification_generation_en": CLASSIFICATION_EN,
    "classification_generation_zh": CLASSIFICATION_ZH,
    # Topic extraction
    "topic_extraction_generation_en": TOPIC_EXTRACTION_EN,
    "topic_extraction_generation_zh": TOPIC_EXTRACTION_ZH,
}