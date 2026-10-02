"""Diagram-type briefs for 思维讲堂.

Audience, familiarity, tone, and tour scope stay listener settings.
This axis says what the diagram is for and what each node role is called.
"""

from __future__ import annotations

from typing import Any

from services.diagram.thinking_map_patterns import normalize_diagram_type

DIAGRAM_PROMPT_IDS = frozenset(
    {
        "mind_map",
        "circle_map",
        "bubble_map",
        "double_bubble_map",
        "tree_map",
        "brace_map",
        "flow_map",
        "multi_flow_map",
        "bridge_map",
        "concept_map",
    }
)

_LABELS = {
    "mind_map": {"zh": "思维导图", "en": "Mind map"},
    "circle_map": {"zh": "圆圈图", "en": "Circle map"},
    "bubble_map": {"zh": "气泡图", "en": "Bubble map"},
    "double_bubble_map": {"zh": "双气泡图", "en": "Double bubble map"},
    "tree_map": {"zh": "树形图", "en": "Tree map"},
    "brace_map": {"zh": "括号图", "en": "Brace map"},
    "flow_map": {"zh": "流程图", "en": "Flow map"},
    "multi_flow_map": {"zh": "复流程图", "en": "Multi-flow map"},
    "bridge_map": {"zh": "桥形图", "en": "Bridge map"},
    "concept_map": {"zh": "概念图", "en": "Concept map"},
}

# Thinking focus + the only legal names for nodes[].role.
_BRIEFS_ZH = {
    "mind_map": (
        "图示：思维导图。思维焦点是把一个主题放射展开再收拢。"
        "topic=中心主题；branch=一级分支；child=分支下的子点。"
        "overview 点名主题和一级分支。branch 步讲这一支在整体里的位置，子点留在该支里。"
        "closing 收成能复述的骨架。可以称「分支」「子点」。"
    ),
    "circle_map": (
        "图示：圆圈图。思维焦点是在情境里给中心词下定义：周围每个词都是对中心的联想，彼此平级。"
        "topic=中心词；context=联想。没有上下级，没有「下属」。"
        "overview 点名中心词，再点出周围联想是从哪些角度打开的。"
        "每个 context 步只讲这一条联想如何帮助定义中心词，不要说「第几支」「它下面还有」。"
        "closing 收成：这些联想一起把中心词放在什么情境里。不要收成树状骨架。"
    ),
    "bubble_map": (
        "图示：气泡图。思维焦点是用属性描述中心事物，不是分类，也不是联想清单。"
        "topic=被描述的事物；attribute=属性。"
        "overview 点名事物，并说明周围是它的属性。"
        "每个 attribute 步讲这条属性如何描述事物。不要把属性叫成分支或子点。"
        "closing 用几条属性收成一句描述。"
    ),
    "double_bubble_map": (
        "图示：双气泡图。思维焦点是比较两个事物：相同点在中间，不同点分列两侧。"
        "left_topic / right_topic=两个被比较的事物；similarity=相同点；"
        "left_diff=左侧不同点；right_diff=右侧不同点。"
        "overview 必须同时点名左右两事物。"
        "相同点步讲两者共有什么；不同点步讲这一侧独有什么，并对照另一侧。"
        "不要把相同点和不同点混叫成普通分支。closing 收成一句比较结论。"
    ),
    "tree_map": (
        "图示：树形图。思维焦点是按同一个分类维度把主题分成类别，类别下才是项目。"
        "topic=被分类的主题；dimension=分类维度；category=类别；item=类别下的项目。"
        "overview 先说出分类维度，再点类别。不要混用别的维度。"
        "category 步讲这一类为什么属于该维度；item 只作为该类的例子，不要升成新类别。"
        "closing 收回这个维度，不要改口换成另一种分法。"
    ),
    "brace_map": (
        "图示：括号图。思维焦点是整体与部分：左边是整体，向右拆成部分和子部分。"
        "whole=整体；dimension=拆分维度；part=部分；subpart=子部分。"
        "overview 点名整体和拆分维度。part 步讲这一部分如何组成整体。"
        "不要把部分说成主题的放射分支。closing 把部分收回整体。"
    ),
    "flow_map": (
        "图示：流程图。思维焦点是顺序：先发生什么，后发生什么。"
        "topic=过程主题；step=步骤；substep=子步骤。"
        "overview 点名过程，并按顺序点出步骤，不要打乱先后。"
        "step 步讲这一步为何接在上一步之后。substep 只解释所属步骤，不要变成新的主步骤。"
        "closing 按顺序收成过程，不要收成并列分支。"
    ),
    "multi_flow_map": (
        "图示：复流程图。思维焦点是一件事的原因和结果。"
        "event=事件；cause=原因；effect=结果。"
        "overview 点名事件。先讲原因，再讲结果。原因在事件之前，结果在事件之后。"
        "不要把原因和结果都叫成分支。closing 收成：哪些原因带来这件事，这件事又造成哪些结果。"
    ),
    "bridge_map": (
        "图示：桥形图。思维焦点是类比：每一对左右节点遵守同一个关系因子。"
        "relating_factor=关系因子；analogy_left=类比对的左项；analogy_right=类比对的右项。"
        "overview 先说出关系因子，再说明每一对都是「左项 之于 右项」。"
        "讲一对时必须同时点左右两项，不要拆成互不相关的分支。"
        "closing 用关系因子收成类比规律。"
    ),
    "concept_map": (
        "图示：概念图。思维焦点是概念之间的关系，连线本身有意义。"
        "topic=焦点概念；concept=其他概念。nodes[].relation 是连到该概念的关系词，有则必须念出来。"
        "overview 点名焦点概念和它连向的概念。"
        "concept 步讲关系词，不要把连线说成无标签的分支。"
        "closing 收成这张概念网，而不是层级大纲。"
    ),
}

_BRIEFS_EN = {
    "mind_map": (
        "Diagram: mind map. Focus: radiate a topic into branches, then gather them. "
        "topic = central topic; branch = first-level branch; child = child of a branch. "
        "Overview names the topic and first-level branches. A branch step places that branch; "
        "children stay inside it. Closing is a retellable skeleton. “Branch” and “child” are allowed."
    ),
    "circle_map": (
        "Diagram: circle map. Focus: define the center in context. Each surrounding word is a peer association. "
        "topic = center; context = association. There is no parent/child hierarchy. "
        "Overview names the center and the angles of association. "
        "Each context step says how that association defines the center. "
        "Do not say “branch N” or “it has children under it”. "
        "Closing states the context these associations place the center in."
    ),
    "bubble_map": (
        "Diagram: bubble map. Focus: describe a thing by its attributes, not by classifying or free-associating. "
        "topic = the thing; attribute = attribute. "
        "Overview names the thing and says the ring is attributes. "
        "Each attribute step says how it describes the thing. Do not call attributes branches. "
        "Closing gathers the attributes into one description."
    ),
    "double_bubble_map": (
        "Diagram: double bubble map. Focus: compare two things. Similarities sit in the middle; "
        "differences sit on each side. "
        "left_topic / right_topic = the two things; similarity = shared trait; "
        "left_diff / right_diff = a difference on that side. "
        "Overview must name both things. A similarity step says what they share. "
        "A difference step says what is unique on that side and contrasts the other. "
        "Closing is one comparison sentence."
    ),
    "tree_map": (
        "Diagram: tree map. Focus: classify the topic on one dimension. Categories sit under the topic; "
        "items sit under a category. "
        "topic = classified topic; dimension = classification dimension; category = category; item = item. "
        "Overview names the dimension, then the categories. Do not mix dimensions. "
        "A category step says why it belongs to that dimension. Items stay examples of that category. "
        "Closing stays on this dimension."
    ),
    "brace_map": (
        "Diagram: brace map. Focus: whole and parts. "
        "whole = the whole; dimension = how it is split; part = part; subpart = subpart. "
        "Overview names the whole and the split. A part step says how that part makes the whole. "
        "Do not call parts radiating branches. Closing returns the parts to the whole."
    ),
    "flow_map": (
        "Diagram: flow map. Focus: sequence. "
        "topic = the process; step = step; substep = substep. "
        "Overview names the process and the steps in order. "
        "A step step says why it follows the previous one. A substep explains its step only. "
        "Closing retells the process in order, not as a list of peer branches."
    ),
    "multi_flow_map": (
        "Diagram: multi-flow map. Focus: causes and effects of one event. "
        "event = event; cause = cause; effect = effect. "
        "Overview names the event. Teach causes before effects. "
        "Do not call both “branches”. "
        "Closing states which causes lead to the event and which effects follow it."
    ),
    "bridge_map": (
        "Diagram: bridge map. Focus: analogy under one relating factor. "
        "relating_factor = the factor; analogy_left / analogy_right = the two sides of a pair. "
        "Overview names the factor, then each pair as “left as to right”. "
        "A pair must be spoken as both sides. Closing states the analogy rule."
    ),
    "concept_map": (
        "Diagram: concept map. Focus: relationships between concepts. The link label is content. "
        "topic = focus concept; concept = another concept. "
        "nodes[].relation, when present, is the link label and must be spoken. "
        "Overview names the focus concept and what it links to. "
        "A concept step teaches the relationship, not an unlabeled branch. "
        "Closing gathers the concept web."
    ),
}


def normalize_lecture_diagram(raw: Any) -> str:
    """Return a known lecture diagram id. Unknown values use mind_map."""
    slug = normalize_diagram_type(str(raw or ""))
    if slug == "mindmap":
        slug = "mind_map"
    if slug in DIAGRAM_PROMPT_IDS:
        return slug
    return "mind_map"


def diagram_label(diagram_type: str, language: str) -> str:
    """UI label for a lecture diagram id."""
    lang = "zh" if str(language or "zh").startswith("zh") else "en"
    return _LABELS[normalize_lecture_diagram(diagram_type)][lang]


def diagram_brief(diagram_type: str, language: str) -> str:
    """Instruction block: thinking focus and legal node-role names."""
    key = normalize_lecture_diagram(diagram_type)
    if str(language or "zh").startswith("zh"):
        return _BRIEFS_ZH[key]
    return _BRIEFS_EN[key]


def diagram_pref_fields(settings: dict[str, Any] | None) -> dict[str, str]:
    """Diagram axis embedded beside the listener briefs."""
    raw = settings if isinstance(settings, dict) else {}
    language = str(raw.get("language") or "zh")
    diagram_type = normalize_lecture_diagram(raw.get("diagram_type"))
    return {
        "diagram_type": diagram_type,
        "diagram_label": diagram_label(diagram_type, language),
        "diagram_brief": diagram_brief(diagram_type, language),
    }


def with_diagram_type(settings: dict[str, Any] | None, spec: Any) -> dict[str, Any]:
    """Copy launch settings and fill diagram_type from the spec when missing."""
    merged = dict(settings or {})
    if str(merged.get("diagram_type") or "").strip():
        return merged
    if isinstance(spec, dict):
        raw = spec.get("type") or spec.get("diagramType") or spec.get("diagram_type") or ""
        if str(raw).strip():
            merged["diagram_type"] = raw
    return merged
