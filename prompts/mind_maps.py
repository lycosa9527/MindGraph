"""
Mind Maps Prompts

This module contains prompts for mind maps and related diagrams.
"""

# ============================================================================
# MIND MAP PROMPTS
# ============================================================================

MINDMAP_GENERATION_EN = """
Please generate a JSON specification for a mind map for the following user request.

Request: {user_prompt}

Please output ONLY a valid JSON object with this exact structure:

{
  "topic": "Central Topic Name",
  "children": [
    {
      "id": "branch_1",
      "label": "Branch 1 Label",
      "children": [
        {"id": "sub_1_1", "label": "Sub-item 1.1"},
        {"id": "sub_1_2", "label": "Sub-item 1.2"}
      ]
    },
    {
      "id": "branch_2", 
      "label": "Branch 2 Label",
      "children": [
        {"id": "sub_2_1", "label": "Sub-item 2.1"}
      ]
    }
  ]
}

CRITICAL JSON Requirements:
- Output ONLY valid JSON - no explanations, no code blocks, no extra text
- Each node MUST have both "id" and "label" fields
- ALL children arrays must be properly closed with ]
- ALL objects must be properly closed with }
- IDs should be lowercase with underscores (e.g., "main_topic", "sub_item")
- Labels should be descriptive text for display
- Generate EXACTLY 4, 6, or 8 main branches (ALWAYS EVEN numbers), each with 2-4 sub-items
- Ensure every comma, bracket, and brace is correctly placed

LOGICAL ORGANIZATION (IMPORTANT):
The mind map follows a clockwise layout starting from top-right. Organize subtopics logically:

- Branch 1 (Top-Right): ALWAYS start with the DEFINITION or CORE CONCEPT of the topic
- Branch 2 (Middle-Right): Continue with supporting or secondary concepts
- Branch 3 (Bottom-Right): Add related or complementary concepts
- Branch 4 (Top-Left): Include contrasting or alternative concepts
- Branch 5 (Bottom-Left): Add final or concluding concepts

For 6+ branches, continue the logical flow while maintaining left-right balance.

EVEN BRANCHES REQUIREMENT (CRITICAL):
- Always generate an EVEN number of branches (4, 6, or 8)
- This ensures perfect left-right visual balance in the mind map
- Distribute content evenly: similar complexity and length across all branches

Each branch should contain related subtopics that flow logically from the main concept.

BRANCH ORDERING PRINCIPLE:
Follow a logical sequence such as:
- By importance (most important to least important)
- By abstraction level (abstract to concrete)
- By process flow (step 1, step 2, etc.)
- By category hierarchy (main category → subcategories)

EXAMPLE LOGICAL FLOW:
For a topic like "Digital Marketing":
- Branch 1: "Definition" (WHAT is digital marketing - always start here)
- Branch 2: "Strategy" (fundamental approach)
- Branch 3: "Channels" (supporting - how to implement)
- Branch 4: "Tools" (complementary - what you need)
- Branch 5: "Analytics" (measurement and optimization)

Please ensure the JSON format is correct, do not include any code block markers.
"""

MINDMAP_GENERATION_ZH = """
请为以下用户需求生成一个思维导图的JSON规范。

需求：{user_prompt}

请输出一个有效的JSON对象，严格按照以下结构：

{
  "topic": "中心主题名称",
  "children": [
    {
      "id": "fen_zhi_1",
      "label": "分支1标签",
      "children": [
        {"id": "zi_xiang_1_1", "label": "子项1.1"},
        {"id": "zi_xiang_1_2", "label": "子项1.2"}
      ]
    },
    {
      "id": "fen_zhi_2",
      "label": "分支2标签", 
      "children": [
        {"id": "zi_xiang_2_1", "label": "子项2.1"}
      ]
    }
  ]
}

关键JSON要求：
- 只输出有效的JSON - 不要解释，不要代码块，不要额外文字
- 每个节点必须同时包含"id"和"label"字段
- 所有children数组必须用]正确闭合
- 所有对象必须用}正确闭合
- ID应该使用小写字母和下划线（如："zhu_ti", "zi_xiang"）
- Label应该是用于显示的描述性文本
- 生成恰好4、6或8个主要分支（始终为偶数），每个分支包含2-4个子项
- 确保每个逗号、括号和大括号都正确放置

逻辑组织（重要）：
思维导图遵循从右上角开始的顺时针布局。请按逻辑组织子主题：

- 分支1（右上）：始终从主题的"定义"或"核心概念"开始
- 分支2（中右）：继续支持性或次要概念
- 分支3（右下）：添加相关或补充概念
- 分支4（左上）：包含对比或替代概念
- 分支5（左下）：添加最终或总结概念

对于6个以上分支，继续逻辑流程同时保持左右平衡。

偶数分支要求（关键）：
- 始终生成偶数个分支（4、6或8个）
- 这确保思维导图完美的左右视觉平衡
- 内容分布均匀：所有分支的复杂性和长度相似

每个分支应包含与主概念逻辑相关的子主题。

分支排序原则：
遵循一定的逻辑序列，如：
- 按重要性排序（最重要到最不重要）
- 按抽象层次排序（抽象到具体）
- 按流程排序（步骤1、步骤2等）
- 按类别层次排序（主类别→子类别）

逻辑流程示例：
以"数字营销"为例：
- 分支1："定义"（什么是数字营销 - 始终从这里开始）
- 分支2："策略"（基础方法）
- 分支3："渠道"（支持 - 如何实施）
- 分支4："工具"（补充 - 你需要什么）
- 分支5："分析"（测量和优化）

请确保JSON格式正确，不要包含任何代码块标记。
"""

# From MindMapAgent - the actual prompts currently being used
MIND_MAP_AGENT_GENERATION_EN = """You are a professional mind mapping expert specializing in mind maps. Mind maps are used to show the branch structure of topics.

Please create a detailed mind map specification based on the user's description. The output must be valid JSON, strictly following this structure:

{
  "topic": "Central Topic",
  "children": [
    {
      "id": "branch_1",
      "label": "Branch 1 Label",
      "children": [
        {"id": "sub_1_1", "label": "Sub-item 1.1"},
        {"id": "sub_1_2", "label": "Sub-item 1.2"}
      ]
    },
    {
      "id": "branch_2",
      "label": "Branch 2 Label",
      "children": [
        {"id": "sub_2_1", "label": "Sub-item 2.1"}
      ]
    }
  ]
}

CRITICAL Requirements:
- Output ONLY valid JSON - no explanations, no code blocks, no extra text
- Central topic should be clear and specific
- Each node must have both id and label fields
- ALL children arrays must be properly closed with ]
- ALL objects must be properly closed with }
- Branches should be organized in logical order
- Use concise but descriptive text
- Ensure the JSON format is completely valid with no syntax errors"""

MIND_MAP_AGENT_GENERATION_ZH = """你是一个专业的思维导图专家，专门创建思维导图。思维导图用于展示主题的分支结构。

请根据用户的描述，创建一个详细的思维导图规范。输出必须是有效的JSON格式，严格按照以下结构：

{
  "topic": "中心主题",
  "children": [
    {
      "id": "fen_zhi_1",
      "label": "分支1标签",
      "children": [
        {"id": "zi_xiang_1_1", "label": "子项1.1"},
        {"id": "zi_xiang_1_2", "label": "子项1.2"}
      ]
    },
    {
      "id": "fen_zhi_2",
      "label": "分支2标签",
      "children": [
        {"id": "zi_xiang_2_1", "label": "子项2.1"}
      ]
    }
  ]
}

关键要求：
- 只输出有效的JSON - 不要解释，不要代码块，不要额外文字
- 中心主题应该清晰明确
- 每个节点必须有id和label字段
- 所有children数组必须用]正确闭合
- 所有对象必须用}正确闭合
- 分支应该按逻辑顺序组织
- 使用简洁但描述性的文本
- 确保JSON格式完全有效，没有语法错误"""

# ============================================================================
# PROMPT REGISTRY
# ============================================================================

MIND_MAP_PROMPTS = {
    "mindmap_generation_en": MINDMAP_GENERATION_EN,
    "mindmap_generation_zh": MINDMAP_GENERATION_ZH,
    
    # Current agent prompts (ACTIVE - these are what the agent is actually using)
    # Format: diagram_type_prompt_type_language
    "mind_map_generation_en": MIND_MAP_AGENT_GENERATION_EN,
    "mind_map_generation_zh": MIND_MAP_AGENT_GENERATION_ZH,
} 