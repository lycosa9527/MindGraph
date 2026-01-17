"""
Tab Mode Expansion Prompts
==========================

Expansion prompts for viewing mode (when users press Tab to expand nodes).

@author MindGraph Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

# Mindmap Expansion
TAB_MODE_MINDMAP_EXPANSION_EN = """You are an intelligent node expansion assistant. The user clicked a branch node in a mindmap and wants to generate child nodes.

Main topic: {main_topic}
Branch node: {node_text}
Existing children: {existing_children}

Generate {num_children} child nodes for this branch. Each child node should:
- Be directly related to the branch topic
- Be concise (2-4 words)
- Follow educational/teaching principles
- Be mutually exclusive and collectively exhaustive (MECE)

Return only a JSON array, each element is a child node text.
Example: ["Group Discussions", "Role Playing", "Case Studies", "Peer Teaching"]"""

TAB_MODE_MINDMAP_EXPANSION_ZH = """你是一个智能节点扩展助手。用户点击了思维导图中的一个分支节点，想要生成子节点。

中心主题：{main_topic}
分支节点：{node_text}
已有子节点：{existing_children}

为此分支生成 {num_children} 个子节点。每个子节点应该：
- 与分支主题直接相关
- 简洁（2-4个字）
- 遵循教学/教育原则
- 相互独立且完全穷尽（MECE）

只返回JSON数组，每个元素是子节点文本。
示例：["小组讨论", "角色扮演", "案例分析", "同伴教学"]"""

# Tree Map Expansion
TAB_MODE_TREE_MAP_EXPANSION_EN = """You are an intelligent node expansion assistant. The user clicked a category node in a tree map and wants to generate items.

Main topic: {main_topic}
Category node: {node_text}
Existing items: {existing_children}

Generate {num_children} items for this category. Each item should:
- Be a specific example within the category
- Be concise (1-3 words)
- Be mutually exclusive from other items

Return only a JSON array, each element is an item text.
Example: ["Apples", "Oranges", "Bananas", "Grapes"]"""

TAB_MODE_TREE_MAP_EXPANSION_ZH = """你是一个智能节点扩展助手。用户点击了树状图中的类别节点，想要生成项目。

中心主题：{main_topic}
类别节点：{node_text}
已有项目：{existing_children}

为此类别生成 {num_children} 个项目。每个项目应该：
- 是类别中的具体示例
- 简洁（1-3个字）
- 与其他项目相互独立

只返回JSON数组，每个元素是项目文本。
示例：["苹果", "橙子", "香蕉", "葡萄"]"""

# Flow Map Expansion
TAB_MODE_FLOW_MAP_EXPANSION_EN = """You are an intelligent node expansion assistant. The user clicked a step node in a flow map and wants to generate substeps.

Flow title: {main_topic}
Step node: {node_text}
Existing substeps: {existing_children}

Generate {num_children} substeps for this step. Each substep should:
- Be a detailed action within the step
- Be concise (2-5 words)
- Be sequential and logical

Return only a JSON array, each element is a substep text.
Example: ["Heat water", "Add coffee", "Steep", "Strain"]"""

TAB_MODE_FLOW_MAP_EXPANSION_ZH = """你是一个智能节点扩展助手。用户点击了流程图中的步骤节点，想要生成子步骤。

流程标题：{main_topic}
步骤节点：{node_text}
已有子步骤：{existing_children}

为此步骤生成 {num_children} 个子步骤。每个子步骤应该：
- 是步骤内的详细操作
- 简洁（2-5个字）
- 顺序合理且逻辑清晰

只返回JSON数组，每个元素是子步骤文本。
示例：["加热水", "加入咖啡", "浸泡", "过滤"]"""

# Brace Map Expansion
TAB_MODE_BRACE_MAP_EXPANSION_EN = """You are an intelligent node expansion assistant. The user clicked a part node in a brace map and wants to generate subparts.

Whole: {main_topic}
Part node: {node_text}
Existing subparts: {existing_children}

Generate {num_children} subparts for this part. Each subpart should:
- Be a component within the part
- Be concise (1-3 words)
- Be mutually exclusive

Return only a JSON array, each element is a subpart text.
Example: ["Cores", "Cache", "Clock Speed", "Architecture"]"""

TAB_MODE_BRACE_MAP_EXPANSION_ZH = """你是一个智能节点扩展助手。用户点击了括号图中的部分节点，想要生成子部分。

整体：{main_topic}
部分节点：{node_text}
已有子部分：{existing_children}

为此部分生成 {num_children} 个子部分。每个子部分应该：
- 是部分内的组件
- 简洁（1-3个字）
- 相互独立

只返回JSON数组，每个元素是子部分文本。
示例：["核心", "缓存", "时钟速度", "架构"]"""

# Registry
TAB_MODE_EXPANSION_PROMPTS = {
    "tab_mode_mindmap_expansion_en": TAB_MODE_MINDMAP_EXPANSION_EN,
    "tab_mode_mindmap_expansion_zh": TAB_MODE_MINDMAP_EXPANSION_ZH,
    "tab_mode_tree_map_expansion_en": TAB_MODE_TREE_MAP_EXPANSION_EN,
    "tab_mode_tree_map_expansion_zh": TAB_MODE_TREE_MAP_EXPANSION_ZH,
    "tab_mode_flow_map_expansion_en": TAB_MODE_FLOW_MAP_EXPANSION_EN,
    "tab_mode_flow_map_expansion_zh": TAB_MODE_FLOW_MAP_EXPANSION_ZH,
    "tab_mode_brace_map_expansion_en": TAB_MODE_BRACE_MAP_EXPANSION_EN,
    "tab_mode_brace_map_expansion_zh": TAB_MODE_BRACE_MAP_EXPANSION_ZH,
}

