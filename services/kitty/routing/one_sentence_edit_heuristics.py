"""Deterministic one-sentence edit phrases when LLM tool-calling fails or times out.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from services.kitty.routing.preference_action_heuristics import heuristic_preference_command

# Longest Thinking-Map role words first so 左边不同点 wins over 不同点.
_ADD_KIND_ZH = (
    r"左边不同点|左侧不同点|左不同点|"
    r"右边不同点|右侧不同点|右不同点|"
    r"相同点|相似点|不同点|"
    r"背景|观察|特征|属性|类别|分类|部分|步骤|原因|结果|"
    r"分支|节点"
)
_ADD_KIND_EN = (
    r"left-diff|right-diff|left_difference|right_difference|"
    r"similarity|context|attribute|category|part|step|cause|effect|"
    r"branch|node"
)
_ADD_KIND_EXTRAS: Dict[str, Dict[str, str]] = {
    "左边不同点": {"category": "left_difference"},
    "左侧不同点": {"category": "left_difference"},
    "左不同点": {"category": "left_difference"},
    "不同点": {"category": "left_difference"},
    "left-diff": {"category": "left_difference"},
    "left_diff": {"category": "left_difference"},
    "left_difference": {"category": "left_difference"},
    "右边不同点": {"category": "right_difference"},
    "右侧不同点": {"category": "right_difference"},
    "右不同点": {"category": "right_difference"},
    "right-diff": {"category": "right_difference"},
    "right_diff": {"category": "right_difference"},
    "right_difference": {"category": "right_difference"},
    "相同点": {"category": "similarity"},
    "相似点": {"category": "similarity"},
    "similarity": {"category": "similarity"},
    "原因": {"category": "cause"},
    "cause": {"category": "cause"},
    "结果": {"category": "effect"},
    "effect": {"category": "effect"},
}
_SPEECH_NAME_PREFIX = re.compile(r"^(?:叫做|名为|叫)")

_ADD_BRANCH_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?:一个|一条|一个新的|一条新的)?"
    r"(?P<label>.+?)"
    r"(?:的)?"
    rf"(?P<kind>{_ADD_KIND_ZH})$"
)

# 「添加分支 A.1」 / 「加一个分支叫A.1」 / 「添加一个左边不同点冰淇淋」
_ADD_BRANCH_ZH_PREFIX = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?:一个|一条|一个新的|一条新的)?"
    rf"(?P<kind>{_ADD_KIND_ZH})"
    r"(?:叫|名为|叫做|：|:|为)?"
    r"\s*"
    r"(?P<label>.+)$"
)

_ADD_BRANCH_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:add|create|insert)\s+"
    r"(?:a\s+|an\s+|the\s+)?"
    r"(?:new\s+)?"
    rf"(?P<kind>{_ADD_KIND_EN})\s+"
    r"(?:called\s+|named\s+|for\s+|titled\s+)?"
    r"[\"']?(?P<label>.+?)[\"']?$",
    re.IGNORECASE,
)

_ADD_BRIDGE_PAIR_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?:一个|一条|一对)?"
    r"(?:类比|类比对|桥对)"
    r"\s*"
    r"(?P<left>.+?)"
    r"(?:和|与|、)"
    r"(?P<right>.+)$"
)

_ADD_BRIDGE_PAIR_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:add|create|insert)\s+"
    r"(?:a\s+|an\s+)?"
    r"(?:new\s+)?"
    r"(?:analogy\s+)?(?:pair|bridge)\s+"
    r"[\"']?(?P<left>.+?)[\"']?"
    r"\s+(?:and|to|with)\s+"
    r"[\"']?(?P<right>.+?)[\"']?$",
    re.IGNORECASE,
)

_COMPLETE_BRANCH_ZH = re.compile(
    r"^(?:请)?(?:帮我)?"
    r"(?:自动)?"
    r"(?:补全|填充|展开|完善)"
    r"(?:一下)?"
    r"(?P<label>.+?)"
    r"(?:这个|这条)?"
    r"(?:的)?"
    r"(?:分支|节点)$"
)

_COMPLETE_BRANCH_ZH_SUFFIX = re.compile(
    r"^(?:请)?(?:帮我)?(?:把|将)?"
    r"(?P<label>.+?)"
    r"(?:这个|这条)?"
    r"(?:的)?"
    r"(?:分支|节点)"
    r"(?:自动)?"
    r"(?:补全|填充|展开|完善)"
    r"(?:一下)?$"
)

_COMPLETE_BRANCH_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:auto[-\s]?complete|complete|fill(?:\s+in)?|expand)\s+"
    r"(?:the\s+|a\s+|an\s+)?"
    r"(?:branch|node)\s+"
    r"(?:called\s+|named\s+|for\s+)?"
    r"[\"']?(?P<label>.+?)[\"']?$",
    re.IGNORECASE,
)

_COMPLETE_BRANCH_EN_ALT = re.compile(
    r"^(?:please\s+)?"
    r"(?:auto[-\s]?complete|complete|fill(?:\s+in)?|expand)\s+"
    r"(?:the\s+|a\s+|an\s+)?"
    r"[\"']?(?P<label>.+?)[\"']?\s+"
    r"(?:branch|node)$",
    re.IGNORECASE,
)

_WHOLE_AUTO_COMPLETE_ZH = re.compile(r"^(?:请)?(?:帮我)?(?:自动)?补全(?:一下)?(?:整张)?(?:导图|图示|思维导图)?$")

_WHOLE_AUTO_COMPLETE_EN = re.compile(
    r"^(?:please\s+)?(?:auto[-\s]?complete|run\s+auto[-\s]?complete)(?:\s+the\s+diagram)?$",
    re.IGNORECASE,
)

_LABEL_LIST_SPLIT = re.compile(r"\s*(?:[、，,/|&]|以及|\s+and\s+)\s*", re.IGNORECASE)

_UPDATE_CENTER_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:把)?"
    r"(?:主题|中心|标题)"
    r"(?:改成|换成|改为|变成|改成是|设为|设置为)"
    r"(?P<label>.+)$"
)

_UPDATE_CENTER_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:change|set|update|rename)\s+"
    r"(?:the\s+)?"
    r"(?:topic|center|title)\s+"
    r"(?:to|as)\s+"
    r"[\"']?(?P<label>.+?)[\"']?$",
    re.IGNORECASE,
)

_DELETE_NODE_ZH = re.compile(
    r"^(?:请)?(?:帮我)?"
    r"(?:删除|删掉|去掉|移除)"
    r"(?:一下)?"
    r"(?P<label>.+?)"
    r"(?:这个|这条)?"
    r"(?:的)?"
    rf"(?:{_ADD_KIND_ZH})$"
)

_DELETE_NUMBER_ZH = re.compile(
    r"^(?:请)?(?:帮我)?"
    r"(?:删除|删掉|去掉|移除)"
    r"(?:一下)?"
    r"(?P<label>第?\d+(?:\.\d+)*号?|第[一二三四五六七八九十]+个?|[①-⑳])$"
)

_UPDATE_NODE_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:把|将)"
    r"(?P<old>.+?)"
    r"(?:这个|这条)?"
    r"(?:的)?"
    rf"(?:{_ADD_KIND_ZH})?"
    r"(?:改成|换成|改为|变成|改成是|设为|设置为)"
    r"(?P<new>.+)$"
)

_UPDATE_NODE_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:rename|change)\s+"
    r"(?:the\s+|a\s+|an\s+)?"
    rf"(?:{_ADD_KIND_EN}\s+)?"
    r"[\"']?(?P<old>.+?)[\"']?\s+"
    r"(?:to|as)\s+"
    r"[\"']?(?P<new>.+?)[\"']?$",
    re.IGNORECASE,
)

_DELETE_NODE_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:delete|remove)\s+"
    r"(?:the\s+|a\s+|an\s+)?"
    rf"(?:{_ADD_KIND_EN})\s+"
    r"(?:called\s+|named\s+)?"
    r"[\"']?(?P<label>.+?)[\"']?$",
    re.IGNORECASE,
)

_STRIP_TRAILING_PUNCT = re.compile(r"[。.!！？?\s]+$")
_WRAP_QUOTES = "\"'「」『』“”‘’《》"
# Fun-ASR wraps the name; 这个/这条 is spoken glue before 分支, not the name.
_WRAPPED_SPAN = re.compile(r"[\"'「『“‘《]([^\"'」』”’》]+)[\"'」』”’》]")
_TRAILING_DEICTIC = re.compile(r"(?:这个|这条)$")
_PLACEHOLDER_LABELS = frozenset({"自定义", "新", "新的", "个", "custom", "new"})
_UNNAMED_ADD_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?:一个|一条|一个新的|一条新的|个)?"
    r"(?:自定义的?)?"
    r"(?:分支|节点)$"
)
_UNNAMED_ADD_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:add|create|insert)\s+"
    r"(?:a\s+|an\s+|the\s+)?"
    r"(?:new\s+|custom\s+)?"
    r"(?:branch|node)$",
    re.IGNORECASE,
)

_EXPLAIN_DEICTIC_ZH = re.compile(
    r"^(?:请)?(?:帮我)?"
    r"(?:解释|介绍|讲解|说明)"
    r"(?:一?下)?"
    r"(?:这个|那个|此项|该)(?:节点|分支)?$"
)

_EXPLAIN_DEICTIC_ZH_SUFFIX = re.compile(
    r"^(?:请)?(?:帮我)?"
    r"(?:把|将|给)"
    r"(?:这个|那个|此项|该)(?:节点|分支)"
    r"(?:解释|介绍|讲解|说明)(?:一?下)?$"
)

_EXPLAIN_DEICTIC_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:explain|introduce)\s+"
    r"(?:this|that)\s+"
    r"(?:branch|node)?$",
    re.IGNORECASE,
)

_EXPLAIN_ZH = re.compile(
    r"^(?:请)?(?:帮我)?"
    r"(?:解释|介绍|讲解|说明)(?:一?下)?"
    r"(?P<label>.+?)"
    r"(?:这个|这条)?"
    r"(?:的)?"
    r"(?:分支|节点)?$"
)

_EXPLAIN_ZH_SUFFIX = re.compile(
    r"^(?:请)?(?:帮我)?(?:把|将)?"
    r"(?P<label>.+?)"
    r"(?:这个|这条)?"
    r"(?:的)?"
    r"(?:分支|节点)?"
    r"(?:解释|介绍|讲解)(?:一?下)?$"
)

_EXPLAIN_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:explain|introduce|tell\s+me\s+about)\s+"
    r"(?:the\s+|a\s+|an\s+)?"
    r"(?:branch|node\s+)?"
    r"(?:called\s+|named\s+|for\s+)?"
    r"[\"']?(?P<label>.+?)[\"']?"
    r"(?:\s+(?:branch|node))?$",
    re.IGNORECASE,
)

_EXPLAIN_MAP_LABELS = frozenset(
    {
        "这张图",
        "这张导图",
        "整张导图",
        "导图",
        "思维导图",
        "图",
        "the diagram",
        "the map",
        "the mind map",
        "diagram",
        "map",
    }
)
_EXPLAIN_DEICTIC_LABELS = frozenset({"这个", "那个", "this", "that"})


def is_placeholder_edit_label(label: str) -> bool:
    """True when the captured label is an adjective, not a branch name."""
    return label.strip().lower() in _PLACEHOLDER_LABELS


def _nameless_add_command() -> Dict[str, Any]:
    return {"action": "add_node", "confidence": 0.9}


def _clean_add_label(raw: str) -> str:
    """Normalize an add label and peel spoken 叫/名为 wrappers."""
    label = normalize_edit_label(raw)
    if not label:
        return ""
    peeled = _SPEECH_NAME_PREFIX.sub("", label)
    cleaned = normalize_edit_label(peeled)
    return cleaned or label


def _extras_for_add_kind(kind: str) -> Dict[str, str]:
    key = kind.strip()
    if not key:
        return {}
    mapped = _ADD_KIND_EXTRAS.get(key)
    if mapped is not None:
        return dict(mapped)
    return dict(_ADD_KIND_EXTRAS.get(key.lower(), {}))


def _add_node_command(
    label: str,
    kind: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    command: Dict[str, Any] = {
        "action": "add_node",
        "target": label,
        "confidence": 0.92,
    }
    command.update(_extras_for_add_kind(kind))
    if extra:
        command.update(extra)
    return command


def _whole_asr_quoted_name(label: str) -> Optional[str]:
    """Inner quoted span when it wraps the whole label plus optional 这个/这条."""
    wrapped = _WRAPPED_SPAN.search(label)
    if wrapped is None:
        return None
    prefix = label[: wrapped.start()].strip()
    suffix = _TRAILING_DEICTIC.sub("", label[wrapped.end() :]).strip()
    if prefix or suffix:
        return None
    inner = wrapped.group(1).strip()
    return inner or None


def normalize_edit_label(raw: str) -> str:
    """Peel speech wrappers so the remaining text is the canvas name.

    Fun-ASR often emits ``“Name”这个``. The quoted span is the name only when
    it wraps the whole label; interior book-title quotes stay in the name.
    Otherwise a trailing 这个/这条 is a demonstrative, not part of the label.
    """
    label = _STRIP_TRAILING_PUNCT.sub("", (raw or "").strip())
    peeled = _whole_asr_quoted_name(label)
    if peeled is not None:
        label = peeled
    else:
        label = _TRAILING_DEICTIC.sub("", label).strip()
        label = label.strip(_WRAP_QUOTES)
    label = _STRIP_TRAILING_PUNCT.sub("", label).strip()
    if label.startswith("和") and len(label) > 1:
        label = label[1:].strip()
    if re.match(r"(?i)^and\s+", label):
        label = label[3:].strip()
    return label.strip()


def edit_labels_match(left: str, right: str) -> bool:
    """True when two labels are equal after quote and punct strip."""
    want = normalize_edit_label(left)
    got = normalize_edit_label(right)
    return bool(want) and want == got


def edit_labels_overlap(left: str, right: str) -> bool:
    """Exact or contains match after quote strip (apply / preview lookup)."""
    want = normalize_edit_label(left)
    got = normalize_edit_label(right)
    if not want or not got:
        return False
    return got == want or want in got or got in want


def split_multi_labels(raw: str) -> list[str]:
    """Split a user-listed branch string into clean labels (need ≥2)."""
    normalized = (raw or "").strip()
    # 「A、B和C」 / "A, B, and C" → normalize list separators.
    normalized = re.sub(r"(?<=\S)和(?=\S)", "、", normalized)
    normalized = re.sub(r"(?i),\s*and\s+", "、", normalized)
    labels: list[str] = []
    for chunk in _LABEL_LIST_SPLIT.split(normalized):
        label = normalize_edit_label(chunk)
        if label:
            labels.append(label)
    return labels


def is_fast_explain_command(command: Dict[str, Any]) -> bool:
    """True for a single-intent 节点解释 with no stacked follow-ups."""
    if str(command.get("action") or "") != "explain_node":
        return False
    follows = command.get("follow_up_actions")
    return not (isinstance(follows, list) and follows)


def _explain_command(label: str) -> Optional[Dict[str, Any]]:
    cleaned = normalize_edit_label(label)
    if not cleaned or cleaned.lower() in _EXPLAIN_MAP_LABELS:
        return None
    if cleaned.lower() in _EXPLAIN_DEICTIC_LABELS:
        return {"action": "explain_node", "confidence": 0.9}
    return {"action": "explain_node", "target": cleaned, "confidence": 0.95}


def heuristic_one_sentence_edit_command(command_text: str) -> Optional[Dict[str, Any]]:
    """
    Map clear structural edit phrases to legacy Kitty commands.

    Returns None when the text is not a high-confidence structural edit.
    """
    text = _STRIP_TRAILING_PUNCT.sub("", (command_text or "").strip())
    if not text:
        return None

    preference = heuristic_preference_command(text)
    if preference is not None:
        return preference

    if _EXPLAIN_DEICTIC_ZH.match(text) or _EXPLAIN_DEICTIC_ZH_SUFFIX.match(text) or _EXPLAIN_DEICTIC_EN.match(text):
        return {"action": "explain_node", "confidence": 0.9}

    for pattern in (_EXPLAIN_ZH, _EXPLAIN_ZH_SUFFIX, _EXPLAIN_EN):
        explained = pattern.match(text)
        if explained is None:
            continue
        command = _explain_command(explained.group("label"))
        if command is not None:
            return command

    if _WHOLE_AUTO_COMPLETE_ZH.match(text) or _WHOLE_AUTO_COMPLETE_EN.match(text):
        return {"action": "auto_complete", "confidence": 0.95}

    if _UNNAMED_ADD_ZH.match(text) or _UNNAMED_ADD_EN.match(text):
        return _nameless_add_command()

    for pattern in (
        _COMPLETE_BRANCH_ZH,
        _COMPLETE_BRANCH_ZH_SUFFIX,
        _COMPLETE_BRANCH_EN,
        _COMPLETE_BRANCH_EN_ALT,
    ):
        complete = pattern.match(text)
        if complete is None:
            continue
        label = normalize_edit_label(complete.group("label"))
        if label:
            return {
                "action": "auto_complete_branch",
                "target": label,
                "confidence": 0.95,
            }

    for pattern in (_UPDATE_CENTER_ZH, _UPDATE_CENTER_EN):
        center = pattern.match(text)
        if center is None:
            continue
        label = normalize_edit_label(center.group("label"))
        if label:
            return {
                "action": "update_center",
                "target": label,
                "confidence": 0.92,
            }

    for pattern in (_UPDATE_NODE_ZH, _UPDATE_NODE_EN):
        rename = pattern.match(text)
        if rename is None:
            continue
        old_label = normalize_edit_label(rename.group("old"))
        new_label = normalize_edit_label(rename.group("new"))
        if old_label in {"主题", "中心", "标题", "topic", "center", "title"}:
            continue
        if old_label and new_label and old_label != new_label:
            return {
                "action": "update_node",
                "target": old_label,
                "new_text": new_label,
                "confidence": 0.92,
            }

    for pattern in (_DELETE_NUMBER_ZH, _DELETE_NODE_ZH, _DELETE_NODE_EN):
        delete = pattern.match(text)
        if delete is None:
            continue
        label = normalize_edit_label(delete.group("label"))
        if label:
            return {
                "action": "delete_node",
                "target": label,
                "confidence": 0.92,
            }

    for pattern in (_ADD_BRIDGE_PAIR_ZH, _ADD_BRIDGE_PAIR_EN):
        pair = pattern.match(text)
        if pair is None:
            continue
        left = _clean_add_label(pair.group("left"))
        right = _clean_add_label(pair.group("right"))
        if left and right:
            return _add_node_command(left, extra={"left": left, "right": right})

    for pattern in (_ADD_BRANCH_ZH, _ADD_BRANCH_ZH_PREFIX, _ADD_BRANCH_EN):
        match = pattern.match(text)
        if match is None:
            continue
        label = _clean_add_label(match.group("label"))
        if is_placeholder_edit_label(label):
            return _nameless_add_command()
        if not label:
            continue
        kind = match.group("kind") if "kind" in match.re.groupindex else ""
        return _add_node_command(label, kind)

    return None
