"""Sticky merge for parallel canvas-tour job progress."""

from __future__ import annotations

from services.mind_classroom.tour_progress import merge_tour_progress, seed_branch_slots


def test_seed_branch_slots_are_pending() -> None:
    """Each family starts pending so the button can name the first one."""
    slots = seed_branch_slots(["光合作用", "呼吸作用"])
    assert [slot["index"] for slot in slots] == [1, 2]
    assert slots[0]["state"] == "pending"
    assert slots[1]["label"] == "呼吸作用"


def test_merge_keeps_tts_ready_when_another_branch_streams() -> None:
    """A late first-token must not wipe first-branch TTS unlock."""
    seeded = merge_tour_progress(None, phase="script_parallel", seed_labels=["开场", "第二支"])
    first_ready = merge_tour_progress(
        seeded,
        phase="first_branch",
        branch=1,
        branch_state="done",
        branch_label="开场",
        tts_ready=True,
        step_count=3,
    )
    late_stream = merge_tour_progress(
        first_ready,
        phase="llm_streaming",
        branch=2,
        branch_state="streaming",
        branch_label="第二支",
        chars=40,
        tts_ready=False,
    )
    assert late_stream["tts_ready"] is True
    assert late_stream["step_count"] == 3
    assert late_stream["done"] == 1
    assert late_stream["in_flight"] == 1
    assert late_stream["branch_label"] == "第二支"
    assert late_stream["branches"][0]["state"] == "done"
    assert late_stream["branches"][1]["state"] == "streaming"


def test_merge_display_prefers_lowest_streaming_not_last_writer() -> None:
    """Button name stays on the first still-writing family."""
    seeded = merge_tour_progress(
        None,
        phase="script_parallel",
        seed_labels=["第一支", "第二支", "第三支"],
    )
    second = merge_tour_progress(
        seeded,
        phase="llm_streaming",
        branch=2,
        branch_state="streaming",
        branch_label="第二支",
    )
    first = merge_tour_progress(
        second,
        phase="llm_streaming",
        branch=1,
        branch_state="streaming",
        branch_label="第一支",
    )
    assert first["branch"] == 1
    assert first["branch_label"] == "第一支"


def test_merge_does_not_regress_done_to_streaming() -> None:
    """A delayed stream publish cannot reopen a finished family."""
    done = merge_tour_progress(
        merge_tour_progress(None, phase="script_parallel", seed_labels=["开场"]),
        phase="first_branch",
        branch=1,
        branch_state="done",
        tts_ready=True,
    )
    replay = merge_tour_progress(
        done,
        phase="llm_streaming",
        branch=1,
        branch_state="streaming",
        chars=12,
    )
    assert replay["branches"][0]["state"] == "done"
    assert replay["tts_ready"] is True
