"""Prompt set A — lesson planner system/user messages for qwen3.7-plus."""

from __future__ import annotations

import json
from typing import Any

LESSON_PLANNER_SYSTEM = """你是资深 K12 课程设计师。根据思维导图结构，设计一堂面向学习者的图示课件（PPT 风格分镜）。

要求：
1. 从学习者视角组织内容（导入 → 展开 → 收束），有趣、清晰、教育性强。
2. 不要固定「每个分支固定 N 页」；可按教学需要合并薄弱分支或拆分内容丰富的分支。
3. 每帧以视觉为主：短标题 + 画面主体线索；避免大段文字。
4. 输出严格 JSON（不要 markdown 代码块），结构如下：
{
  "style_seed": "全课件统一的视觉风格描述（媒介、配色、光感、角色/装饰）",
  "batches": [
    {
      "batch_role": "open|develop|close",
      "frames": [
        {
          "title": "短标题",
          "lesson_beat": "本帧教学意图（学习者视角）",
          "visual_subjects": ["画面主体关键词", "..."],
          "focus_branch": "对应导图分支原文或 id（可空）"
        }
      ]
    }
  ]
}
5. batches 可 1 个或多个；每个 batch 的 frames 数量建议 ≤ 12。
6. 只输出 JSON。"""


LESSON_PLANNER_REPAIR_USER = "上一次输出不是合法 JSON 或缺少必要字段。请仅输出符合 schema 的 JSON 对象，不要解释。"


def build_lesson_planner_user_message(
    outline_payload: dict[str, Any],
    *,
    language: str = "zh",
    diagram_title: str = "",
) -> str:
    """Build the user message carrying mind-map outline JSON."""
    lang = (language or "zh").strip() or "zh"
    title = (diagram_title or "").strip()
    payload = {
        "language": lang,
        "diagram_title": title,
        "outline": outline_payload,
    }
    return f"请根据以下思维导图大纲设计课件分镜 JSON。\n{json.dumps(payload, ensure_ascii=False)}"
