"""Typed spec for filling the BNU thinking-classroom teaching-design DOCX."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ThinkingPointRow:
    """One 思维训练点 table row."""

    category: str
    point: str = ""
    intent: str = ""


@dataclass
class ActivityStage:
    """One 学习活动设计 stage (环节)."""

    title: str
    teacher_actions: list[str] = field(default_factory=list)
    student_actions: list[str] = field(default_factory=list)
    intent: str = ""


@dataclass
class TeachingDesignSpec:
    """Mapped teaching-design fields for the official Word template."""

    title: str = ""
    grade: str = ""
    subject: str = ""
    textbook: str = ""
    period: str = ""
    school: str = ""
    teacher: str = ""
    summary: str = ""
    content_analysis: str = ""
    learner_analysis: str = ""
    objectives: str = ""
    structure: str = ""
    board_design: str = ""
    homework: str = ""
    materials: str = ""
    thinking_source: str = ""
    activity_source: str = ""
    leftover: str = ""
    thinking_points: list[ThinkingPointRow] = field(default_factory=list)
    activities: list[ActivityStage] = field(default_factory=list)

    def filled_prose_count(self) -> int:
        """Count core prose sections that already have text."""
        blocks = (
            self.summary,
            self.content_analysis,
            self.learner_analysis,
            self.objectives,
        )
        return sum(1 for block in blocks if block.strip())

    def needs_llm_fill(self) -> bool:
        """True when heading parse left gaps that a mapping call should fill."""
        has_meta = bool(self.title.strip() or self.subject.strip() or self.grade.strip())
        if not has_meta and self.filled_prose_count() == 0 and not self.activities:
            return True
        if self.activity_source.strip() and not self.activities:
            return True
        if self.thinking_source.strip() and not self.thinking_points:
            return True
        return self.filled_prose_count() < 2
