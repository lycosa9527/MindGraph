"""
Canonical diagram-type slugs and aliases for Kitty voice routing (desktop canvas open).

Kept aligned with ``frontend/src/composables/canvasPage/diagramTypeMaps.ts`` VALID_DIAGRAM_TYPES.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Dict, FrozenSet, Optional

# Slugs accepted by SPA ``/canvas?type=...``
KITTY_CANONICAL_DIAGRAM_TYPES: FrozenSet[str] = frozenset(
    {
        "circle_map",
        "bubble_map",
        "double_bubble_map",
        "tree_map",
        "brace_map",
        "flow_map",
        "multi_flow_map",
        "bridge_map",
        "mindmap",
        "mind_map",
        "concept_map",
    }
)

# Lowercase keys (English phrases / snake_case variants) plus Chinese labels → slug
_KITTY_DIAGRAM_ALIAS_TO_SLUG: Dict[str, str] = {}
for _slug in sorted(KITTY_CANONICAL_DIAGRAM_TYPES):
    _KITTY_DIAGRAM_ALIAS_TO_SLUG[_slug] = _slug
    _KITTY_DIAGRAM_ALIAS_TO_SLUG[_slug.replace("_", " ")] = _slug

_ZH_ALIAS: Dict[str, str] = {
    "圆圈图": "circle_map",
    "圆圈": "circle_map",
    "气泡图": "bubble_map",
    "气泡": "bubble_map",
    "双气泡图": "double_bubble_map",
    "双气泡": "double_bubble_map",
    "树形图": "tree_map",
    "树图": "tree_map",
    "括号图": "brace_map",
    "括号": "brace_map",
    "流程图": "flow_map",
    "流程": "flow_map",
    "复流程图": "multi_flow_map",
    "复流程": "multi_flow_map",
    "多重流程图": "multi_flow_map",
    "桥形图": "bridge_map",
    "桥图": "bridge_map",
    "类比图": "bridge_map",
    "思维导图": "mindmap",
    "概念图": "concept_map",
}
for _cn, _sl in list(_ZH_ALIAS.items()):
    _KITTY_DIAGRAM_ALIAS_TO_SLUG[_cn] = _sl

_EN_EXTRA: Dict[str, str] = {
    "circle map": "circle_map",
    "bubble map": "bubble_map",
    "double bubble map": "double_bubble_map",
    "bubble map comparing": "double_bubble_map",
    "comparison map": "double_bubble_map",
    "tree map": "tree_map",
    "brace map": "brace_map",
    "bracemap": "brace_map",
    "flow map": "flow_map",
    "multi-flow map": "multi_flow_map",
    "multi flow map": "multi_flow_map",
    "bridge map": "bridge_map",
    "mind map": "mind_map",
    "mind-map": "mind_map",
}
for _lk, _sl in _EN_EXTRA.items():
    _KITTY_DIAGRAM_ALIAS_TO_SLUG[_lk.lower()] = _sl


KITTY_DIAGRAM_CATALOG_PROMPT = """
【MindGraph diagram_type slugs (use EXACT slug in JSON field diagram_type）】
- circle_map — Circle map; nodes: contexts / 上下文 surrounding the topic
- bubble_map — Bubble map; nodes: attributes / 形容词、特征
- double_bubble_map — Double bubble comparing two topics; nodes: similarities, left_differences,
  right_differences / 共同点、左边不同点、右边不同点
- tree_map — Tree map classification; categories and items / 类别、项目
- brace_map — Brace map part-whole; parts and subparts / 部分、子部分
- flow_map — Flow map sequencing; steps and substeps / 步骤、子步骤
- multi_flow_map — Multi-flow causes and effects; causes, effects / 原因、结果
- bridge_map — Bridge map analogies; pairs (left-right) tied by a relating dimension / 类比对、关系维度
- mindmap OR mind_map — Mind map branches and children / 分支、子项
- concept_map — Concept map; concepts and labeled relationships / 概念、命题关系

【Unsupported / in development】Do NOT call open_desktop_canvas for: fishbone (鱼骨图), org chart,
Gantt, Venn, SWOT, or other slugs not listed above. They are not available yet — suggest mind map,
flow map, or bubble map as alternatives.


【Desktop canvas open intent】When the user wants the COMPUTER/desktop app (电脑、桌面、PC、浏览器画布)
to open or switch to a **new blank** diagram of a given type (especially when no diagram is open
on the phone or they ask to work on the big screen), return:
{"action":"open_desktop_canvas","diagram_type":"<slug>","target":"<optional main title>",
 "left":"<optional left topic double bubble>","right":"<optional right topic double bubble>",
 "confidence":0.9}
- Put the primary title in "target" when there is a single center/title (not for double_bubble_map
  unless you also fill left/right).
- For double_bubble_map comparisons, fill "left" and "right" with the two compared subjects;
  you may omit "target".
Examples:
- 「在电脑上打开一个气泡图」→
  {"action":"open_desktop_canvas","diagram_type":"bubble_map","confidence":0.92}
- 「帮我在桌面新建思维导图，主题是运动会」→
  {"action":"open_desktop_canvas","diagram_type":"mindmap","target":"运动会","confidence":0.92}
- 「Open a flow map on my computer titled Photosynthesis」→
  {"action":"open_desktop_canvas","diagram_type":"flow_map","target":"Photosynthesis","confidence":0.9}
- 「在电脑开双气泡图比较苹果和梨」→
  {"action":"open_desktop_canvas","diagram_type":"double_bubble_map","left":"苹果","right":"梨",
   "confidence":0.9}
"""


KITTY_VOICE_COMMAND_PROMPT = """
【Diagram edit & UI tools — call the matching function when the user wants a canvas change】
- update_center — change topic/title/center (e.g. 「主题是运动会」, 「change topic to Cars」)
- add_node — add one node (text required; optional 0-based position)
- update_node — change an existing node's text (node_identifier + new_text)
- delete_node — remove a node (node_identifier: index label like 第一个 / node text / id)
- select_node — highlight a node on canvas
- auto_complete — AI fill the whole diagram (needs a valid center/topic first)
- start_inline_recommendations — Tab-style inline suggestions for ONE node
  (联想/推荐/建议/suggestions for this node; omit node_identifier if a node is already selected)
- add_node_with_recommendations — add ONE node, then open inline suggestions to pick a label
  (e.g. 「增加一个节点并给出一些建议」; optional text placeholder; user chooses from suggestions)
- explain_node — open MindMate to explain a node concept (解释/讲解 + node reference)
- ask_mindmate — send a free-form question to MindMate panel (message required)
- open_panel / close_panel — mindmate or node_palette

Node reference tips:
- Prefer node text or spoken index (第一个, second, 2) in node_identifier.
- When the user says「这个节点/当前节点/选中的节点」, omit node_identifier (uses selected_nodes).
Examples:
- 「添加节点 光合作用」→ add_node(text="光合作用")
- 「删除第二个节点」→ delete_node(node_identifier="第二个")
- 「把第一个改成 发动机」→ update_node(node_identifier="第一个", new_text="发动机")
- 「自动补全」→ auto_complete()
- 「给这个节点一些建议」→ start_inline_recommendations()
- 「增加一个节点并给出一些建议」→ add_node_with_recommendations()
- 「解释一下第一个节点」→ explain_node(node_identifier="第一个")
- 「帮我问一下 MindMate 什么是光合作用」→ ask_mindmate(message="什么是光合作用")
"""


def normalize_voice_desktop_canvas_diagram_type(raw: Optional[str]) -> Optional[str]:
    """Map LLM or user-facing label to a canonical slug, or None if unknown."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    if text in KITTY_CANONICAL_DIAGRAM_TYPES:
        return text
    zh = _ZH_ALIAS.get(text)
    if zh:
        return zh
    lowered = text.lower().replace("-", "_")
    by_snake = _KITTY_DIAGRAM_ALIAS_TO_SLUG.get(lowered)
    if by_snake:
        return by_snake
    spaced = text.lower().replace("_", " ")
    return _KITTY_DIAGRAM_ALIAS_TO_SLUG.get(spaced)


def coerce_open_desktop_payload_diagram_slug(payload: Dict[str, object]) -> Optional[str]:
    """Resolve diagram slug from enqueue payload dict (mutates canonical ``diagram_type``)."""
    raw_dt = payload.get("diagram_type")
    slug = normalize_voice_desktop_canvas_diagram_type(raw_dt if isinstance(raw_dt, str) else None)
    if slug is None:
        return None
    payload["diagram_type"] = slug
    return slug
