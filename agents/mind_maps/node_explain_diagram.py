"""Diagram-role lines for node explain.

Thinking maps reuse the same neighbor lists as a mind map, but the words
differ: a bubble attribute is not a branch, and a cause is not an effect.
"""

from __future__ import annotations

from typing import Dict, List, Literal, NamedTuple

PromptShell = Literal["zh", "en", "az"]

_THINKING_MAPS = frozenset(
    {
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


class ContextLabels(NamedTuple):
    """Headings for the four neighbor slots. Empty path hides that line."""

    topic: str
    branches: str
    siblings: str
    children: str
    path: str
    hide_children: bool
    hide_path: bool


def explain_diagram_key(diagram_type: str) -> str:
    """Normalize a canvas diagram type for explain prompts."""
    normalized = (diagram_type or "mindmap").strip().lower().replace("-", "_")
    if normalized == "mind_map":
        return "mindmap"
    return normalized


def _labels() -> Dict[str, Dict[str, ContextLabels]]:
    mind = {
        "zh": ContextLabels(
            "中心主题",
            "主要分支",
            "同层相关节点",
            "该节点下的子节点",
            "节点层级路径",
            False,
            False,
        ),
        "en": ContextLabels(
            "Central topic",
            "Main branches",
            "Sibling / related nodes",
            "Child nodes",
            "Node path",
            False,
            False,
        ),
        "az": ContextLabels(
            "Mərkəz mövzu",
            "Əsas budaqlar",
            "Eyni səviyyəli düyünlər",
            "Alt düyünlər",
            "Düyün yolu",
            False,
            False,
        ),
    }
    circle = {
        "zh": ContextLabels("中心词", "周围联想", "其他联想", "", "", True, True),
        "en": ContextLabels("Center word", "Associations", "Other associations", "", "", True, True),
        "az": ContextLabels("Mərkəz söz", "Assosiasiyalar", "Digər assosiasiyalar", "", "", True, True),
    }
    bubble = {
        "zh": ContextLabels("被描述的事物", "属性", "其他属性", "", "", True, True),
        "en": ContextLabels("Thing described", "Attributes", "Other attributes", "", "", True, True),
        "az": ContextLabels("Təsvir olunan", "Xüsusiyyətlər", "Digər xüsusiyyətlər", "", "", True, True),
    }
    double = {
        "zh": ContextLabels("被比较的两事物", "相同点", "同角色的其他项", "不同点", "", False, True),
        "en": ContextLabels(
            "Two things compared",
            "Similarities",
            "Other items of this role",
            "Differences",
            "",
            False,
            True,
        ),
        "az": ContextLabels("Müqayisə olunanlar", "Oxşarlıqlar", "Eyni roldan digərləri", "Fərqlər", "", False, True),
    }
    tree = {
        "zh": ContextLabels("被分类的主题", "类别", "同级", "下属项目", "上层类别", False, False),
        "en": ContextLabels(
            "Classified topic",
            "Categories",
            "Peers",
            "Items under this node",
            "Category above",
            False,
            False,
        ),
        "az": ContextLabels(
            "Təsnif mövzusu",
            "Kateqoriyalar",
            "Eyni səviyyə",
            "Alt maddələr",
            "Üst kateqoriya",
            False,
            False,
        ),
    }
    brace = {
        "zh": ContextLabels("整体", "部分", "同级部分", "子部分", "上层部分", False, False),
        "en": ContextLabels(
            "Whole",
            "Parts",
            "Peer parts",
            "Subparts",
            "Part above",
            False,
            False,
        ),
        "az": ContextLabels("Bütün", "Hissələr", "Eyni səviyyəli hissələr", "Alt hissələr", "Üst hissə", False, False),
    }
    flow = {
        "zh": ContextLabels("过程", "步骤", "同级步骤", "子步骤", "所属步骤", False, False),
        "en": ContextLabels(
            "Process",
            "Steps",
            "Peer steps",
            "Substeps",
            "Parent step",
            False,
            False,
        ),
        "az": ContextLabels(
            "Proses",
            "Addımlar",
            "Eyni səviyyəli addımlar",
            "Alt addımlar",
            "Aid olduğu addım",
            False,
            False,
        ),
    }
    multi = {
        "zh": ContextLabels("事件", "原因", "其他同类", "结果", "", False, True),
        "en": ContextLabels(
            "Event",
            "Causes",
            "Other items of this role",
            "Effects",
            "",
            False,
            True,
        ),
        "az": ContextLabels("Hadisə", "Səbəblər", "Eyni roldan digərləri", "Nəticələr", "", False, True),
    }
    bridge = {
        "zh": ContextLabels("关系因子", "类比对", "这一对的另一项", "", "", True, True),
        "en": ContextLabels(
            "Relating factor",
            "Analogy pairs",
            "The other side of this pair",
            "",
            "",
            True,
            True,
        ),
        "az": ContextLabels("Əlaqə faktoru", "Analogiya cütləri", "Bu cütün o biri tərəfi", "", "", True, True),
    }
    concept = {
        "zh": ContextLabels("焦点概念", "其他概念", "相关关系", "", "", True, True),
        "en": ContextLabels("Focus concept", "Other concepts", "Relationships", "", "", True, True),
        "az": ContextLabels("Fokus anlayış", "Digər anlayışlar", "Əlaqələr", "", "", True, True),
    }
    return {
        "mindmap": mind,
        "circle_map": circle,
        "bubble_map": bubble,
        "double_bubble_map": double,
        "tree_map": tree,
        "brace_map": brace,
        "flow_map": flow,
        "multi_flow_map": multi,
        "bridge_map": bridge,
        "concept_map": concept,
    }


_CONTEXT_LABELS = _labels()

_ROLE_CAPTIONS: Dict[PromptShell, Dict[str, str]] = {
    "zh": {
        "topic": "中心",
        "context": "联想",
        "attribute": "属性",
        "similarity": "相同点",
        "left_diff": "左侧不同点",
        "right_diff": "右侧不同点",
        "left_topic": "左侧事物",
        "right_topic": "右侧事物",
        "dimension": "维度",
        "category": "类别",
        "item": "项目",
        "whole": "整体",
        "part": "部分",
        "subpart": "子部分",
        "step": "步骤",
        "substep": "子步骤",
        "event": "事件",
        "cause": "原因",
        "effect": "结果",
        "relating_factor": "关系因子",
        "concept": "概念",
        "analogy": "类比项",
        "analogy_left": "左项",
        "analogy_right": "右项",
        "branch": "分支",
        "child": "子点",
    },
    "en": {
        "topic": "center",
        "context": "association",
        "attribute": "attribute",
        "similarity": "similarity",
        "left_diff": "left difference",
        "right_diff": "right difference",
        "left_topic": "left thing",
        "right_topic": "right thing",
        "dimension": "dimension",
        "category": "category",
        "item": "item",
        "whole": "whole",
        "part": "part",
        "subpart": "subpart",
        "step": "step",
        "substep": "substep",
        "event": "event",
        "cause": "cause",
        "effect": "effect",
        "relating_factor": "relating factor",
        "concept": "concept",
        "analogy": "analogy side",
        "analogy_left": "left side",
        "analogy_right": "right side",
        "branch": "branch",
        "child": "child",
    },
    "az": {
        "topic": "mərkəz",
        "context": "assosiasiya",
        "attribute": "xüsusiyyət",
        "similarity": "oxşarlıq",
        "left_diff": "sol fərq",
        "right_diff": "sağ fərq",
        "left_topic": "sol tərəf",
        "right_topic": "sağ tərəf",
        "dimension": "ölçü",
        "category": "kateqoriya",
        "item": "maddə",
        "whole": "bütün",
        "part": "hissə",
        "subpart": "alt hissə",
        "step": "addım",
        "substep": "alt addım",
        "event": "hadisə",
        "cause": "səbəb",
        "effect": "nəticə",
        "relating_factor": "əlaqə faktoru",
        "concept": "anlayış",
        "analogy": "analogiya tərəfi",
        "analogy_left": "sol tərəf",
        "analogy_right": "sağ tərəf",
        "branch": "budaq",
        "child": "alt düyün",
    },
}

_READING: Dict[PromptShell, Dict[str, str]] = {
    "zh": {
        "circle_map": "周围每个词都是对中心词的平级联想，用来下定义。不要叫成分支或下属。",
        "bubble_map": "周围是属性，用来描述中心事物，不是分类，也不是联想清单。不要叫成分支或子点。",
        "double_bubble_map": "比较两个事物：相同点在中间，不同点分列两侧。不要把相同点和不同点都叫成分支。",
        "tree_map": "按一个分类维度分成类别，类别下面才是项目。点明类别或项目，不要改成另一种分法。",
        "brace_map": "左边是整体，向右拆成部分和子部分。不要把部分说成放射分支。",
        "flow_map": "按先后说明这一步。同级是前后步骤，下面是子步骤。不要打乱顺序，不要说成并列分支。",
        "multi_flow_map": "原因在事件之前，结果在事件之后。不要把原因和结果都叫成分支。",
        "bridge_map": "每一对左右项遵守同一个关系因子。讲一侧时带上配对的另一侧。",
        "concept_map": "连线上的词是概念之间的关系，解释时要说出关系。不要把概念叫成思维导图的分支。",
    },
    "en": {
        "circle_map": (
            "Each surrounding word is a peer association that defines the center. Do not call them branches."
        ),
        "bubble_map": ("The ring is attributes that describe the thing, not a classification or a branch list."),
        "double_bubble_map": ("Compare two things. Similarities sit in the middle; differences sit on each side."),
        "tree_map": ("One classification dimension, then categories, then items. Do not switch dimensions."),
        "brace_map": ("The left side is the whole; parts and subparts break it down. Do not call parts branches."),
        "flow_map": (
            "Explain this step in sequence. Peers are earlier or later steps. Do not treat them as a flat list."
        ),
        "multi_flow_map": ("Causes come before the event; effects come after. Do not call both branches."),
        "bridge_map": "Each pair follows the relating factor. Name the other side of the pair.",
        "concept_map": (
            "The words on the links are the relationships. Say the relationship. Do not call concepts branches."
        ),
    },
    "az": {
        "circle_map": "Ətraf sözlər mərkəzi müəyyən edən bərabər assosiasiyalardır. Onlara budaq deməyin.",
        "bubble_map": "Ətraf xüsusiyyətlərdir, budaq siyahısı deyil.",
        "double_bubble_map": "İki şeyi müqayisə edin: oxşarlıq ortada, fərqlər yanlarda.",
        "tree_map": "Bir təsnif ölçüsü, sonra kateqoriya, sonra maddə.",
        "brace_map": "Sol bütün, sağa hissələr. Hissələrə budaq deməyin.",
        "flow_map": "Bu addımı ardıcıllıqla izah edin. Eyni səviyyə əvvəl və ya sonrakı addımdır.",
        "multi_flow_map": "Səbəb hadisədən əvvəl, nəticə sonra gəlir.",
        "bridge_map": "Hər cüt eyni əlaqə faktoruna tabedir. Cütün o biri tərəfini də deyin.",
        "concept_map": "Xəttin üzərindəki söz əlaqədir. Anlayışa budaq deməyin.",
    },
}

_OVERRIDE: Dict[PromptShell, str] = {
    "zh": "若与后文“不要讲层级”冲突，以这里的角色为准。",
    "en": "If this conflicts with “do not lecture on hierarchy”, follow this role.",
    "az": "İerarxiya qadağası ilə ziddiyyət varsa, bu rol əsasdır.",
}


def context_labels(diagram_type: str, shell: PromptShell) -> ContextLabels:
    """Headings for this diagram. Unknown types keep mind-map headings."""
    table = _CONTEXT_LABELS.get(explain_diagram_key(diagram_type), _CONTEXT_LABELS["mindmap"])
    return table[shell]


def role_caption(node_role: str, shell: PromptShell) -> str:
    """Short role name, or empty when the canvas did not send one."""
    key = (node_role or "").strip().lower().replace("-", "_")
    if not key:
        return ""
    return _ROLE_CAPTIONS[shell].get(key, "")


def diagram_reading_line(diagram_type: str, shell: PromptShell) -> str:
    """One line that tells the model how this thinking map uses a node."""
    key = explain_diagram_key(diagram_type)
    if key not in _THINKING_MAPS:
        return ""
    reading = _READING[shell].get(key, "")
    if not reading:
        return ""
    return f"{reading}{_OVERRIDE[shell]}"


def selected_label(node_label: str, node_role: str, shell: PromptShell, diagram_type: str) -> str:
    """Append the role caption on thinking maps."""
    caption = role_caption(node_role, shell)
    if not caption or explain_diagram_key(diagram_type) not in _THINKING_MAPS:
        return node_label
    if shell == "zh":
        return f"{node_label}（{caption}）"
    return f"{node_label} ({caption})"


def path_line(path: List[str], shell: PromptShell, heading: str) -> str:
    """One path line, or empty when there is no ancestor."""
    if not path or not heading:
        return ""
    joined = " → ".join(path)
    if shell == "zh":
        return f"- {heading}：{joined}\n"
    if shell == "az":
        return f"- {heading}: {joined}\n"
    return f"- {heading}: {joined}\n"
