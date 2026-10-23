"""Semantic diagram fixtures for the Act 02 hybrid montage (Chinese labels)."""

from __future__ import annotations

from typing import Any, TypedDict


class PromoDiagram(TypedDict):
    """One exported still for the promo montage."""

    slug: str
    diagram_type: str
    data: dict[str, Any]
    label_zh: str


PROMO_DIAGRAMS: tuple[PromoDiagram, ...] = (
    {
        "slug": "01-circle_map",
        "diagram_type": "circle_map",
        "label_zh": "圆圈图",
        "data": {
            "topic": "光合作用",
            "context": ["阳光", "水", "二氧化碳", "叶绿体"],
        },
    },
    {
        "slug": "02-bubble_map",
        "diagram_type": "bubble_map",
        "label_zh": "气泡图",
        "data": {
            "topic": "主题",
            "attributes": ["定义", "特征", "例子"],
        },
    },
    {
        "slug": "03-double_bubble_map",
        "diagram_type": "double_bubble_map",
        "label_zh": "双气泡图",
        "data": {
            "left": "班级规模",
            "right": "课堂互动",
            "similarities": ["相似点"],
            "left_differences": ["不同点A"],
            "right_differences": ["不同点B"],
        },
    },
    {
        "slug": "04-tree_map",
        "diagram_type": "tree_map",
        "label_zh": "树形图",
        "data": {
            "topic": "动物",
            "children": [
                {"text": "哺乳动物", "children": []},
                {"text": "鸟类", "children": []},
                {"text": "鱼类", "children": []},
            ],
        },
    },
    {
        "slug": "05-brace_map",
        "diagram_type": "brace_map",
        "label_zh": "括号图",
        "data": {
            "whole": "电脑",
            "parts": [
                {"name": "显示器", "subparts": []},
                {"name": "主机", "subparts": []},
                {"name": "键盘", "subparts": []},
            ],
        },
    },
    {
        "slug": "06-flow_map",
        "diagram_type": "flow_map",
        "label_zh": "流程图",
        "data": {
            "title": "流程",
            "steps": ["输入", "处理", "输出"],
        },
    },
    {
        "slug": "07-multi_flow_map",
        "diagram_type": "multi_flow_map",
        "label_zh": "复流程图",
        "data": {
            "event": "下雨",
            "causes": ["云层聚集"],
            "effects": ["地面湿润"],
        },
    },
    {
        "slug": "08-bridge_map",
        "diagram_type": "bridge_map",
        "label_zh": "桥形图",
        "data": {
            "relating_factor": "如同",
            "analogies": [
                {"left": "火车", "right": "高铁", "id": "a1"},
                {"left": "书信", "right": "电子邮件", "id": "a2"},
            ],
        },
    },
    {
        "slug": "09-mindmap",
        "diagram_type": "mindmap",
        "label_zh": "思维导图",
        "data": {
            "topic": "教学设计",
            "children": [
                {"id": "b1", "label": "目标", "children": []},
                {"id": "b2", "label": "活动", "children": []},
                {"id": "b3", "label": "评价", "children": []},
            ],
        },
    },
    {
        "slug": "10-concept_map",
        "diagram_type": "concept_map",
        "label_zh": "概念图",
        "data": {
            "topic": "细胞",
            "focus_question": "细胞的结构",
            "concepts": ["细胞膜", "细胞核"],
            "relationships": [
                {"from": "细胞", "to": "细胞膜", "label": "包含"},
                {"from": "细胞", "to": "细胞核", "label": "包含"},
            ],
        },
    },
)
