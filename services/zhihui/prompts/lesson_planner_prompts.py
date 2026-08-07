"""Prompt set A — lesson planner system/user messages for qwen3.7-plus."""

from __future__ import annotations

import json
from typing import Any

# Shared pedagogy + frame schema. Phase user messages scope the slice of the deck.
LESSON_PLANNER_SYSTEM = """你是资深 K12 课程设计师 + 批判性思维教练 + 可视化教学 PPT 导演。
根据用户提供的思维导图结构，设计面向学习者的图示课件分镜（PPT 风格）。

# 最高优先级：跟着用户导图走（不可违背）
1. **outline / 当前分支是唯一知识骨架**：禁止发明导图里不存在的一级分支或子点。
2. **导图联动字段必准**
   - 主题总览与收束：focus_branch=""、focus_child=""。
   - 分支帧：focus_branch = 该分支的 id（优先）或原文 text。
   - 子点帧：focus_child = 该子节点原文；无对应子点时为 ""。
3. 子点表述可轻度教学改写，但必须能对应 children；学习内容服务于导图逻辑。

# 受众与基调
- 默认受众：初中～高一；禁止“小朋友们”等低幼称呼。
- 教学严谨度约 7/10，趣味引导约 3/10。

# 每帧内容质量（必守）
- title：≤14 字；投影可见字（标题除外）心态 ≤30 字。
- lesson_beat / learning_point / manifestation：可画、具体；冲突帧 cognitive_conflict=true 且 think_prompt 必填。
- teacher_script：口语化教师旁白（1～3 句，可课堂朗读）。必须点名本帧对应的主题/分支/子点，与 focus 对齐；开场可用「今天我们一起聊聊…」，收束可金句收口。禁止只重复 title；禁止写成板书条目。
- visual_subjects：3～6 个关键词。
- 本阶段 frames ≤ 12；只输出用户要求的 JSON 切片，不要 markdown 代码块。

# 单帧字段
{
  "title": "短标题",
  "frame_role": "topic_overview|branch_intro|child_detail|cognitive_conflict|synthesis|close",
  "lesson_beat": "本帧教学意图",
  "learning_point": "一句核心收获",
  "manifestation": "可画具象",
  "think_prompt": "问句或空字符串",
  "teacher_script": "口语教师旁白，点名本帧导图焦点",
  "visual_subjects": ["关键词", "..."],
  "focus_branch": "分支 id 或原文；主题/收束为空字符串",
  "focus_child": "子点原文或空字符串",
  "cognitive_conflict": false
}"""

_FRAME_SCHEMA_HINT = (
    "每帧含 title、frame_role、lesson_beat、learning_point、manifestation、"
    "think_prompt、teacher_script、visual_subjects、focus_branch、focus_child、cognitive_conflict。"
)

LESSON_PLANNER_REPAIR_USER = "上一次输出不是合法 JSON 或缺少必要字段。请仅按当前阶段要求输出合法 JSON 对象，不要解释。"

LESSON_PLANNER_OPEN_REPAIR = (
    "上一次输出不是合法 JSON。"
    '请仅输出 {"style_seed":"...","batches":[{"batch_role":"open","frames":[...]}]}；'
    "第一帧必须是 topic_overview 且 focus_branch/focus_child 为空。不要解释。"
)

LESSON_PLANNER_BRANCH_REPAIR = (
    "上一次输出不是合法 JSON。"
    '请仅输出 {"batches":[{"batch_role":"develop","frames":[...]}]}；'
    "所有帧 focus_branch 必须指向当前分支；先 branch_intro 再 children。不要解释。"
)

LESSON_PLANNER_CLOSE_REPAIR = (
    "上一次输出不是合法 JSON。"
    '请仅输出 {"batches":[{"batch_role":"close","frames":[...]}]}；'
    "收束帧 focus_branch/focus_child 为空。不要解释。"
)


def _base_payload(
    *,
    language: str,
    diagram_title: str,
) -> dict[str, Any]:
    return {
        "language": (language or "zh").strip() or "zh",
        "diagram_title": (diagram_title or "").strip(),
    }


def build_open_planner_message(
    outline_payload: dict[str, Any],
    *,
    language: str = "zh",
    diagram_title: str = "",
) -> str:
    """User message for open phase: style_seed + topic_overview only."""
    payload = {
        **_base_payload(language=language, diagram_title=diagram_title),
        "phase": "open",
        "outline": {
            "topic": outline_payload.get("topic"),
            "branch_order": outline_payload.get("branch_order", "clockwise"),
            "branch_titles": [
                str(branch.get("text") or "").strip()
                for branch in (outline_payload.get("branches") or [])
                if isinstance(branch, dict) and str(branch.get("text") or "").strip()
            ],
        },
        "requirements": [
            "只设计开场：反直觉钩子 topic_overview，只问不答",
            "给出全课件统一 style_seed（媒介、配色、光感；课堂友好、非低幼）",
            "batches 仅含一个 batch_role=open；通常 1 帧，最多 2 帧",
            "focus_branch 与 focus_child 必须为空字符串",
            "每帧必须有 teacher_script（口语开场旁白，点名主题）",
            _FRAME_SCHEMA_HINT,
        ],
    }
    return (
        "阶段：开场（open）。只输出 JSON："
        '{"style_seed":"...","batches":[{"batch_role":"open","frames":[...]}]}。\n'
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def build_branch_planner_message(
    outline_payload: dict[str, Any],
    branch: dict[str, Any],
    *,
    style_seed: str,
    branch_index: int,
    branch_total: int,
    language: str = "zh",
    diagram_title: str = "",
    include_choice_frame: bool = False,
) -> str:
    """User message for one develop branch."""
    branch_id = str(branch.get("id") or "").strip()
    branch_text = str(branch.get("text") or "").strip()
    focus = branch_id or branch_text
    payload = {
        **_base_payload(language=language, diagram_title=diagram_title),
        "phase": "develop_branch",
        "style_seed_fixed": (style_seed or "").strip(),
        "topic": outline_payload.get("topic"),
        "branch_index": branch_index,
        "branch_total": branch_total,
        "branch": branch,
        "requirements": [
            f"只设计当前一级分支：{branch_text}（focus_branch 必须用 {focus!r}）",
            "先 branch_intro（含具体类比），再按 children 顺序 child_detail（可择要）",
            "发现对立/误解/两难：加 cognitive_conflict + think_prompt",
            (
                "本分支尽量安排一帧 A/B 角色抉择（扎根本分支）"
                if include_choice_frame
                else "若本分支有自然冲突可加抉择；否则不必强行加"
            ),
            "不要输出其他分支的帧；不要改 style_seed",
            "batches 仅含一个 batch_role=develop",
            "每帧必须有 teacher_script（口语旁白，点名本分支/子点）",
            _FRAME_SCHEMA_HINT,
        ],
    }
    return (
        "阶段：单分支展开（develop）。只输出 JSON："
        '{"batches":[{"batch_role":"develop","frames":[...]}]}。\n'
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def build_close_planner_message(
    outline_payload: dict[str, Any],
    *,
    style_seed: str,
    language: str = "zh",
    diagram_title: str = "",
) -> str:
    """User message for close/synthesis phase."""
    branch_titles = [
        str(branch.get("text") or "").strip()
        for branch in (outline_payload.get("branches") or [])
        if isinstance(branch, dict) and str(branch.get("text") or "").strip()
    ]
    payload = {
        **_base_payload(language=language, diagram_title=diagram_title),
        "phase": "close",
        "style_seed_fixed": (style_seed or "").strip(),
        "topic": outline_payload.get("topic"),
        "branch_titles": branch_titles,
        "requirements": [
            "只设计收束：金句 + 有记忆点画面；勿复读分支清单",
            "batches 仅含一个 batch_role=close；通常 1 帧",
            "focus_branch 与 focus_child 必须为空字符串",
            "不要改 style_seed",
            "每帧必须有 teacher_script（口语收束旁白）",
            _FRAME_SCHEMA_HINT,
        ],
    }
    return (
        "阶段：收束（close）。只输出 JSON："
        '{"batches":[{"batch_role":"close","frames":[...]}]}。\n'
        f"{json.dumps(payload, ensure_ascii=False)}"
    )


def build_lesson_planner_user_message(
    outline_payload: dict[str, Any],
    *,
    language: str = "zh",
    diagram_title: str = "",
) -> str:
    """Backward-compatible full-deck prompt (prefer phase builders for production)."""
    return build_open_planner_message(
        outline_payload,
        language=language,
        diagram_title=diagram_title,
    )
