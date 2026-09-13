"""Planner checks for the ground-up 思维讲堂 lookahead audit."""

from __future__ import annotations

from scripts.audit_lecture_prefetch_map import BRANCH_ONE_ID, BRANCH_TWO_ID, build_prefetch_mindmap
from scripts.audit_lecture_prefetch_walk import (
    LectureCaption,
    WalkBeat,
    next_lookahead_step,
    planned_prefetch_ids,
    prefetch_walk_checks,
    spoken_lecture_steps,
)


def _caption(step_id: str, kind: str, title: str) -> LectureCaption:
    return LectureCaption(id=step_id, kind=kind, title=title, caption=f"{title} caption")


def test_prefetch_mindmap_has_three_trunks() -> None:
    """The audit map is a topic with three first-level branches."""
    spec = build_prefetch_mindmap()
    nodes = spec["nodes"]
    assert spec["type"] == "mindmap"
    assert len(nodes) == 10
    trunks = [edge["target"] for edge in spec["connections"] if edge["source"] == "topic"]
    assert trunks == [BRANCH_ONE_ID, BRANCH_TWO_ID, "branch-3"]


def test_spoken_steps_drop_empty_captions() -> None:
    """Kitty only prefetches captions the lecture runner would speak."""
    spoken = spoken_lecture_steps(
        [
            {"id": "overview-0", "kind": "overview", "title": "开场", "caption": "先看中心"},
            {"id": "blank", "kind": "branch", "title": "空", "caption": "  "},
            {"id": "branch-1", "kind": "branch", "title": "光反应", "caption": "第一条"},
        ]
    )
    assert [step.id for step in spoken] == ["overview-0", "branch-1"]


def test_branch_one_lookahead_is_the_next_caption() -> None:
    """While branch 1 plays, the planner names branch 2 as the lookahead."""
    steps = [
        _caption("overview-0", "overview", "光合作用"),
        _caption("branch-1", "branch", "光反应"),
        _caption("branch-2", "branch", "暗反应"),
        _caption("branch-3", "branch", "影响因素"),
        _caption("closing", "closing", "收束"),
    ]
    assert next_lookahead_step(steps, 1) == steps[2]
    assert planned_prefetch_ids(steps) == [
        "branch-1",
        "branch-2",
        "branch-3",
        "closing",
        "",
    ]


def test_walk_checks_require_cache_hit_on_slide_after_branch_one() -> None:
    """The audit passes only when the slide after branch 1 plays from cache."""
    steps = [
        _caption("overview-0", "overview", "光合作用"),
        _caption("branch-1", "branch", "光反应"),
        _caption("branch-2", "branch", "暗反应"),
    ]
    beats = [
        WalkBeat(0, "overview-0", "overview", "光合作用", "cache", "branch-1", True, 2, "a.wav"),
        WalkBeat(1, "branch-1", "branch", "光反应", "cache", "branch-2", True, 3, "b.wav"),
        WalkBeat(2, "branch-2", "branch", "暗反应", "cache", "", False, 3, "c.wav"),
    ]
    checks = prefetch_walk_checks(steps, beats)
    assert all(checks.values())
