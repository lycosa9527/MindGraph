"""Vision prompt: name a photographed diagram and copy its node text.

Used by the canvas image / hand-drawn import. The call does not go through
``get_prompt``, so the generation language footer is not appended. Labels must
stay as written on the image.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

VISION_DIAGRAM_PROMPT_ZH = """看这张图，判断它是哪一种图，并原样抄下图上所有可见文字。不要翻译，不要发明图上没有的节点，不需要坐标。

只能从这些类型里选一个 diagram_type：
- circle_map：一个中心，周围一圈上下文，没有分支层级
- bubble_map：一个中心，周围是描述它的属性气泡
- double_bubble_map：左右两个主题，中间是相同点，两侧是各自的不同点
- tree_map：一个主题，下面是分类，分类下是条目
- brace_map：一个整体，用大括号拆成部分
- flow_map：一条步骤链，步骤上可以有子步骤
- multi_flow_map：中间一个事件，左边原因，右边结果
- bridge_map：成对的类比
- mindmap：一个中心，向四周伸出多层分支
- concept_map：多个概念，连线上有关系词

若看不出是上面任何一种图，diagram_type 设为 null，spec 设为 null。

只输出 JSON：
{
  "diagram_type": "上面之一或 null",
  "confidence": 0.0,
  "reason": "只用布局说明，不要复述节点",
  "spec": {}
}

spec 按类型填写，文字必须来自图上：
- circle_map: {"topic":"","context":[""]}
- bubble_map: {"topic":"","attributes":[""]}
- double_bubble_map: {"left":"","right":"","similarities":[""],"left_differences":[""],"right_differences":[""]}
- tree_map: {"topic":"","children":[{"text":"","children":[{"text":""}]}]}
- brace_map: {"whole":"","parts":[{"name":"","subparts":[{"name":""}]}]}
- flow_map: {"title":"","steps":[{"text":"","substeps":[""]}]}
- multi_flow_map: {"event":"","causes":[""],"effects":[""]}
- bridge_map: {"relating_factor":"","pairs":[{"left":"","right":""}]}
- mindmap: {"topic":"","children":[{"text":"","children":[{"text":""}]}]}
- concept_map: {"topic":"","concepts":[""],"relationships":[{"from":"","to":"","label":""}]}

规则：
- 只输出 JSON，不要用代码块包裹。
- 难以辨认的字用 "?"，不要臆造长文。
- 节点数量以图为准，不要补到固定个数。
- confidence 仅在类型和文字都清楚时 >= 0.55。"""

VISION_DIAGRAM_PROMPT_EN = """Look at this image. Name the diagram type and copy every visible label exactly. Do not translate. Do not invent nodes that are not drawn. Positions are not needed.

diagram_type must be one of:
- circle_map: one center, a ring of context items, no branch hierarchy
- bubble_map: one center, surrounding attribute bubbles
- double_bubble_map: two topics, shared points in the middle, differences on each side
- tree_map: one topic, categories under it, items under each category
- brace_map: one whole broken into parts by a brace
- flow_map: a chain of steps; a step may have substeps
- multi_flow_map: one event in the center, causes on the left, effects on the right
- bridge_map: analogy pairs
- mindmap: one center with nested branches
- concept_map: concepts joined by labeled relationships

If it is none of these, set diagram_type to null and spec to null.

Output JSON only:
{
  "diagram_type": "one of the types above, or null",
  "confidence": 0.0,
  "reason": "layout only, do not repeat the node text",
  "spec": {}
}

Fill spec for that type. Text must come from the image:
- circle_map: {"topic":"","context":[""]}
- bubble_map: {"topic":"","attributes":[""]}
- double_bubble_map: {"left":"","right":"","similarities":[""],"left_differences":[""],"right_differences":[""]}
- tree_map: {"topic":"","children":[{"text":"","children":[{"text":""}]}]}
- brace_map: {"whole":"","parts":[{"name":"","subparts":[{"name":""}]}]}
- flow_map: {"title":"","steps":[{"text":"","substeps":[""]}]}
- multi_flow_map: {"event":"","causes":[""],"effects":[""]}
- bridge_map: {"relating_factor":"","pairs":[{"left":"","right":""}]}
- mindmap: {"topic":"","children":[{"text":"","children":[{"text":""}]}]}
- concept_map: {"topic":"","concepts":[""],"relationships":[{"from":"","to":"","label":""}]}

Rules:
- JSON only. No markdown fences.
- Use "?" for an illegible word. Do not guess a long phrase.
- Keep the node count shown in the drawing. Do not pad to a fixed number.
- confidence >= 0.55 only when both the type and the text are clear."""
