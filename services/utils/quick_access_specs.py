"""Built-in and per-user diagram specs for the quick-access inspiration prompts."""

from __future__ import annotations

import json
from typing import Any

QUICK_ACCESS_SPEC_KEYS = frozenset(
    {
        "landing.international.example1",
        "landing.international.example2",
        "landing.international.example3",
        "landing.international.example4",
        "landing.international.example5",
        "landing.international.example6",
    }
)
QUICK_ACCESS_SPEC_DIAGRAM_TYPES = frozenset(
    {
        "bubble_map",
        "bridge_map",
        "tree_map",
        "circle_map",
        "double_bubble_map",
        "flow_map",
        "brace_map",
        "multi_flow_map",
        "concept_map",
        "mindmap",
        "mind_map",
        "diagram",
    }
)
QUICK_ACCESS_SPEC_TEXT_MAX = 10000
QUICK_ACCESS_SPEC_JSON_MAX = 200_000

_MINDMAP_STYLE = {"_mindmap_theme": "rainbow", "_mindmap_diagram_style": "classic"}


def _branch(label: str, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    nodes = children or []
    return {"label": label, "text": label, "children": nodes}


def _leaf(label: str) -> dict[str, Any]:
    return _branch(label, [])


# The six landing prompts, ready to open without another model call.
DEFAULT_QUICK_ACCESS_SPECS: dict[str, dict[str, Any]] = {
    "landing.international.example1": {
        "diagramType": "mindmap",
        "spec": {
            **_MINDMAP_STYLE,
            "topic": "光合作用",
            "children": [
                _branch("场所与原料", [_leaf("叶绿体"), _leaf("二氧化碳"), _leaf("水")]),
                _branch("条件", [_leaf("光"), _leaf("叶绿素")]),
                _branch("产物", [_leaf("葡萄糖"), _leaf("氧气")]),
                _branch("意义", [_leaf("储存能量"), _leaf("维持大气含氧量")]),
            ],
        },
    },
    "landing.international.example2": {
        "diagramType": "tree_map",
        "spec": {
            "topic": "脊椎动物",
            "dimension": "按类群",
            "alternative_dimensions": [],
            "children": [
                {"text": "鱼类", "children": [{"text": "用鳃呼吸", "children": []}]},
                {"text": "两栖类", "children": [{"text": "幼体水生", "children": []}]},
                {"text": "爬行类", "children": [{"text": "体表有鳞", "children": []}]},
                {"text": "哺乳类", "children": [{"text": "胎生哺乳", "children": []}]},
            ],
        },
    },
    "landing.international.example3": {
        "diagramType": "flow_map",
        "spec": {
            "title": "测量物体密度",
            "steps": ["称质量", "量体积", "计算", "记录结论"],
            "substeps": [
                {"step": "称质量", "substeps": ["天平调平", "读出示数"]},
                {"step": "量体积", "substeps": ["量筒读数", "记下体积"]},
                {"step": "计算", "substeps": ["密度 = 质量 / 体积"]},
                {"step": "记录结论", "substeps": ["写出单位", "比较常见物质"]},
            ],
        },
    },
    "landing.international.example4": {
        "diagramType": "double_bubble_map",
        "spec": {
            "left": "植物细胞",
            "right": "动物细胞",
            "similarities": ["细胞膜", "细胞核", "细胞质"],
            "left_differences": ["细胞壁", "叶绿体", "大液泡"],
            "right_differences": ["中心体", "无细胞壁", "无叶绿体"],
        },
    },
    "landing.international.example5": {
        "diagramType": "brace_map",
        "spec": {
            "whole": "一元二次方程",
            "dimension": "组成部分",
            "parts": [
                {"name": "标准式", "subparts": [{"name": "ax² + bx + c = 0"}]},
                {"name": "判别式", "subparts": [{"name": "Δ = b² - 4ac"}]},
                {"name": "求根公式", "subparts": [{"name": "x = (-b ± √Δ) / 2a"}]},
                {"name": "图像与根", "subparts": [{"name": "抛物线与 x 轴交点"}]},
            ],
        },
    },
    "landing.international.example6": {
        "diagramType": "bubble_map",
        "spec": {
            "topic": "牛顿三大定律",
            "attributes": ["惯性定律", "F = ma", "作用力与反作用力", "适用于宏观低速"],
        },
    },
}


def _spec_json_size(spec: dict[str, Any]) -> int:
    return len(json.dumps(spec, ensure_ascii=False))


def clean_quick_access_saved_specs(value: object) -> dict[str, dict[str, Any]]:
    """Keep one saved diagram per inspiration key. Incomplete entries are dropped."""
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, dict[str, Any]] = {}
    for key, entry in value.items():
        if not isinstance(key, str) or key not in QUICK_ACCESS_SPEC_KEYS:
            continue
        if not isinstance(entry, dict):
            continue
        text = entry.get("text")
        diagram_type = entry.get("diagramType")
        spec = entry.get("spec")
        if not isinstance(text, str) or not isinstance(diagram_type, str) or not isinstance(spec, dict):
            continue
        stripped = text.strip()[:QUICK_ACCESS_SPEC_TEXT_MAX]
        if not stripped or diagram_type not in QUICK_ACCESS_SPEC_DIAGRAM_TYPES or not spec:
            continue
        if _spec_json_size(spec) > QUICK_ACCESS_SPEC_JSON_MAX:
            continue
        cleaned[key] = {"text": stripped, "diagramType": diagram_type, "spec": spec}
    return cleaned


def default_quick_access_specs() -> dict[str, dict[str, Any]]:
    """Copy of the built-in specs so callers cannot mutate the module table."""
    return json.loads(json.dumps(DEFAULT_QUICK_ACCESS_SPECS))
