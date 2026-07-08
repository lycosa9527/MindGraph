"""
Case Square constants — enums aligned with the product spec.
"""

from __future__ import annotations

CASE_TYPES = frozenset({"teaching_design", "diagram_case", "diagram_template"})
CASE_STATUSES = frozenset({"pending", "approved", "rejected", "withdrawn"})
SORT_OPTIONS = frozenset(
    {
        "default",
        "hot",
        "newest",
        "oldest",
        "title_asc",
        "title_desc",
        "subject_asc",
        "subject_desc",
        "grade_asc",
        "grade_desc",
        "reviewed_newest",
        "reviewed_oldest",
    }
)
PUBLISH_SOURCES = frozenset({"self", "proxy"})

SUBJECT_ORDER = (
    "数学",
    "语文",
    "英语",
    "物理",
    "化学",
    "生物",
    "历史",
    "地理",
    "政治",
    "信息技术",
    "跨学科",
    "其他",
)

GRADE_ORDER = (
    "一年级",
    "二年级",
    "三年级",
    "四年级",
    "五年级",
    "六年级",
    "七年级",
    "八年级",
    "九年级",
    "高一",
    "高二",
    "高三",
)

SUBJECTS = frozenset(SUBJECT_ORDER)
GRADES = frozenset(GRADE_ORDER)

DIAGRAM_TYPE_LABELS = frozenset(
    {
        "circle_map",
        "bubble_map",
        "double_bubble_map",
        "brace_map",
        "tree_map",
        "flow_map",
        "multi_flow_map",
        "bridge_map",
        "mind_map",
        "mindmap",
        "concept_map",
        "combined",
    }
)

DIAGRAM_TYPE_DISPLAY = {
    "circle_map": "圆圈图",
    "bubble_map": "气泡图",
    "double_bubble_map": "双气泡图",
    "brace_map": "括号图",
    "tree_map": "树形图",
    "flow_map": "流程图",
    "multi_flow_map": "复流程图",
    "bridge_map": "桥型图",
    "mind_map": "思维导图",
    "mindmap": "思维导图",
    "concept_map": "概念图",
    "combined": "组合应用",
}

CASE_TYPE_TO_API = {
    "全部": None,
    "教学设计": "teaching_design",
    "图示案例": "diagram_case",
    "图示模板": "diagram_template",
}
