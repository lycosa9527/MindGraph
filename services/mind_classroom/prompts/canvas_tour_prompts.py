"""Prompt templates for 画布语音巡讲 script generation."""

from __future__ import annotations

import json
from typing import Any

from services.mind_classroom.prompts.lesson_writers import lesson_part_fields, lesson_writer
from services.mind_classroom.prompts.mastery_prompts import (
    build_axis_contract_block,
    classroom_pref_fields,
)

CANVAS_TOUR_SYSTEM_SKELETON = """你是思维图示讲解助手。本场图示、口吻、深度、走图方式以「本场选择」与用户消息里的 brief 为准，不要套默认课堂腔或默认初识人设。

# 不可违背
1. 只讲解清单里出现的节点，禁止发明清单外的节点。事实必须能从 nodes 的 text / child_texts / relation 读出。
2. focus_node_ids / branch_node_id 必须使用清单里的 id。overview / closing 的框选听 lesson_focus，不要只框中心节点。
3. 只输出 JSON，不要 markdown 代码块。
4. caption 格式听 tone_brief：考点提纲可用序号与【记】；其他语气不要报幕编号或「标签：内容」。
5. 五份 brief 的分工见「本场选择」。节点叫法听 diagram_brief 与 nodes[].role，走图听 tour_scope_brief，口吻听 tone_brief。
6. 不要把本图示没有的层级说成「分支 / 子点」。role 与 role_label 是该节点在本图示里的身份。

# 步骤
- overview → 按 nodes 清单顺序写 branch 步 → closing。walk=opening 的节点只在 overview 点名，不要单独成步。其余节点一步一个，不要合并、不要跳过。
- 这一步讲什么听 lesson_step 和 tour_scope_brief。不要套思维导图的「主分支 / 子点」，除非 diagram_brief 允许。
- title ≤ 20 字；bullets 原样抄 child_texts，最多 6 条（只给画布）。
- 步骤数不要超过 max_steps。
- 全稿中心主题名字最多出现 2 次。

# 输出
{"steps":[{"kind":"overview|branch|closing","title":"...","caption":"...","bullets":["..."],"focus_node_ids":["id"],"branch_node_id":"id或空字符串"}]}
"""

CANVAS_TOUR_SYSTEM = CANVAS_TOUR_SYSTEM_SKELETON

CANVAS_TOUR_REPAIR = (
    "上一次输出不是合法 JSON 或缺少 steps。"
    '请仅输出 {"steps":[...]}，每步含 kind、title、caption、bullets、focus_node_ids、branch_node_id。不要解释。'
)

_PLACE_HINT_ZH = (
    "place 是画布方位：center=中心，right=右侧，left=左侧，"
    "right_top=右上，right_mid=右中，right_bottom=右下，"
    "left_top=左上，left_mid=左中，left_bottom=左下。"
    "点名和过渡时用中文方位词，以 nodes[].place 为准。"
)

_PLACE_HINT_EN = (
    "place is the canvas quadrant. Name and transition with those directions. Trust nodes[].place, not guesswork."
)


def _lang_is_zh(language: str) -> bool:
    return str(language or "zh").startswith("zh")


def build_canvas_tour_system_message(settings: dict[str, Any] | None) -> str:
    """System prompt: invariant walk/JSON rules plus the selected four-axis contract."""
    return f"{CANVAS_TOUR_SYSTEM_SKELETON.rstrip()}\n\n{build_axis_contract_block(settings)}"


def build_canvas_tour_user_message(
    tour_nodes: list[dict[str, Any]],
    *,
    settings: dict[str, Any],
    max_steps: int,
    write_only_ids: list[str] | None = None,
    emit_overview: bool = True,
    emit_closing: bool = True,
) -> str:
    """User message for canvas-tour script / lesson plan generation."""
    prefs = classroom_pref_fields(settings)
    language = str(settings.get("language") or "zh")
    parts = lesson_writer(str(prefs.get("diagram_type") or ""), language)
    payload: dict[str, Any] = {
        "language": language,
        **prefs,
        **lesson_part_fields(str(prefs.get("diagram_type") or ""), language),
        "max_steps": max_steps,
        "place_hint": _PLACE_HINT_ZH if _lang_is_zh(language) else _PLACE_HINT_EN,
        "nodes": tour_nodes,
        "requirements": [
            "开场遵守 lesson_overview",
            "每一步遵守 lesson_step，叫法用 nodes[].role",
            "收束遵守 lesson_closing",
            "框选遵守 lesson_focus",
            "必须遵守 mastery_brief：听者立场（初识带路 / 复习对照 / 备课教别人）",
            "必须遵守 audience_brief：用词与深度",
            "必须遵守 tour_scope_brief：哪些节点成步",
            "必须遵守 tone_brief：怎么说（句数、问句、提纲或叙事）",
            "跟着 nodes 顺序讲，不要合并或跳过清单节点",
            parts.focus,
            "branch 的 branch_node_id 必须是该节点 id",
            parts.closing,
            "caption 格式听 tone_brief",
        ],
    }
    wanted = [node_id for node_id in (write_only_ids or []) if str(node_id).strip()]
    if wanted:
        payload["write_only_node_ids"] = wanted
        payload["emit_overview"] = emit_overview
        payload["emit_closing"] = emit_closing
        payload["requirements"] = [
            "本批只写 write_only_node_ids 里这些节点的 branch 步，不要写清单里的其他节点",
            "emit_overview 为 true 时第一步写 overview，否则不要 overview",
            "emit_closing 为 true 时最后写 closing，收束遵守 lesson_closing，不要只收本批",
            *payload["requirements"],
        ]
    return f'任务：画布语音巡讲讲稿／教案。只输出 JSON：{{"steps":[...]}}。\n{json.dumps(payload, ensure_ascii=False)}'
