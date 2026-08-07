"""Regression: real 山姆会员商店 .mg L1 clockwise order."""

from __future__ import annotations

import json
from pathlib import Path

from services.zhihui.lesson_planner import (
    develop_branch_first_seen_texts,
    normalize_lesson_plan_to_outline,
    reorder_develop_batches_to_outline,
)
from services.zhihui.outline import MindMapBranchOutline, MindMapOutline, extract_mindmap_outline
from services.zhihui.wan_prompt_shell import plan_batches_to_wan_jobs

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "zhihui_sams_club_l1.json"

# From user export 山姆会员商店_2026-08-07.mg — right top→bottom, left bottom→top.
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


def test_real_sams_club_mg_l1_clockwise_order() -> None:
    """Fixture trimmed from the user .mg export must stay clockwise."""
    spec = json.loads(FIXTURE.read_text(encoding="utf-8"))
    outline = extract_mindmap_outline(spec, diagram_type="mindmap", fallback_title="山姆会员商店")
    assert outline.topic == "山姆会员商店"
    assert [branch.text for branch in outline.branches] == EXPECTED_CLOCKWISE
    assert [branch.id for branch in outline.branches] == EXPECTED_IDS
    # Connection order on disk is NOT the teaching order (left after right, but left top→bottom).
    conn_order = [conn["target"] for conn in spec["connections"] if conn.get("source") == "topic"]
    assert conn_order != EXPECTED_IDS
    assert conn_order[:5] == EXPECTED_IDS[:5]
    assert conn_order[5:] == list(reversed(EXPECTED_IDS[5:]))


def test_real_sams_club_planner_reorder_matches_outline() -> None:
    """Shuffled develop batches are restored to the .mg clockwise order."""
    outline = MindMapOutline(
        topic="山姆会员商店",
        branches=[
            MindMapBranchOutline(id=branch_id, text=text)
            for branch_id, text in zip(EXPECTED_IDS, EXPECTED_CLOCKWISE, strict=True)
        ],
    )
    shuffled = list(reversed(EXPECTED_CLOCKWISE))
    plan = {
        "style_seed": "课堂",
        "batches": [{"batch_role": "open", "frames": [{"title": "开场"}]}]
        + [{"batch_role": "develop", "frames": [{"title": text, "focus_branch": text}]} for text in shuffled]
        + [{"batch_role": "close", "frames": [{"title": "收束"}]}],
    }
    reordered = reorder_develop_batches_to_outline(plan, outline)
    titles = [batch["frames"][0]["title"] for batch in reordered["batches"] if batch.get("batch_role") == "develop"]
    assert titles == EXPECTED_CLOCKWISE
    assert develop_branch_first_seen_texts(reordered, outline) == EXPECTED_CLOCKWISE
    jobs = plan_batches_to_wan_jobs(normalize_lesson_plan_to_outline(plan, outline))
    develop_titles = [job["frames"][0]["title"] for job in jobs if job.get("batch_role") == "develop"]
    assert develop_titles == EXPECTED_CLOCKWISE
