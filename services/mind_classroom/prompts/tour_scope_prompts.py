"""巡讲粒度 briefs — which nodes become steps, not how they are spoken."""

from __future__ import annotations

from typing import Any

TOUR_SCOPE_IDS = frozenset({"main_branch", "each_node"})

_LABELS = {
    "main_branch": {"zh": "按主分支", "en": "Main branches"},
    "each_node": {"zh": "逐个节点", "en": "Node by node"},
}

_BRIEFS_ZH = {
    "main_branch": (
        "巡讲粒度：按主分支。"
        "一步对应清单里一个一级分支；子点不拆步，都留在父支 caption 里。"
        "overview：点名主题，按 nodes[].place 报一级分支方位，不展开子点。"
        "branch：点名+方位+定调；子点覆盖面听 tone_brief（精读可只挑关系近的两三点）。"
        "支末不要预告下一支。"
        "closing：把已走分支收成轮廓，不要新知识点。"
        "不要合并或跳过清单节点。"
    ),
    "each_node": (
        "巡讲粒度：逐个节点。"
        "清单里每个节点一步，不要跳过叶子。"
        "overview：点名主题，按 place 报一级分支方位，不展开子点。"
        "stop=trunk：只做点名+方位+定调，并说清子点怎么挂在这一支上；不要展开子点细节。"
        "stop=leaf：只讲本节点。用 parent_text / sibling_texts 讲关系；细节深度听 tone_brief。"
        "不要预告下一站。"
        "closing：收成已走一级分支的轮廓，不要只收本批、不要新知识点。"
    ),
}

_BRIEFS_EN = {
    "main_branch": (
        "Tour scope: main branches. "
        "One step per first-level branch; children stay in the parent caption. "
        "Overview names the topic and first-level places — no child dump. "
        "A branch names place and frames the question; how many children you cover "
        "follows tone_brief (close reading may pick two or three related ones). "
        "Do not preview the next branch. "
        "Closing is a contour of walked branches; no new facts. "
        "Do not merge or skip listed nodes."
    ),
    "each_node": (
        "Tour scope: node by node. "
        "One step per listed node; do not skip leaves. "
        "Overview names the topic and first-level places. "
        "stop=trunk: name, place, frame, and how children hang off this branch — "
        "no child detail. "
        "stop=leaf: this node only; use parent_text / sibling_texts for relations; "
        "detail depth follows tone_brief. "
        "Do not preview the next stop. "
        "Closing contours all first-level branches, not only this batch."
    ),
}


def normalize_tour_scope(raw: Any) -> str:
    """Return a valid 巡讲粒度 id, defaulting to main_branch."""
    value = str(raw or "").strip()
    return value if value in TOUR_SCOPE_IDS else "main_branch"


def tour_scope_label(scope: str, language: str) -> str:
    """UI label for a 巡讲粒度 id."""
    lang = "zh" if str(language or "zh").startswith("zh") else "en"
    return _LABELS[normalize_tour_scope(scope)][lang]


def tour_scope_brief(scope: str, language: str) -> str:
    """Instruction block for which nodes become lecture steps."""
    key = normalize_tour_scope(scope)
    if str(language or "zh").startswith("zh"):
        return _BRIEFS_ZH[key]
    return _BRIEFS_EN[key]
