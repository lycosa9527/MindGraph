"""Split 教学设计 markdown headings into a TeachingDesignSpec."""

from __future__ import annotations

import re

from services.mindmate.teaching_design_flag import strip_reply_kind_markers
from services.mindmate.teaching_design_models import (
    ActivityStage,
    TeachingDesignSpec,
    ThinkingPointRow,
)

HEADING_ALIASES: dict[str, str] = {
    "基本信息": "meta",
    "摘要": "summary",
    "总结": "summary",
    "教学内容分析": "content_analysis",
    "学习者分析": "learner_analysis",
    "学习目标及重难点": "objectives",
    "学习目标": "objectives",
    "思维训练点": "thinking",
    "学习活动设计": "activities",
    "课例结构": "structure",
    "板书设计": "board_design",
    "作业与拓展学习设计": "homework",
    "作业与拓展": "homework",
    "素材设计": "materials",
}

HEADING_RE = re.compile(
    r"^(?:#{1,4}\s*|【)\s*(" + "|".join(re.escape(name) for name in HEADING_ALIASES) + r")\s*】?\s*$",
    re.MULTILINE,
)

FIELD_LINE_RE = re.compile(
    r"^(学段年级|学科|教材版本|课时说明|教师单位|教师姓名)\s*[：:]\s*(.+)$",
    re.MULTILINE,
)
TITLE_RE = re.compile(r"[“\"《]([^”\"》]+)[”\"》]\s*教学设计")
BARE_TITLE_RE = re.compile(r"教学设计\s*$")

THINKING_LABELS: tuple[tuple[str, str], ...] = (
    ("问题情境", "问题情境"),
    ("认知冲突", "认知冲突"),
    ("思维可视化", "思维可视化"),
    ("思维图示", "思维可视化"),
    ("变式运用", "变式运用"),
    ("变式设计", "变式运用"),
    ("变式", "变式运用"),
)

STAGE_RE = re.compile(
    r"^环节([一二三四五六七八九十0-9]+)[：:．.\s]*(.*)$",
    re.MULTILINE,
)
ACTION_RE = re.compile(r"^(教师活动|学生活动)\s*\d*\s*[：:]\s*(.*)$")
INTENT_RE = re.compile(r"^(?:环节)?设计意图(?:说明)?\s*[：:]\s*(.*)$")


def parse_teaching_design_markdown(markdown: str) -> TeachingDesignSpec:
    """Map named headings and labeled rows onto the Word-template spec."""
    cleaned = strip_reply_kind_markers(markdown)
    spec = TeachingDesignSpec()
    matches = list(HEADING_RE.finditer(cleaned))
    if not matches:
        spec.leftover = cleaned.strip()
        return spec

    preamble = cleaned[: matches[0].start()].strip()
    if preamble:
        spec.leftover = preamble
        _apply_meta_block(spec, preamble)

    for index, match in enumerate(matches):
        key = HEADING_ALIASES[match.group(1)]
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(cleaned)
        body = cleaned[start:end].strip()
        _assign_section(spec, key, body)
    return spec


def _assign_section(spec: TeachingDesignSpec, key: str, body: str) -> None:
    if key == "meta":
        _apply_meta_block(spec, body)
        return
    if key == "summary":
        spec.summary = body
        return
    if key == "content_analysis":
        spec.content_analysis = body
        return
    if key == "learner_analysis":
        spec.learner_analysis = body
        return
    if key == "objectives":
        spec.objectives = body
        return
    if key == "thinking":
        spec.thinking_source = body
        spec.thinking_points = _parse_thinking_points(body)
        return
    if key == "activities":
        spec.activity_source = body
        spec.activities = _parse_activity_stages(body)
        return
    if key == "structure":
        spec.structure = body
        return
    if key == "board_design":
        spec.board_design = body
        return
    if key == "homework":
        spec.homework = body
        return
    if key == "materials":
        spec.materials = body


def _apply_meta_block(spec: TeachingDesignSpec, body: str) -> None:
    title_match = TITLE_RE.search(body)
    if title_match:
        spec.title = f"《{title_match.group(1).strip()}》教学设计"
    elif not spec.title:
        first_line = body.splitlines()[0].strip() if body.strip() else ""
        if first_line and BARE_TITLE_RE.search(first_line):
            spec.title = first_line
    for match in FIELD_LINE_RE.finditer(body):
        label = match.group(1)
        value = match.group(2).strip()
        if label == "学段年级":
            spec.grade = value
        elif label == "学科":
            spec.subject = value
        elif label == "教材版本":
            spec.textbook = value
        elif label == "课时说明":
            spec.period = value
        elif label == "教师单位":
            spec.school = value
        elif label == "教师姓名":
            spec.teacher = value


def _parse_thinking_points(body: str) -> list[ThinkingPointRow]:
    rows: list[ThinkingPointRow] = []
    current: ThinkingPointRow | None = None
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        labeled = _match_thinking_label(line)
        if labeled is not None:
            category, rest = labeled
            current = ThinkingPointRow(category=category, point=rest)
            rows.append(current)
            continue
        if current is None:
            continue
        intent_match = INTENT_RE.match(line)
        if intent_match:
            current.intent = _join_text(current.intent, intent_match.group(1))
            continue
        current.point = _join_text(current.point, line)
    return rows


def _match_thinking_label(line: str) -> tuple[str, str] | None:
    for label, category in THINKING_LABELS:
        prefix = f"{label}："
        alt_prefix = f"{label}:"
        if line.startswith(prefix):
            return category, line[len(prefix) :].strip()
        if line.startswith(alt_prefix):
            return category, line[len(alt_prefix) :].strip()
        if line == label:
            return category, ""
    return None


def _parse_activity_stages(body: str) -> list[ActivityStage]:
    starts = list(STAGE_RE.finditer(body))
    if not starts:
        return []
    stages: list[ActivityStage] = []
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
        block = body[match.end() : end]
        title = match.group(2).strip() or f"环节{match.group(1)}"
        stages.append(_parse_one_stage(title, block))
    return stages


def _parse_one_stage(title: str, block: str) -> ActivityStage:
    stage = ActivityStage(title=title)
    bucket: str | None = None
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        intent_match = INTENT_RE.match(line)
        if intent_match:
            stage.intent = _join_text(stage.intent, intent_match.group(1))
            bucket = "intent"
            continue
        action_match = ACTION_RE.match(line)
        if action_match:
            role = action_match.group(1)
            text = action_match.group(2).strip()
            if role == "教师活动":
                if text:
                    stage.teacher_actions.append(text)
                bucket = "teacher"
            else:
                if text:
                    stage.student_actions.append(text)
                bucket = "student"
            continue
        if bucket == "teacher":
            _append_or_extend(stage.teacher_actions, line)
        elif bucket == "student":
            _append_or_extend(stage.student_actions, line)
        elif bucket == "intent":
            stage.intent = _join_text(stage.intent, line)
    return stage


def _append_or_extend(items: list[str], line: str) -> None:
    if items:
        items[-1] = _join_text(items[-1], line)
        return
    items.append(line)


def _join_text(existing: str, extra: str) -> str:
    piece = (extra or "").strip()
    if not piece:
        return existing
    if not existing:
        return piece
    return f"{existing}\n{piece}"
