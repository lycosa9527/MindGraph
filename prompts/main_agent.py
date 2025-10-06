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
- "generate a bubble map about mind maps" → user wants bubble_map, topic is about mind maps → bubble_map
- "generate a mind map about concept maps" → user wants mind_map, topic is about concept maps → mind_map
- "generate a concept map about mind maps" → user wants concept_map, topic is about mind maps → concept_map
- "generate a double bubble map comparing apples and oranges" → user wants double_bubble_map → double_bubble_map
- "generate a bridge map showing learning is like building" → user wants bridge_map → bridge_map
- "generate a tree map for animal classification" → user wants tree_map → tree_map
- "generate a circle map defining climate change" → user wants circle_map → circle_map
- "generate a multi-flow map analyzing lamp explosion" → user wants multi_flow_map → multi_flow_map
- "generate a flow map showing coffee making steps" → user wants flow_map → flow_map
- "generate a brace map breaking down computer parts" → user wants brace_map → brace_map

User input: "{user_prompt}"

Based on user intent and content analysis, select the most appropriate diagram type:

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
11. factor_analysis (Factor Analysis) - analyzing key factors affecting a topic
12. three_position_analysis (Three-Position Analysis) - examining from three perspectives
13. perspective_analysis (Perspective Analysis) - understanding different viewpoints
14. goal_analysis (Goal Analysis) - breaking down goals into actions
15. possibility_analysis (Possibility Analysis) - exploring options and alternatives
16. result_analysis (Result Analysis) - analyzing outcomes and consequences
17. five_w_one_h (5W1H Analysis) - systematic analysis (What, Why, When, Where, Who, How)
18. whwm_analysis (WHWM Analysis) - project planning (What, How, Who, Measure)
19. four_quadrant (Four Quadrant Analysis) - categorizing into four quadrants

Edge Cases and Decision Logic:
- If user intent is unclear or ambiguous, prefer mind_map (most versatile)
- If multiple types could fit, choose the most specific one
- If user mentions "chart", "graph", or "diagram" without specifics, analyze the content intent
- If user wants to compare/contrast two things, use double_bubble_map
- If user wants to show causes and effects, use multi_flow_map
- If user wants to show steps or processes, use flow_map

Return only the diagram type name (e.g., bubble_map), no other content."""

CLASSIFICATION_ZH = """分析以下用户输入，判断用户想要创建的图表类型。

重要：区分用户想要创建的图表类型 vs 图表内容主题
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
- "生成一个括号图分解电脑组成部分" → 用户要创建括号图 → brace_map

用户输入："{user_prompt}"

基于用户意图和内容分析，选择最合适的图表类型：

1. bubble_map (气泡图) - 描述事物的属性、特征、特点
2. bridge_map (桥形图) - 通过类比来理解新概念
3. tree_map (树形图) - 分类、层次结构、组织架构
4. circle_map (圆圈图) - 联想，围绕中心主题生成相关的信息
5. double_bubble_map (双气泡图) - 对比两个事物的异同
6. multi_flow_map (复流程图) - 因果关系、事件的多重原因和结果
7. flow_map (流程图) - 步骤序列、过程流程
8. brace_map (括号图) - 对中心词进行拆分，整体与部分的关系
9. concept_map (概念图) - 概念间的关系网络
10. mind_map (思维导图) - 发散思维、头脑风暴
11. factor_analysis (因素分析法) - 分析影响主题的关键因素
12. three_position_analysis (三位分析法) - 从三个角度审视问题
13. perspective_analysis (换位分析法) - 理解不同的视角和立场
14. goal_analysis (目标分析法) - 将目标分解为具体行动
15. possibility_analysis (可能分析法) - 探索选项和替代方案
16. result_analysis (结果分析法) - 分析结果和后果
17. five_w_one_h (六何分析法) - 系统性分析（什么、为什么、何时、何地、谁、如何）
18. whwm_analysis (WHWM分析法) - 项目规划（做什么、怎么做、谁来做、如何衡量）
19. four_quadrant (四象限分析法) - 按四个象限分类

边缘情况和决策逻辑：
- 如果用户意图不明确或模糊，优先选择 mind_map（最通用）
- 如果多个类型都适用，选择最具体的那个
- 如果用户提到"图表"、"图形"或"图"但没有具体说明，分析内容意图
- 如果用户想要对比两个事物，使用 double_bubble_map
- 如果用户想要显示因果关系，使用 multi_flow_map
- 如果用户想要显示步骤或流程，使用 flow_map

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