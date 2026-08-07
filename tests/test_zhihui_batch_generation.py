"""Batch generation order: plan normalize → Wan jobs → resume ranges."""

from __future__ import annotations

import json
from pathlib import Path

from services.zhihui.lesson_deck import iter_batch_resume_ranges
from services.zhihui.lesson_planner import (
    develop_branch_first_seen_texts,
    normalize_lesson_plan_to_outline,
)
from services.zhihui.outline import MindMapBranchOutline, MindMapOutline, extract_mindmap_outline
from services.zhihui.wan_prompt_shell import plan_batches_to_wan_jobs, split_frames_for_wan

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "zhihui_sams_club_l1.json"

EXPECTED_CLOCKWISE = [
    "竞争对手",
    "分布特点",
    "分部特",
    "产品与货品策略",
    "营销聚焦：目标客群与价值主张",
    "新分支",
    "运营与精益管理",
    "店内体验与多渠道",
    "Costco对比",
    "汇源汁商店",
]

EXPECTED_IDS = [
    "branch-r-1-0",
    "branch-r-1-7",
    "branch-r-1-8",
    "branch-r-1-14",
    "branch-r-1-24",
    "branch-l-1-24",
    "branch-l-1-19",
    "branch-l-1-14",
    "branch-l-1-7",
    "branch-l-1-0",
]


def _sams_outline() -> MindMapOutline:
    return extract_mindmap_outline(
        json.loads(FIXTURE.read_text(encoding="utf-8")),
        diagram_type="mindmap",
        fallback_title="山姆会员商店",
    )


def _frame(
    title: str,
    focus_branch: str,
    *,
    frame_role: str = "branch_intro",
    focus_child: str = "",
) -> dict:
    return {
        "title": title,
        "frame_role": frame_role,
        "focus_branch": focus_branch,
        "focus_child": focus_child,
        "lesson_beat": "beat",
        "learning_point": "point",
        "manifestation": "scene",
        "think_prompt": "",
        "visual_subjects": ["a", "b", "c"],
        "cognitive_conflict": False,
    }


def _shuffled_one_batch_per_branch_plan(outline: MindMapOutline) -> dict:
    """One develop batch per branch, deliberately reversed."""
    develop = []
    for branch in reversed(outline.branches):
        branch_key = (branch.id or branch.text or "").strip()
        develop.append(
            {
                "batch_role": "develop",
                "frames": [
                    _frame(f"{branch.text}-intro", branch_key, frame_role="branch_intro"),
                    _frame(
                        f"{branch.text}-child",
                        branch_key,
                        frame_role="child_detail",
                        focus_child="子点",
                    ),
                ],
            }
        )
    return {
        "style_seed": "课堂水彩",
        "batches": [
            {
                "batch_role": "open",
                "frames": [
                    _frame("主题总览", "", frame_role="topic_overview"),
                ],
            },
            *develop,
            {
                "batch_role": "close",
                "frames": [_frame("收束", "", frame_role="synthesis")],
            },
        ],
    }


def test_sams_club_normalize_then_wan_jobs_follow_clockwise() -> None:
    """Shuffled per-branch batches become clockwise Wan jobs for the real .mg."""
    outline = _sams_outline()
    assert [branch.text for branch in outline.branches] == EXPECTED_CLOCKWISE

    plan = normalize_lesson_plan_to_outline(_shuffled_one_batch_per_branch_plan(outline), outline)
    assert develop_branch_first_seen_texts(plan, outline) == EXPECTED_CLOCKWISE

    jobs = plan_batches_to_wan_jobs(plan)
    assert jobs[0]["batch_role"] == "open"
    assert jobs[-1]["batch_role"] == "close"

    develop_jobs = [job for job in jobs if job["batch_role"] == "develop"]
    assert len(develop_jobs) == 10
    for job, branch_id, branch_text in zip(develop_jobs, EXPECTED_IDS, EXPECTED_CLOCKWISE, strict=True):
        assert job["n"] == 2
        assert job["frames"][0]["focus_branch"] == branch_id
        assert job["frames"][0]["frame_role"] == "branch_intro"
        assert job["frames"][1]["frame_role"] == "child_detail"
        assert job["frames"][0]["title"] == f"{branch_text}-intro"


def test_mixed_develop_batch_frames_sorted_before_wan() -> None:
    """Frames inside one develop batch are stable-sorted by clockwise branch."""
    outline = MindMapOutline(
        topic="山姆会员商店",
        branches=[
            MindMapBranchOutline(id=branch_id, text=text)
            for branch_id, text in zip(EXPECTED_IDS, EXPECTED_CLOCKWISE, strict=True)
        ],
    )
    # Single develop batch with branches in reverse + scrambled within pairs.
    frames = []
    for branch_id, text in zip(reversed(EXPECTED_IDS), reversed(EXPECTED_CLOCKWISE), strict=True):
        frames.append(_frame(f"{text}-child", branch_id, frame_role="child_detail", focus_child="x"))
        frames.append(_frame(f"{text}-intro", branch_id, frame_role="branch_intro"))
    plan = {
        "style_seed": "课堂",
        "batches": [
            {"batch_role": "open", "frames": [_frame("开场", "", frame_role="topic_overview")]},
            {"batch_role": "develop", "frames": frames},
            {"batch_role": "close", "frames": [_frame("收束", "", frame_role="close")]},
        ],
    }
    normalized = normalize_lesson_plan_to_outline(plan, outline)
    develop_frames = normalized["batches"][1]["frames"]
    # Clockwise by branch; within each branch child stayed before intro (stable).
    first_seen = []
    for frame in develop_frames:
        hint = frame["focus_branch"]
        if hint not in first_seen:
            first_seen.append(hint)
    assert first_seen == EXPECTED_IDS

    jobs = plan_batches_to_wan_jobs(normalized)
    # Branch-aware packing: never mix focus_branch, so one job per branch (2 frames).
    assert jobs[0]["batch_role"] == "open"
    assert jobs[-1]["batch_role"] == "close"
    develop_jobs = [job for job in jobs if job["batch_role"] == "develop"]
    assert len(develop_jobs) == 10
    assert all(job["n"] == 2 for job in develop_jobs)
    flat_ids = [frame["focus_branch"] for job in develop_jobs for frame in job["frames"]]
    assert flat_ids == [frame["focus_branch"] for frame in develop_frames]
    for job in develop_jobs:
        branch_keys = {frame["focus_branch"] for frame in job["frames"]}
        assert len(branch_keys) == 1
        assert len(job["prompt"]) <= 5000


def test_wan_chunking_preserves_frame_order() -> None:
    """Same-branch frames pack by n≤12 and keep order."""
    frames = [{"title": f"f{index}", "focus_branch": "same"} for index in range(25)]
    chunks = split_frames_for_wan(frames, style_seed="短")
    assert [len(chunk) for chunk in chunks] == [12, 12, 1]
    flat = [frame["title"] for chunk in chunks for frame in chunk]
    assert flat == [f"f{index}" for index in range(25)]


def test_wan_packing_splits_on_branch_boundary() -> None:
    """Different focus_branch never share a Wan job even under n/char limits."""
    frames = [
        _frame("a1", "b1"),
        _frame("a2", "b1"),
        _frame("b1", "b2"),
        _frame("b2", "b2"),
    ]
    jobs = plan_batches_to_wan_jobs(
        {
            "style_seed": "课堂",
            "batches": [{"batch_role": "develop", "frames": frames}],
        }
    )
    assert len(jobs) == 2
    assert [frame["focus_branch"] for frame in jobs[0]["frames"]] == ["b1", "b1"]
    assert [frame["focus_branch"] for frame in jobs[1]["frames"]] == ["b2", "b2"]
    assert all(len(job["prompt"]) <= 5000 for job in jobs)


def test_wan_packing_splits_on_char_budget() -> None:
    """Verbose same-branch frames split before exceeding 5000 chars."""
    long_scene = "具象场景描述" * 200
    frames = [
        {
            "title": f"帧{index}",
            "frame_role": "child_detail",
            "focus_branch": "b1",
            "lesson_beat": long_scene,
            "learning_point": long_scene,
            "manifestation": long_scene,
            "think_prompt": "",
            "visual_subjects": ["a", "b", "c"],
            "cognitive_conflict": False,
        }
        for index in range(4)
    ]
    jobs = plan_batches_to_wan_jobs(
        {
            "style_seed": "课堂水彩风统一扁平",
            "batches": [{"batch_role": "develop", "frames": frames}],
        }
    )
    assert len(jobs) >= 2
    assert sum(job["n"] for job in jobs) == 4
    assert all(len(job["prompt"]) <= 5000 for job in jobs)
    flat = [frame["title"] for job in jobs for frame in job["frames"]]
    assert flat == [f"帧{index}" for index in range(4)]


def test_resume_ranges_match_wan_job_sizes_for_sams_plan() -> None:
    """Resume skip math uses the same frame counts as plan_batches_to_wan_jobs."""
    outline = _sams_outline()
    plan = normalize_lesson_plan_to_outline(_shuffled_one_batch_per_branch_plan(outline), outline)
    jobs = plan_batches_to_wan_jobs(plan)
    counts = [len(job["frames"]) for job in jobs]
    # open(1) + 10*develop(2) + close(1) = 22 slides
    assert sum(counts) == 22
    assert counts == [1] + [2] * 10 + [1]

    # After finishing open + first 3 develop batches (1+2+2+2=7 slides), resume at 7.
    ranges = iter_batch_resume_ranges(counts, resume_slide=7)
    assert ranges[0][2] == 1  # open fully skipped
    assert ranges[1][2] == 2
    assert ranges[2][2] == 2
    assert ranges[3][2] == 2
    assert ranges[4][2] == 0  # next develop starts fresh
    assert all(skip == count for _, _, skip, count in ranges[5:]) is False
    assert ranges[4][0] == 7  # absolute start of 5th batch (0-based index 4)


def test_open_and_close_sandwich_develop_jobs() -> None:
    """Wan job roles stay open → develop… → close after normalize."""
    outline = _sams_outline()
    plan = normalize_lesson_plan_to_outline(_shuffled_one_batch_per_branch_plan(outline), outline)
    roles = [job["batch_role"] for job in plan_batches_to_wan_jobs(plan)]
    assert roles[0] == "open"
    assert roles[-1] == "close"
    assert all(role == "develop" for role in roles[1:-1])
