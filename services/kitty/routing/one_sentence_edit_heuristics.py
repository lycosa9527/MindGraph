"""Deterministic one-sentence edit phrases when LLM tool-calling fails or times out.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

_ADD_BRANCH_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?:一个|一条|一个新的|一条新的)?"
    r"(?P<label>.+?)"
    r"(?:的)?"
    r"(?:分支|节点)$"
)

# 「添加分支 A.1」 / 「加一个分支叫A.1」 — label after 分支/节点
_ADD_BRANCH_ZH_PREFIX = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?:一个|一条|一个新的|一条新的)?"
    r"(?:分支|节点)"
    r"(?:叫|名为|叫做|：|:|为)?"
    r"\s*"
    r"(?P<label>.+)$"
)

_ADD_BRANCH_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:add|create|insert)\s+"
    r"(?:a\s+|an\s+|the\s+)?"
    r"(?:new\s+)?"
    r"(?:branch|node)\s+"
    r"(?:called\s+|named\s+|for\s+|titled\s+)?"
    r"[\"']?(?P<label>.+?)[\"']?$",
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

_UPDATE_CENTER_THEN_AUTO_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:把)?"
    r"(?:主题|中心|标题)"
    r"(?:改成|换成|改为|变成|改成是|设为|设置为)"
    r"(?P<label>.+?)"
    r"[，,、]?\s*"
    r"(?:并|然后|再)?"
    r"(?:自动)?(?:补全|补完|完善|填充)"
    r"(?:一下)?(?:整张)?(?:导图|图示|思维导图)?$"
)

_UPDATE_CENTER_THEN_AUTO_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:change|set|update|rename)\s+"
    r"(?:the\s+)?"
    r"(?:topic|center|title)\s+"
    r"(?:to|as)\s+"
    r"[\"']?(?P<label>.+?)[\"']?\s*"
    r"(?:,\s*)?(?:and\s+)?(?:then\s+)?"
    r"(?:auto[-\s]?complete|complete)(?:\s+the\s+diagram)?$",
    re.IGNORECASE,
)

_ADD_BRANCH_THEN_AUTO_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?:一个|一条|一个新的|一条新的)?"
    r"(?P<label>.+?)"
    r"(?:的)?"
    r"(?:分支|节点)"
    r"[，,、]?\s*"
    r"(?:并|然后|再)?"
    r"(?:自动)?(?:补全|补完|完善|填充)"
    r"(?:一下|它|这个分支|该分支)?$"
)

_ADD_BRANCH_THEN_AUTO_ZH_PREFIX = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?:一个|一条|一个新的|一条新的)?"
    r"(?:分支|节点)"
    r"(?:叫|名为|叫做|：|:|为)?"
    r"\s*"
    r"(?P<label>.+?)"
    r"[，,、]?\s*"
    r"(?:并|然后|再)?"
    r"(?:自动)?(?:补全|补完|完善|填充)"
    r"(?:一下|它|这个分支|该分支)?$"
)

_ADD_BRANCH_THEN_AUTO_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:add|create|insert)\s+"
    r"(?:a\s+|an\s+|the\s+)?"
    r"(?:new\s+)?"
    r"(?:branch|node)\s+"
    r"(?:called\s+|named\s+|for\s+|titled\s+)?"
    r"[\"']?(?P<label>.+?)[\"']?\s*"
    r"(?:,\s*)?(?:and\s+)?(?:then\s+)?"
    r"(?:auto[-\s]?complete|complete|fill(?:\s+in)?)\s*"
    r"(?:it|the\s+branch)?$",
    re.IGNORECASE,
)

# Multi named branches — list separators required so single-add phrases stay intact.
_MULTI_ADD_BRANCH_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?:以下|这些|几个)?"
    r"(?:分支|节点)?"
    r"(?:：|:|为)?"
    r"\s*"
    r"(?P<labels>.+?(?:[、，,]|和|&).+?)"
    r"(?:这?[二三四五六七八九十\d]+个)?"
    r"(?:分支|节点)"
    r"(?:[，,、]?\s*(?:并|然后|再)?(?:自动)?(?:补全|补完|完善|填充)(?:一下|它们)?)?$"
)

_MULTI_ADD_BRANCH_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:add|create)\s+"
    r"(?:(?:the\s+|these\s+|new\s+)?)?"
    r"(?:branches|nodes)\s+"
    r"(?:called\s+|named\s+)?"
    r"(?P<labels>.+?(?:,| and ).+?)$",
    re.IGNORECASE,
)

_MULTI_ADD_BRANCH_EN_SUFFIX = re.compile(
    r"^(?:please\s+)?"
    r"(?:add|create)\s+"
    r"(?P<labels>.+?(?:,| and ).+?)\s+"
    r"(?:branches|nodes)$",
    re.IGNORECASE,
)

_UPDATE_CENTER_THEN_MULTI_ADD_ZH = re.compile(
    r"^(?:请)?(?:帮我)?(?:把)?"
    r"(?:主题|中心|标题)"
    r"(?:改成|换成|改为|变成|改成是|设为|设置为)"
    r"(?P<topic>.+?)"
    r"[，,、]?\s*"
    r"(?:并|然后|再)?"
    r"(?:添加|增加|加|新建|加入)"
    r"(?:以下|这些|几个)?"
    r"(?:分支|节点)?"
    r"(?:：|:|为)?"
    r"\s*"
    r"(?P<labels>.+?(?:[、，,]|和|&).+?)"
    r"(?:这?[二三四五六七八九十\d]+个)?"
    r"(?:分支|节点)?"
    r"(?:[，,、]?\s*(?:并|然后|再)?(?:自动)?(?:补全|补完|完善|填充)(?:一下|它们)?)?$"
)

_UPDATE_CENTER_THEN_MULTI_ADD_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:change|set|update|rename)\s+"
    r"(?:the\s+)?"
    r"(?:topic|center|title)\s+"
    r"(?:to|as)\s+"
    r"[\"']?(?P<topic>.+?)[\"']?\s*"
    r"(?:,\s*)?(?:and\s+)?(?:then\s+)?"
    r"(?:add|create)\s+"
    r"(?:(?:the\s+|these\s+|new\s+)?)?"
    r"(?:branches|nodes)\s+"
    r"(?:called\s+|named\s+)?"
    r"(?P<labels>.+?(?:,| and ).+?)$",
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
    r"(?:删除|去掉|移除)"
    r"(?:一下)?"
    r"(?P<label>.+?)"
    r"(?:的)?"
    r"(?:分支|节点)$"
)

_DELETE_NODE_EN = re.compile(
    r"^(?:please\s+)?"
    r"(?:delete|remove)\s+"
    r"(?:the\s+|a\s+|an\s+)?"
    r"(?:branch|node)\s+"
    r"(?:called\s+|named\s+)?"
    r"[\"']?(?P<label>.+?)[\"']?$",
    re.IGNORECASE,
)

_STRIP_TRAILING_PUNCT = re.compile(r"[。.!！？?\s]+$")


def _clean_label(raw: str) -> str:
    label = _STRIP_TRAILING_PUNCT.sub("", (raw or "").strip())
    label = label.strip("\"'「」『』")
    if label.startswith("和") and len(label) > 1:
        label = label[1:].strip()
    if re.match(r"(?i)^and\s+", label):
        label = label[3:].strip()
    return label.strip()


def _split_multi_labels(raw: str) -> list[str]:
    """Split a user-listed branch string into clean labels (need ≥2)."""
    normalized = (raw or "").strip()
    # 「A、B和C」 / "A, B, and C" → normalize list separators.
    normalized = re.sub(r"(?<=\S)和(?=\S)", "、", normalized)
    normalized = re.sub(r"(?i),\s*and\s+", "、", normalized)
    labels: list[str] = []
    for chunk in _LABEL_LIST_SPLIT.split(normalized):
        label = _clean_label(chunk)
        if label:
            labels.append(label)
    return labels


def _multi_add_command(
    labels: list[str],
    *,
    topic: str = "",
) -> Optional[Dict[str, Any]]:
    """Build update_center? + sequential add_node follow-ups (no AC tools)."""
    if len(labels) < 2:
        return None
    first, *rest = labels
    follows: list[Dict[str, Any]] = [{"action": "add_node", "target": label, "confidence": 0.92} for label in rest]
    topic_label = topic.strip()
    if topic_label:
        return {
            "action": "update_center",
            "target": topic_label,
            "confidence": 0.92,
            "follow_up_actions": [
                {"action": "add_node", "target": first, "confidence": 0.92},
                *follows,
            ],
        }
    return {
        "action": "add_node",
        "target": first,
        "confidence": 0.92,
        "follow_up_actions": follows,
    }


def heuristic_one_sentence_edit_command(command_text: str) -> Optional[Dict[str, Any]]:
    """
    Map clear structural edit phrases to legacy Kitty commands.

    Returns None when the text is not a high-confidence structural edit.
    """
    text = _STRIP_TRAILING_PUNCT.sub("", (command_text or "").strip())
    if not text:
        return None

    if _WHOLE_AUTO_COMPLETE_ZH.match(text) or _WHOLE_AUTO_COMPLETE_EN.match(text):
        return {"action": "auto_complete", "confidence": 0.95}

    for pattern in (
        _COMPLETE_BRANCH_ZH,
        _COMPLETE_BRANCH_ZH_SUFFIX,
        _COMPLETE_BRANCH_EN,
        _COMPLETE_BRANCH_EN_ALT,
    ):
        complete = pattern.match(text)
        if complete is None:
            continue
        label = _clean_label(complete.group("label"))
        if label:
            return {
                "action": "auto_complete_branch",
                "target": label,
                "confidence": 0.95,
            }

    for pattern in (_UPDATE_CENTER_THEN_AUTO_ZH, _UPDATE_CENTER_THEN_AUTO_EN):
        center_auto = pattern.match(text)
        if center_auto is None:
            continue
        label = _clean_label(center_auto.group("label"))
        if label:
            return {
                "action": "update_center",
                "target": label,
                "confidence": 0.92,
                "follow_up_actions": [
                    {"action": "auto_complete", "confidence": 0.95},
                ],
            }

    for pattern in (_UPDATE_CENTER_THEN_MULTI_ADD_ZH, _UPDATE_CENTER_THEN_MULTI_ADD_EN):
        center_multi = pattern.match(text)
        if center_multi is None:
            continue
        topic = _clean_label(center_multi.group("topic"))
        labels = _split_multi_labels(center_multi.group("labels"))
        cmd = _multi_add_command(labels, topic=topic)
        if cmd is not None:
            return cmd

    for pattern in (_MULTI_ADD_BRANCH_ZH, _MULTI_ADD_BRANCH_EN, _MULTI_ADD_BRANCH_EN_SUFFIX):
        multi_add = pattern.match(text)
        if multi_add is None:
            continue
        labels = _split_multi_labels(multi_add.group("labels"))
        cmd = _multi_add_command(labels)
        if cmd is not None:
            return cmd

    for pattern in (
        _ADD_BRANCH_THEN_AUTO_ZH,
        _ADD_BRANCH_THEN_AUTO_ZH_PREFIX,
        _ADD_BRANCH_THEN_AUTO_EN,
    ):
        add_auto = pattern.match(text)
        if add_auto is None:
            continue
        label = _clean_label(add_auto.group("label"))
        if label:
            return {
                "action": "add_node",
                "target": label,
                "confidence": 0.92,
                "follow_up_actions": [
                    {
                        "action": "auto_complete_branch",
                        "target": label,
                        "confidence": 0.95,
                    },
                ],
            }

    for pattern in (_UPDATE_CENTER_ZH, _UPDATE_CENTER_EN):
        center = pattern.match(text)
        if center is None:
            continue
        label = _clean_label(center.group("label"))
        if label:
            return {
                "action": "update_center",
                "target": label,
                "confidence": 0.92,
            }

    for pattern in (_DELETE_NODE_ZH, _DELETE_NODE_EN):
        delete = pattern.match(text)
        if delete is None:
            continue
        label = _clean_label(delete.group("label"))
        if label:
            return {
                "action": "delete_node",
                "target": label,
                "confidence": 0.92,
            }

    for pattern in (_ADD_BRANCH_ZH, _ADD_BRANCH_ZH_PREFIX, _ADD_BRANCH_EN):
        match = pattern.match(text)
        if match is None:
            continue
        label = _clean_label(match.group("label"))
        if not label:
            continue
        return {
            "action": "add_node",
            "target": label,
            "confidence": 0.92,
        }

    return None
