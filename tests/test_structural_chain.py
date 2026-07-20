"""Unit tests for multi-structural mutation chain helpers."""

from __future__ import annotations

from services.diagram_edit.effects import refresh_session_diagram_data_from_evidence
from services.kitty.routing.structural_chain import (
    build_structural_steps,
    collect_created_branch,
    filter_autocomplete_after_deferred,
    peel_chain_from_command,
    render_multi_step_done,
    render_multi_step_progress,
    split_structural_follow_ups,
)


def test_split_structural_follow_ups_peels_add_nodes() -> None:
    """add_node follow-ups peel into structural; autocomplete stays deferred."""
    structural, rest = split_structural_follow_ups(
        [
            {"action": "add_node", "target": "running"},
            {"action": "add_node", "target": "jumping"},
            {"action": "auto_complete_branch", "target": "running"},
            {"action": "auto_complete"},
        ]
    )
    assert [item["target"] for item in structural] == ["running", "jumping"]
    assert [item["action"] for item in rest] == ["auto_complete_branch", "auto_complete"]


def test_peel_chain_from_command_marks_multi() -> None:
    """Primary plus structural follow-ups become a multi-step chain."""
    command = {
        "action": "update_center",
        "target": "student sport",
        "follow_up_actions": [
            {"action": "add_node", "target": "running"},
            {"action": "add_node", "target": "jumping"},
        ],
    }
    follow = list(command["follow_up_actions"])
    steps, autocomplete, multi = peel_chain_from_command(command, follow)
    assert multi is True
    assert len(steps) == 3
    assert steps[0]["action"] == "update_center"
    assert "follow_up_actions" not in steps[0]
    assert steps[1]["target"] == "running"
    assert steps[2]["target"] == "jumping"
    assert autocomplete == []


def test_build_structural_steps_single() -> None:
    """Single structural command yields one step list entry."""
    steps = build_structural_steps({"action": "add_node", "target": "A"}, [])
    assert len(steps) == 1
    assert steps[0]["target"] == "A"


def test_collect_created_branch_from_applied_ops() -> None:
    """Created branch label/id are recovered from applied ops."""
    created = collect_created_branch(
        {"action": "add_node", "target": "climbing"},
        [{"op": "add_branch", "text": "climbing", "node_id": "branch-r-1-2"}],
    )
    assert created == {"label": "climbing", "node_id": "branch-r-1-2"}


def test_refresh_session_diagram_data_from_evidence() -> None:
    """Session diagram_data is replaced from mutation evidence payload."""
    ctx: dict = {"diagram_data": {"center": {"text": "Cars"}, "children": []}}
    refresh_session_diagram_data_from_evidence(
        ctx,
        {
            "nodes": [{"id": "topic", "text": "Cars"}, {"id": "branch-r-1-0", "text": "DIY"}],
            "connections": [{"source": "topic", "target": "branch-r-1-0"}],
        },
    )
    diagram = ctx["diagram_data"]
    assert isinstance(diagram, dict)
    assert len(diagram["nodes"]) == 2
    assert len(diagram["connections"]) == 1


def test_multi_step_ack_templates() -> None:
    """Progress/done ack strings cover topic, branches, and locale variants."""
    progress = render_multi_step_progress(
        lang="zh",
        topic="",
        branch_labels=["A", "B", "C", "D"],
    )
    assert progress == "好的，正在添加「A」、「B」、「C」、「D」…"

    progress_topic = render_multi_step_progress(
        lang="zh",
        topic="学生运动",
        branch_labels=["跑步", "跳跃", "攀爬", "下蹲"],
    )
    assert progress_topic == ("好的，正在把主题改为「学生运动」，并添加「跑步」、「跳跃」、「攀爬」、「下蹲」…")

    progress_en = render_multi_step_progress(
        lang="en",
        topic="",
        branch_labels=["A", "B", "C", "D"],
    )
    assert progress_en == 'OK — adding "A", "B", "C", and "D"…'

    done = render_multi_step_done(
        lang="zh",
        topic="",
        branch_labels=["A", "B", "C", "D"],
        completing=True,
    )
    assert done == "「A」、「B」、「C」、「D」已经加好了，开始为它们自动补全…"

    done_topic = render_multi_step_done(
        lang="zh",
        topic="学生运动",
        branch_labels=["跑步", "跳跃"],
        completing=True,
    )
    assert done_topic == ("主题已改为「学生运动」，「跑步」、「跳跃」已经加好了，开始为它们自动补全…")

    done_en = render_multi_step_done(
        lang="en",
        topic="",
        branch_labels=["A", "B", "C", "D"],
        completing=True,
    )
    assert done_en == ('"A", "B", "C", and "D" are ready. Starting auto-complete for them…')

    done_only = render_multi_step_done(
        lang="zh",
        topic="",
        branch_labels=["跑步", "跳跃"],
        completing=False,
    )
    assert done_only == "「跑步」、「跳跃」已经加好了。"
    assert "自动补全" not in done_only

    mixed = render_multi_step_done(
        lang="zh",
        topic="",
        branch_labels=["新分支"],
        completing=False,
        updated_labels=["旧名"],
        deleted_labels=["多余"],
    )
    assert mixed == "「新分支」已经加好了，已改名「旧名」，已删除「多余」。"


def test_filter_autocomplete_after_deferred_keeps_existing_branch() -> None:
    """Deferred fills cover new branches; existing-branch AC and whole-map skip."""
    created = [{"label": "跑步", "node_id": "n1"}, {"label": "跳跃", "node_id": "n2"}]
    kept = filter_autocomplete_after_deferred(
        [
            {"action": "auto_complete_branch", "target": "跑步"},
            {"action": "auto_complete_branch", "target": "已有分支"},
            {"action": "auto_complete"},
        ],
        created_branches=created,
        completing=True,
    )
    assert kept == [{"action": "auto_complete_branch", "target": "已有分支"}]


def test_filter_autocomplete_after_deferred_keeps_whole_map_without_fills() -> None:
    """Whole-map auto_complete stays when no deferred branch fills ran."""
    kept = filter_autocomplete_after_deferred(
        [{"action": "auto_complete"}],
        created_branches=[],
        completing=False,
    )
    assert kept == [{"action": "auto_complete"}]
