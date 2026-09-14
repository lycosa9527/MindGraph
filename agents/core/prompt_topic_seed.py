"""Topic and diagram-type seeds from a free-form prompt (Kitty / prepare).

Keep aliases aligned with frontend/src/composables/canvasPage/diagramTypeFromPrompt.ts.
"""

from __future__ import annotations

import re
from typing import Optional

_DIAGRAM_TYPE_ALIASES: tuple[tuple[str, str], ...] = (
    ("double bubble map", "double_bubble_map"),
    ("double_bubble_map", "double_bubble_map"),
    ("multi-flow map", "multi_flow_map"),
    ("multi flow map", "multi_flow_map"),
    ("multi_flow_map", "multi_flow_map"),
    ("多重流程图", "multi_flow_map"),
    ("复流程图", "multi_flow_map"),
    ("双气泡图", "double_bubble_map"),
    ("双气泡", "double_bubble_map"),
    ("思维导图", "mindmap"),
    ("mind map", "mindmap"),
    ("mind-map", "mindmap"),
    ("mind_map", "mindmap"),
    ("mindmap", "mindmap"),
    ("circle map", "circle_map"),
    ("circle_map", "circle_map"),
    ("圆圈图", "circle_map"),
    ("bubble map", "bubble_map"),
    ("bubble_map", "bubble_map"),
    ("气泡图", "bubble_map"),
    ("tree map", "tree_map"),
    ("tree_map", "tree_map"),
    ("树形图", "tree_map"),
    ("brace map", "brace_map"),
    ("brace_map", "brace_map"),
    ("括号图", "brace_map"),
    ("flow map", "flow_map"),
    ("flow_map", "flow_map"),
    ("流程图", "flow_map"),
    ("bridge map", "bridge_map"),
    ("bridge_map", "bridge_map"),
    ("桥形图", "bridge_map"),
    ("类比图", "bridge_map"),
    ("concept map", "concept_map"),
    ("concept_map", "concept_map"),
    ("概念图", "concept_map"),
)

_SORTED_ALIASES = tuple(sorted(_DIAGRAM_TYPE_ALIASES, key=lambda row: len(row[0]), reverse=True))
_QUOTE_RE = re.compile(r"[「」\"'“”‘’]")
_TRAIL_PUNCT_RE = re.compile(r"[，。！？、,.!?;:：；]+$")
_ABOUT_RE = re.compile(r"关于\s*[「\"']?([^「」\"'“”\n]+?)[「\"']?\s*的")
_ABOUT_SHORT_RE = re.compile(r"关于\s*[「\"']?([^「」\"'“”\n，。！？]+)")
_THEME_RE = re.compile(r"主题(?:是|为|：|:)\s*[「\"']?([^「」\"'“”\n]+)")
_TITLED_RE = re.compile(r"(?:title|titled)\s+(.+?)(?:\.|$)", re.IGNORECASE)
_COMPARE_RE = re.compile(r"比较\s*[「\"']?([^「」\"'“”和与]+)[「\"']?\s*(?:和|与)\s*[「\"']?([^「」\"'“”]+)")
_COMPARE_REV_RE = re.compile(
    r"[「\"']?([^「」\"'“”和与]+)[「\"']?\s*(?:和|与)\s*[「\"']?([^「」\"'“”]+)[「\"']?\s*(?:的)?(?:对比|比较|双气泡)"
)
_USER_REQ_RE = re.compile(r"【用户要求】[\s\S]*")
_USER_REQ_EN_RE = re.compile(r"user requirements:", re.IGNORECASE)
_LEAD_GENERATE_RE = re.compile(
    r"^(?:请)?(?:帮我)?"
    r"(?:生成|创建|制作|绘制|画|做|打开|新建)?"
    r"(?:一个|一张|一幅)?"
)
_TRAIL_PARTICLE_RE = re.compile(r"[的了着]+$")
_WS_RE = re.compile(r"\s+")


def resolve_diagram_type_from_prompt(text: str) -> Optional[str]:
    """Return a canvas type slug when the prompt names a supported diagram."""
    body = (text or "").strip()
    if not body:
        return None
    lowered = body.lower()
    for alias, slug in _SORTED_ALIASES:
        if alias in body or alias.lower() in lowered:
            return slug
    return None


def _clean_topic_fragment(raw: str) -> str:
    return _TRAIL_PUNCT_RE.sub("", _QUOTE_RE.sub("", raw or "")).strip()


def _strip_diagram_type_phrases(text: str) -> str:
    out = text
    for alias, _slug in _SORTED_ALIASES:
        out = re.sub(re.escape(alias), " ", out, flags=re.IGNORECASE)
    return out


def extract_topic_seed_from_prompt(text: str, diagram_type: str) -> dict[str, str]:
    """Pull topic / double-bubble subjects after type phrases are removed."""
    body = (text or "").strip()
    if not body:
        return {}

    if diagram_type in {"double_bubble_map", "double-bubble-map"}:
        compare = _COMPARE_RE.search(body)
        if compare is None:
            compare = _COMPARE_REV_RE.search(body)
        if compare is not None:
            left = _clean_topic_fragment(compare.group(1))[:240]
            right = _clean_topic_fragment(compare.group(2))[:240]
            if left and right:
                return {"left": left, "right": right}

    about = _ABOUT_RE.search(body)
    if about is not None:
        topic = _clean_topic_fragment(about.group(1))[:480]
        if topic:
            return {"topic": topic}

    about_short = _ABOUT_SHORT_RE.search(body)
    if about_short is not None:
        topic = _clean_topic_fragment(about_short.group(1))[:480]
        if topic:
            return {"topic": topic}

    theme = _THEME_RE.search(body)
    if theme is not None:
        topic = _clean_topic_fragment(theme.group(1))[:480]
        if topic:
            return {"topic": topic}

    titled = _TITLED_RE.search(body)
    if titled is not None:
        topic = _clean_topic_fragment(titled.group(1))[:480]
        if topic:
            return {"topic": topic}

    stripped = _strip_diagram_type_phrases(body)
    stripped = _USER_REQ_RE.sub(" ", stripped)
    stripped = _USER_REQ_EN_RE.sub(" ", stripped)
    stripped = _LEAD_GENERATE_RE.sub("", stripped.strip())
    stripped = _TRAIL_PARTICLE_RE.sub("", stripped.strip())
    stripped = _WS_RE.sub(" ", stripped).strip()
    topic = _clean_topic_fragment(stripped)
    if 1 <= len(topic) <= 480:
        return {"topic": topic}
    return {}


def primary_topic_seed(seed: dict[str, str]) -> str:
    """Single topic string for auto_complete / generate_graph."""
    topic = (seed.get("topic") or "").strip()
    if topic:
        return topic
    left = (seed.get("left") or "").strip()
    right = (seed.get("right") or "").strip()
    if left and right:
        return f"{left} {right}"
    return left or right
