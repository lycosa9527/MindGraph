"""
Main Agent Prompts

This module contains prompts used by the main agent for:
- Concept generation for various diagram types
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
- "generate a mind map about concept maps" → user wants mind_map, topic is about concept maps → mind_map
- "generate a concept map about mind maps" → user wants concept_map, topic is about mind maps → concept_map
- "generate a double bubble map comparing apples and oranges" → user wants double_bubble_map → double_bubble_map

User input: "{user_prompt}"

Key phrases to identify:
- "generate... bubble map" / "create... bubble map" → bubble_map
- "generate... double bubble map" / "create... double bubble map" → double_bubble_map
- "generate... mind map" / "create... mind map" → mind_map
- "generate... concept map" / "create... concept map" → concept_map
- "generate... flow map" / "create... flow map" → flow_map
- "generate... tree map" / "create... tree map" → tree_map
- Focus on what diagram type the user is requesting (after "generate/create"), not the topic content (after "about")

Available diagram types and their use cases:
1. bubble_map (Bubble Map) - describing attributes, characteristics, features
2. bridge_map (Bridge Map) - analogies, comparing similarities between concepts
3. tree_map (Tree Map) - classification, hierarchy, organizational structure
4. circle_map (Circle Map) - association, generating related information around the central topic
5. double_bubble_map (Double Bubble Map) - comparing and contrasting two things
6. multi_flow_map (Multi-Flow Map) - cause-effect relationships, multiple causes and effects
7. flow_map (Flow Map) - step sequences, process flows
8. brace_map (Brace Map) - decomposing the central topic, whole-to-part relationships
9. concept_map (Concept Map) - relationship networks between concepts
10. mind_map (Mind Map) - divergent thinking, brainstorming

Return only the diagram type name (e.g., bubble_map), no other content."""

CLASSIFICATION_ZH = """分析以下用户输入，判断用户想要创建的图表类型。

重要：区分用户想要创建的图表类型 vs 图表内容主题
- "生成一个关于双气泡图的气泡图" → 用户要创建气泡图，主题是双气泡图 → bubble_map
- "生成一个关于概念图的思维导图" → 用户要创建思维导图，主题是概念图 → mind_map
- "生成一个关于思维导图的概念图" → 用户要创建概念图，主题是思维导图 → concept_map
- "生成一个双气泡图比较苹果和橙子" → 用户要创建双气泡图 → double_bubble_map

用户输入："{user_prompt}"

注意识别关键词：
- "生成...的气泡图" / "创建...的气泡图" → bubble_map
- "生成...的双气泡图" / "创建...的双气泡图" → double_bubble_map
- "生成...的思维导图" / "创建...的思维导图" → mind_map
- "生成...的概念图" / "创建...的概念图" → concept_map
- "生成...的流程图" / "创建...的流程图" → flow_map
- "生成...的树形图" / "创建...的树形图" → tree_map
- 重点关注用户要求的图表类型（"的X图"中的X），而不是内容主题（"关于Y"中的Y）

可选图表类型及其适用场景：
1. bubble_map (气泡图) - 描述事物的属性、特征、特点
2. bridge_map (桥梁图) - 通过类比来理解新概念
3. tree_map (树形图) - 分类、层次结构、组织架构
4. circle_map (圆圈图) - 联想，围绕中心主题生成相关的信息
5. double_bubble_map (双气泡图) - 对比两个事物的异同
6. multi_flow_map (复流程图) - 因果关系、事件的多重原因和结果
7. flow_map (流程图) - 步骤序列、过程流程
8. brace_map (括号图) - 对中心词进行拆分，整体与部分的关系
9. concept_map (概念图) - 概念间的关系网络
10. mind_map (思维导图) - 发散思维、头脑风暴

请只返回图表类型的英文名称（如：bubble_map），不要返回其他内容。"""

# Main agent prompt registry
MAIN_AGENT_PROMPTS = {
    # Concept generation  
    "concept_30_generation_en": CONCEPT_30_EN,
    "concept_30_generation_zh": CONCEPT_30_ZH,
    # Classification
    "classification_generation_en": CLASSIFICATION_EN,
    "classification_generation_zh": CLASSIFICATION_ZH,
}