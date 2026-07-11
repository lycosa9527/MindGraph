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
    return label.strip()


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
