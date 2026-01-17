"""
Tab Mode Autocomplete Prompts
=============================

Autocomplete prompts for editing mode (when users type in inputs).

@author MindGraph Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

# Double Bubble Map Autocomplete
TAB_MODE_DOUBLE_BUBBLE_AUTOCOMPLETE_EN = """You are an intelligent autocomplete assistant. The user is typing in a double bubble map node.

Left topic: {left_topic}
Right topic: {right_topic}
Current input: {partial_input}
Node category: {node_category}
Existing nodes in this category: {existing_nodes}

Based on the two topics and the current partial input, provide 3-5 most relevant completion suggestions.
- For similarities: Suggest shared characteristics of both topics
- For left differences: Suggest unique characteristics of the left topic
- For right differences: Suggest unique characteristics of the right topic
- Suggestions should be concise (1-4 words)
- Should match the partial input pattern (e.g., if user types "fru...", suggest "fruit")

Return only a JSON array of suggestion strings.
Example: ["fruit", "vitamin C", "round shape"]"""

TAB_MODE_DOUBLE_BUBBLE_AUTOCOMPLETE_ZH = """你是一个智能补全助手。用户正在双气泡图的节点中输入内容。

左主题：{left_topic}
右主题：{right_topic}
当前输入：{partial_input}
节点类别：{node_category}
此类别中的已有节点：{existing_nodes}

请根据两个主题和当前部分输入，提供3-5个最相关的补全建议。
- 对于相似点：建议两个主题的共同特征
- 对于左差异：建议左主题的独特特征
- 对于右差异：建议右主题的独特特征
- 建议应简洁（1-4个字）
- 应匹配部分输入模式（例如，如果用户输入"水..."，建议"水果"）

只返回JSON数组，每个元素是建议文本字符串。
示例：["水果", "维生素C", "圆形"]"""

# Mindmap Child Node Autocomplete
TAB_MODE_MINDMAP_CHILD_AUTOCOMPLETE_EN = """You are an intelligent autocomplete assistant. The user is typing in a child node of a mindmap.

Main topic: {main_topic}
Parent branch: {branch_label}
Current input: {partial_input}
Existing children in this branch: {existing_children}

Based on the main topic and parent branch context, provide 3-5 most relevant completion suggestions for the child node.
- Suggestions should be directly related to the parent branch
- Should follow educational/teaching principles
- Should be concise (2-4 words)

Return only a JSON array of suggestion strings.
Example: ["Group Discussions", "Role Playing", "Case Studies"]"""

TAB_MODE_MINDMAP_CHILD_AUTOCOMPLETE_ZH = """你是一个智能补全助手。用户正在思维导图的子节点中输入内容。

中心主题：{main_topic}
父分支：{branch_label}
当前输入：{partial_input}
此分支的已有子节点：{existing_children}

请根据中心主题和父分支上下文，提供3-5个最相关的子节点补全建议。
- 建议应与父分支直接相关
- 应遵循教学/教育原则
- 应简洁（2-4个字）

只返回JSON数组，每个元素是建议文本字符串。
示例：["小组讨论", "角色扮演", "案例分析"]"""

# Generic Autocomplete (fallback for other diagram types)
TAB_MODE_GENERIC_AUTOCOMPLETE_EN = """You are an intelligent autocomplete assistant. The user is typing in a diagram node.

Main topic: {main_topic}
Node category: {node_category}
Current input: {partial_input}
Existing nodes: {existing_nodes}

Based on the main topic and current partial input, provide 3-5 most relevant completion suggestions.
- Suggestions should be contextually relevant
- Should be concise (1-4 words)
- Should match the partial input pattern

Return only a JSON array of suggestion strings.
Example: ["suggestion1", "suggestion2", "suggestion3"]"""

TAB_MODE_GENERIC_AUTOCOMPLETE_ZH = """你是一个智能补全助手。用户正在图表节点中输入内容。

中心主题：{main_topic}
节点类别：{node_category}
当前输入：{partial_input}
已有节点：{existing_nodes}

请根据中心主题和当前部分输入，提供3-5个最相关的补全建议。
- 建议应上下文相关
- 应简洁（1-4个字）
- 应匹配部分输入模式

只返回JSON数组，每个元素是建议文本字符串。
示例：["建议1", "建议2", "建议3"]"""

# Registry
TAB_MODE_AUTOCOMPLETE_PROMPTS = {
    "tab_mode_double_bubble_autocomplete_en": TAB_MODE_DOUBLE_BUBBLE_AUTOCOMPLETE_EN,
    "tab_mode_double_bubble_autocomplete_zh": TAB_MODE_DOUBLE_BUBBLE_AUTOCOMPLETE_ZH,
    "tab_mode_mindmap_child_autocomplete_en": TAB_MODE_MINDMAP_CHILD_AUTOCOMPLETE_EN,
    "tab_mode_mindmap_child_autocomplete_zh": TAB_MODE_MINDMAP_CHILD_AUTOCOMPLETE_ZH,
    "tab_mode_generic_autocomplete_en": TAB_MODE_GENERIC_AUTOCOMPLETE_EN,
    "tab_mode_generic_autocomplete_zh": TAB_MODE_GENERIC_AUTOCOMPLETE_ZH,
}

