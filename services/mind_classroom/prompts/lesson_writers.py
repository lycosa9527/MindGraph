"""Per-diagram lesson writers for 思维讲堂.

Overview, a single step, and closing are separate instructions.
Canvas tour and the slide planner call the writer for the diagram on the canvas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from services.mind_classroom.prompts.diagram_prompts import normalize_lecture_diagram


@dataclass(frozen=True)
class LessonParts:
    """Opening, one step, and closing for a single diagram type."""

    overview: str
    step: str
    closing: str
    focus: str
    scope_main: str
    scope_each: str
    planner_open: str
    planner_develop: str
    planner_close: str


def _zh(language: str) -> bool:
    return str(language or "zh").startswith("zh")


def mind_map_writer(language: str) -> LessonParts:
    """Mind map: radiate a topic into branches, then gather them."""
    if _zh(language):
        return LessonParts(
            overview="开场点名中心主题，并按 place 报出一级分支，不展开子点。",
            step="这一步是一级分支。讲它在整体中的位置；子点留在本步 caption 里，不要另起一步。",
            closing="收成可复述的骨架：主题加上一级分支。不要新知识点。",
            focus="overview / closing 的 focus_node_ids 必须是主题 id 加全部一级分支 id，不要只用主题 id。",
            scope_main="一步对应一个一级分支；子点不拆步。支末不要预告下一支。",
            scope_each="stop=trunk 只定调并说明子点如何挂上；stop=leaf 只讲本节点，用 parent_text / sibling_texts。",
            planner_open="开场只问主题为何要分成这些分支，点名一级分支，不讲子点。",
            planner_develop="先 branch_intro，再按 children 顺序 child_detail。这是思维导图的分支，可以称子点。",
            planner_close="收成主题与一级分支的骨架，不要改成别的图示。",
        )
    return LessonParts(
        overview="Opening names the topic and first-level branches by place. Do not unpack children.",
        step="This step is one first-level branch. Place it in the whole; keep children in this caption.",
        closing="Close as a retellable skeleton: topic plus first-level branches. No new facts.",
        focus="Overview and closing focus_node_ids are the topic id plus every first-level branch id.",
        scope_main="One step per first-level branch; do not split children into steps.",
        scope_each=(
            "stop=trunk frames how children hang on; stop=leaf is this node only, using parent_text / sibling_texts."
        ),
        planner_open="Opening asks why the topic splits into these branches and names them. No children yet.",
        planner_develop="branch_intro first, then child_detail in children order. These are mind-map branches.",
        planner_close="Close on the topic and first-level branches.",
    )


def circle_map_writer(language: str) -> LessonParts:
    """Circle map: define the center by peer associations. No hierarchy."""
    if _zh(language):
        return LessonParts(
            overview="开场点名中心词，并点出周围联想是从哪些角度把中心放进情境。联想彼此平级，没有上下级。",
            step="这一步是一条联想（role=context）。只讲它如何帮助定义中心词。不要说第几支、下属、它下面还有。",
            closing="收成这些联想一起把中心词放在什么情境里。不要收成树状骨架。",
            focus="overview / closing 的 focus_node_ids 必须包含中心词 id 和全部 context 节点 id，不要只框中心词。",
            scope_main="一步对应一条联想。联想没有子点，不要拆层，也不要合并两条联想。",
            scope_each="每条联想单独一步。用 sibling_texts 讲别的联想，用 parent_text 指中心词。没有叶子层级。",
            planner_open="开场问：提到中心词会联想到什么。点名周围的联想角度，不要写成思维导图分支。",
            planner_develop="本节点是一条联想。一帧讲它如何定义中心词。不要 branch_intro 加子点，不要写下属。",
            planner_close="用这些联想收成中心词所处的情境，不要收成分支清单。",
        )
    return LessonParts(
        overview=(
            "Opening names the center and the angles of association around it. "
            "Associations are peers. There is no hierarchy."
        ),
        step=(
            "This step is one association (role=context). "
            "Say how it defines the center. Do not say branch, child, or “under it”."
        ),
        closing="Close on the context these associations place the center in. Do not close as a tree.",
        focus=(
            "Overview and closing focus_node_ids include the center id and every context node id, not the center alone."
        ),
        scope_main="One step per association. Associations have no children. Do not merge two associations.",
        scope_each="Each association is its own step. sibling_texts are other associations; parent_text is the center.",
        planner_open=(
            "Opening asks what the center brings to mind and names the angles. Do not write mind-map branches."
        ),
        planner_develop=(
            "This node is one association. One frame on how it defines the center. No branch_intro plus children."
        ),
        planner_close="Close on the context around the center, not a branch list.",
    )


def bubble_map_writer(language: str) -> LessonParts:
    """Bubble map: describe a thing by its attributes."""
    if _zh(language):
        return LessonParts(
            overview="开场点名被描述的事物，说明周围气泡是它的属性，不是分类，也不是自由联想。",
            step="这一步是一条属性（role=attribute）。讲它如何描述该事物。不要把属性叫成分支或子点。",
            closing="用这些属性收成一句描述。",
            focus="overview / closing 的 focus_node_ids 必须包含事物 id 和全部 attribute 节点 id。",
            scope_main="一步对应一条属性。属性没有下级。",
            scope_each="每条属性单独一步。parent_text 是被描述的事物，sibling_texts 是其他属性。",
            planner_open="开场问这个事物该用哪些属性来描述，并点出属性，不要说成分类。",
            planner_develop="本节点是一条属性。一帧讲它如何描述事物。不要写成类别下的项目。",
            planner_close="把属性收成一句完整描述。",
        )
    return LessonParts(
        overview="Opening names the thing and says the bubbles are attributes, not categories or free associations.",
        step="This step is one attribute (role=attribute). Say how it describes the thing. Do not call it a branch.",
        closing="Close the attributes into one description.",
        focus="Overview and closing focus_node_ids include the thing id and every attribute id.",
        scope_main="One step per attribute. Attributes have no children.",
        scope_each="Each attribute is its own step. parent_text is the thing; sibling_texts are other attributes.",
        planner_open="Opening asks which attributes describe this thing.",
        planner_develop="This node is one attribute. One frame on how it describes the thing.",
        planner_close="Gather the attributes into one description.",
    )


def double_bubble_writer(language: str) -> LessonParts:
    """Double bubble: compare two things."""
    if _zh(language):
        return LessonParts(
            overview="开场必须同时点名左右两事物。说明中间是相同点，两侧是各自的不同点。",
            step="按 role 讲：similarity 讲两者共有什么；left_diff / right_diff 讲这一侧独有什么，并对照另一侧。不要叫成普通分支。",
            closing="收成一句比较结论：哪里相同，哪里不同。",
            focus="overview / closing 的 focus_node_ids 必须同时包含左右主题、全部相同点和两侧不同点，不要只框左侧。",
            scope_main="相同点、左侧不同点、右侧不同点各成步。right_topic 是 walk=opening，不要单独成步，但 overview 必须点名它。",
            scope_each="每个相同点或不同点单独一步，并点明它属于相同还是某一侧。不要为 right_topic 单独成步。",
            planner_open="开场同时摆出两个事物，并问比的是相同还是不同。",
            planner_develop="相同点帧写共有特征；不同点帧写该侧独有并点出另一侧。不要写成单主题的子点。",
            planner_close="收成一句比较，两侧都要在结论里。",
        )
    return LessonParts(
        overview=("Opening names both things. The middle is similarity; each side is that thing’s differences."),
        step=(
            "similarity says what they share. "
            "left_diff / right_diff says what is unique on that side and contrasts the other."
        ),
        closing="Close with one comparison: what is shared and what differs.",
        focus="Overview and closing focus_node_ids include both topics, every similarity, and both difference columns.",
        scope_main=(
            "Similarities, left differences, and right differences are all steps. "
            "right_topic is walk=opening: name it in the overview, not as its own step."
        ),
        scope_each="Each similarity or difference is its own step and says which column it belongs to.",
        planner_open="Opening places both things and asks what the comparison is about.",
        planner_develop=(
            "A similarity frame is a shared trait. A difference frame is unique to that side and names the other side."
        ),
        planner_close="The closing sentence includes both sides.",
    )


def tree_map_writer(language: str) -> LessonParts:
    """Tree map: classify on one dimension."""
    if _zh(language):
        return LessonParts(
            overview="开场先说出分类维度（role=dimension），再点类别。声明全程只用这一个维度。",
            step="category 步讲这一类为何属于该维度；item 只作为该类的例子，不要升成新类别。",
            closing="收回这一个分类维度，不要改口换成另一种分法。",
            focus="overview / closing 的 focus_node_ids 必须包含主题、维度标签和全部类别 id。",
            scope_main="一步对应一个类别；项目留在该类别 caption 里。dimension 是 walk=opening，只在开场说清，不要单独成步。",
            scope_each="类别是 trunk，项目是 leaf。项目不要讲成另一个维度。",
            planner_open="开场亮出分类维度，再列出类别名。",
            planner_develop="类别帧解释它为何属于该维度；children 里的项目只作例子，不要另起维度。",
            planner_close="收束在同一个分类维度上。",
        )
    return LessonParts(
        overview="Opening names the classification dimension first, then the categories. One dimension only.",
        step="A category step says why it belongs to that dimension. Items stay examples of that category.",
        closing="Close on this same dimension. Do not switch schemes.",
        focus="Overview and closing focus_node_ids include the topic, the dimension label, and every category id.",
        scope_main=(
            "One step per category; items stay in that caption. "
            "The dimension node is walk=opening: name it in the overview, not as its own step."
        ),
        scope_each="Categories are trunks; items are leaves. Do not promote an item into a new dimension.",
        planner_open="Opening states the dimension, then the category names.",
        planner_develop="A category frame explains the dimension. Children are examples, not a new scheme.",
        planner_close="Close on the same dimension.",
    )


def brace_map_writer(language: str) -> LessonParts:
    """Brace map: whole and parts."""
    if _zh(language):
        return LessonParts(
            overview="开场点名整体和拆分维度，说明向右是部分，不是放射分支。",
            step="part 步讲这一部分如何组成整体；subpart 只解释所属部分。",
            closing="把部分收回整体。",
            focus="overview / closing 的 focus_node_ids 必须包含整体 id、维度标签和全部 part id。",
            scope_main="一步对应一个部分；子部分留在该部分 caption 里。dimension 是 walk=opening，只在开场说清，不要单独成步。",
            scope_each="部分是 trunk，子部分是 leaf。",
            planner_open="开场亮出整体，并说出按什么拆。",
            planner_develop="部分帧讲它如何构成整体；children 是子部分，不要写成思维导图分支。",
            planner_close="把部分收回到整体。",
        )
    return LessonParts(
        overview="Opening names the whole and how it is split. Parts are not radiating branches.",
        step="A part step says how that part makes the whole. A subpart explains its part only.",
        closing="Return the parts to the whole.",
        focus="Overview and closing focus_node_ids include the whole id, the dimension label, and every part id.",
        scope_main=(
            "One step per part; subparts stay in that caption. "
            "The dimension is walk=opening and is named only in the overview."
        ),
        scope_each="Parts are trunks; subparts are leaves.",
        planner_open="Opening names the whole and the split.",
        planner_develop="A part frame says how it makes the whole. Children are subparts.",
        planner_close="Gather the parts back into the whole.",
    )


def flow_map_writer(language: str) -> LessonParts:
    """Flow map: sequence."""
    if _zh(language):
        return LessonParts(
            overview="开场点名过程，并按先后点出步骤。不要打乱顺序，也不要说成并列分支。",
            step="step 步讲这一步为何接在上一步之后。substep 只解释所属步骤，不要变成新的主步骤。",
            closing="按顺序把过程再走一遍。",
            focus="overview / closing 的 focus_node_ids 必须包含过程主题 id 和全部 step id，按清单顺序。",
            scope_main="一步对应一个主步骤，按时间顺序；子步骤留在该步 caption 里。",
            scope_each="主步骤是 trunk，子步骤是 leaf。leaf 不要改顺序。",
            planner_open="开场问这个过程从哪一步开始，并按顺序列出步骤名。",
            planner_develop="本帧是过程中的一步。讲它和前一步的先后。children 是子步骤，不要升成主步骤。",
            planner_close="按原顺序收成整段过程。",
        )
    return LessonParts(
        overview="Opening names the process and the steps in order. Do not treat them as peer branches.",
        step="A step says why it follows the previous one. A substep explains its step only.",
        closing="Retell the process in the same order.",
        focus="Overview and closing focus_node_ids include the process id and every step id, in list order.",
        scope_main="One step per main step, in time order; substeps stay in that caption.",
        scope_each="Main steps are trunks; substeps are leaves. Do not reorder leaves.",
        planner_open="Opening asks where the process starts and lists step names in order.",
        planner_develop="This frame is one moment in the process and how it follows the previous step.",
        planner_close="Close by walking the same order again.",
    )


def multi_flow_writer(language: str) -> LessonParts:
    """Multi-flow: causes then effects of one event."""
    if _zh(language):
        return LessonParts(
            overview="开场点名事件。先预告原因在事件之前，结果在事件之后。原因和结果都要出现。",
            step="cause 步讲这个原因如何导致事件；effect 步讲事件如何造成这个结果。不要都叫成分支。",
            closing="收成：哪些原因带来这件事，这件事又造成哪些结果。",
            focus="overview / closing 的 focus_node_ids 必须包含事件 id、全部 cause id 和全部 effect id。",
            scope_main="先原因步，后结果步。不要只讲结果。",
            scope_each="每个原因或结果单独一步，并说清它在事件之前还是之后。",
            planner_open="开场点名事件，并问原因与结果分别在哪一侧。",
            planner_develop="原因帧写它如何导致事件；结果帧写事件如何造成它。不要写成普通子点。",
            planner_close="结论里原因和结果都要在。",
        )
    return LessonParts(
        overview="Opening names the event. Causes come before it; effects come after. Both columns appear.",
        step="A cause step says how it leads to the event. An effect step says how the event leads to it.",
        closing="Close on which causes lead to the event and which effects follow.",
        focus="Overview and closing focus_node_ids include the event id, every cause id, and every effect id.",
        scope_main="Cause steps first, then effect steps. Do not teach effects only.",
        scope_each="Each cause or effect is its own step and says whether it is before or after the event.",
        planner_open="Opening names the event and asks which side is cause and which is effect.",
        planner_develop="A cause frame leads to the event. An effect frame follows from the event.",
        planner_close="The closing sentence includes both causes and effects.",
    )


def bridge_map_writer(language: str) -> LessonParts:
    """Bridge map: analogy under one relating factor."""
    if _zh(language):
        return LessonParts(
            overview="开场先说出关系因子，再说明每一对都是「左项之于右项」，遵守同一个因子。",
            step="讲一对时必须同时点 analogy_left 和 analogy_right。不要把左右拆成互不相关的节点。",
            closing="用关系因子收成类比规律。",
            focus="overview / closing 的 focus_node_ids 必须包含关系因子 id 以及每一对的左右节点 id。",
            scope_main="一步对应一对。清单里左项代表这一对，child_texts 是右项。关系因子 walk=opening，不要单独成步。",
            scope_each="一对一步，左右都写在这一步里。不要把左右拆成两步。关系因子只在开场点名。",
            planner_open="开场说出关系因子，并问每一对在比什么。",
            planner_develop="本帧必须同时写这对的左项和右项，以及它们如何体现关系因子。不要只写一侧。",
            planner_close="用同一个关系因子收成规律。",
        )
    return LessonParts(
        overview="Opening names the relating factor, then each pair as left-as-to-right under that factor.",
        step="Speak analogy_left and analogy_right together. Do not split the pair into unrelated nodes.",
        closing="Close on the analogy rule of the relating factor.",
        focus="Overview and closing focus_node_ids include the factor id and both sides of every pair.",
        scope_main=(
            "One step per pair. The left node stands for the pair; child_texts is the right side. "
            "The relating factor is walk=opening, not its own step."
        ),
        scope_each="One step per pair, both sides in that step. Do not split the pair. Name the factor in the opening.",
        planner_open="Opening states the relating factor and asks what each pair compares.",
        planner_develop="The frame names both sides of the pair and how they show the factor.",
        planner_close="Close on that same factor.",
    )


def concept_map_writer(language: str) -> LessonParts:
    """Concept map: the link label is the content."""
    if _zh(language):
        return LessonParts(
            overview="开场点名焦点概念，以及它连向哪些概念。有 relation 就必须念出来。",
            step="concept 步讲关系词，不要把连线说成没有标签的分支。relation 为空就不要编关系。",
            closing="收成这张概念网：谁通过什么关系连到谁。",
            focus="overview / closing 的 focus_node_ids 必须包含焦点概念 id 和清单里的全部 concept id。",
            scope_main="一步对应一个相连概念，并带上它的 relation。",
            scope_each="每个概念单独一步，caption 里必须出现 relation（若节点带了 relation）。",
            planner_open="开场问焦点概念和谁有关系，并念出关系词。",
            planner_develop="本帧讲这个概念与焦点（或 parent）之间的关系词。不要写成无标签子点。",
            planner_close="收成概念之间的关系，而不是层级大纲。",
        )
    return LessonParts(
        overview="Opening names the focus concept and what it links to. Speak relation when it is present.",
        step="A concept step teaches the link label. Do not invent a relation when relation is empty.",
        closing="Close as a web: who links to whom, and by which relationship.",
        focus="Overview and closing focus_node_ids include the focus id and every concept id in the list.",
        scope_main="One step per linked concept, including its relation.",
        scope_each="Each concept is its own step and the caption includes relation when the node has one.",
        planner_open="Opening asks which concepts relate to the focus and speaks the link labels.",
        planner_develop="This frame teaches the relationship, not an unlabeled child.",
        planner_close="Close on the relationships, not a hierarchy.",
    )


_WRITERS: dict[str, Callable[[str], LessonParts]] = {
    "mind_map": mind_map_writer,
    "circle_map": circle_map_writer,
    "bubble_map": bubble_map_writer,
    "double_bubble_map": double_bubble_writer,
    "tree_map": tree_map_writer,
    "brace_map": brace_map_writer,
    "flow_map": flow_map_writer,
    "multi_flow_map": multi_flow_writer,
    "bridge_map": bridge_map_writer,
    "concept_map": concept_map_writer,
}


def lesson_writer(diagram_type: str, language: str) -> LessonParts:
    """Return the overview / step / closing writer for this diagram."""
    writer = _WRITERS.get(normalize_lecture_diagram(diagram_type), mind_map_writer)
    return writer(language)


def lesson_scope_brief(diagram_type: str, scope: str, language: str) -> str:
    """Tour-scope body for a non-mind-map diagram. Mind maps keep the shared brief."""
    parts = lesson_writer(diagram_type, language)
    if scope == "each_node":
        return parts.scope_each
    return parts.scope_main


def lesson_part_fields(diagram_type: str, language: str) -> dict[str, str]:
    """Structured overview / step / closing fields for a user payload."""
    parts = lesson_writer(diagram_type, language)
    return {
        "lesson_overview": parts.overview,
        "lesson_step": parts.step,
        "lesson_closing": parts.closing,
        "lesson_focus": parts.focus,
    }
