"""Shared lecture step validation and canvas-tour JSON repair."""

from __future__ import annotations

import asyncio

import pytest

from services.mind_classroom.canvas_tour import (
    contiguous_raw_prefix,
    generate_tour_steps,
    parse_canvas_tour_json,
)
from services.mind_classroom.canvas_tour_chunks import merge_usage, split_each_node_families
from services.mind_classroom.enqueue import TASK_SCRIPT, TASK_SLIDES, _task_name
from services.mind_classroom.steps import MAX_STEPS_DEFAULT, normalize_steps


def test_normalize_steps_caps_and_drops_unknown_ids() -> None:
    """Cap the step list and drop focus ids that are not in the spec."""
    spec = {"nodes": [{"id": "topic"}, {"id": "b1"}]}
    raw = [
        {
            "kind": "overview",
            "title": "Open",
            "caption": "Hello",
            "focus_node_ids": ["topic", "ghost"],
        }
    ] + [
        {"kind": "branch", "title": f"N{index}", "caption": f"C{index}", "focus_node_ids": ["b1"]}
        for index in range(50)
    ]
    steps = normalize_steps(raw, spec=spec, max_steps=MAX_STEPS_DEFAULT)
    assert len(steps) == MAX_STEPS_DEFAULT
    assert steps[0]["focus_node_ids"] == ["topic"]


def test_parse_canvas_tour_json_strips_fence() -> None:
    """Accept fenced JSON from the canvas-tour LLM."""
    raw = """```json
{"steps": [{"kind": "overview", "title": "Hi", "caption": "Welcome"}]}
```"""
    steps = parse_canvas_tour_json(raw)
    assert steps[0]["caption"] == "Welcome"


def test_split_each_node_families_groups_leaves_under_trunk() -> None:
    """Deep walk is chunked as one trunk plus its leaves."""
    nodes = [
        {"id": "topic", "kind": "topic", "stop": "trunk"},
        {"id": "b1", "kind": "branch", "stop": "trunk"},
        {"id": "b1c1", "kind": "branch", "stop": "leaf"},
        {"id": "b1c2", "kind": "branch", "stop": "leaf"},
        {"id": "b2", "kind": "branch", "stop": "trunk"},
        {"id": "b2c1", "kind": "branch", "stop": "leaf"},
    ]
    families = split_each_node_families(nodes)
    assert [[node["id"] for node in family] for family in families] == [
        ["b1", "b1c1", "b1c2"],
        ["b2", "b2c1"],
    ]
    merged = merge_usage({"prompt_tokens": 2, "total_tokens": 5}, {"prompt_tokens": 3, "total_tokens": 4})
    assert merged == {"prompt_tokens": 5, "total_tokens": 9}


@pytest.mark.asyncio
async def test_each_node_families_call_llm_in_parallel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Seven trunks must start seven DashScope calls before any one finishes."""
    started: list[int] = []
    release = asyncio.Event()

    async def _fake_chat(chat: object, *, prompt: str, settings: dict) -> tuple[list[dict], dict]:
        del prompt, settings
        branch = int(getattr(chat, "branch"))
        started.append(branch)
        await release.wait()
        return (
            [{"kind": "branch", "title": f"b{branch}", "caption": "ok", "focus_node_ids": []}],
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    monkeypatch.setattr("services.mind_classroom.canvas_tour._chat_script", _fake_chat)
    tour_nodes = [{"id": "topic", "kind": "topic", "text": "主题", "stop": "trunk"}]
    for index in range(1, 8):
        tour_nodes.append({"id": f"b{index}", "kind": "branch", "text": f"分支{index}", "stop": "trunk"})
    task = asyncio.create_task(
        generate_tour_steps(
            tour_nodes,
            settings={"tour_scope": "each_node"},
            user_id=3,
            organization_id=1,
        )
    )
    for _ in range(40):
        if len(started) == 7:
            break
        await asyncio.sleep(0)
    assert sorted(started) == [1, 2, 3, 4, 5, 6, 7]
    release.set()
    steps, usage = await task
    assert [step["title"] for step in steps] == [f"b{index}" for index in range(1, 8)]
    assert usage == {"prompt_tokens": 7, "completion_tokens": 7, "total_tokens": 14}


@pytest.mark.asyncio
async def test_main_branch_families_call_llm_in_parallel(monkeypatch: pytest.MonkeyPatch) -> None:
    """按主分支 also fans out one DashScope call per L1 trunk."""
    started: list[int] = []
    release = asyncio.Event()

    async def _fake_chat(chat: object, *, prompt: str, settings: dict) -> tuple[list[dict], dict]:
        del prompt, settings
        branch = int(getattr(chat, "branch"))
        started.append(branch)
        await release.wait()
        return (
            [{"kind": "branch", "title": f"b{branch}", "caption": "ok", "focus_node_ids": []}],
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    monkeypatch.setattr("services.mind_classroom.canvas_tour._chat_script", _fake_chat)
    tour_nodes = [{"id": "topic", "kind": "topic", "text": "主题", "stop": "trunk"}]
    for index in range(1, 4):
        tour_nodes.append({"id": f"b{index}", "kind": "branch", "text": f"分支{index}", "stop": "trunk"})
    task = asyncio.create_task(
        generate_tour_steps(
            tour_nodes,
            settings={"tour_scope": "main_branch"},
            user_id=3,
            organization_id=1,
        )
    )
    for _ in range(40):
        if len(started) == 3:
            break
        await asyncio.sleep(0)
    assert sorted(started) == [1, 2, 3]
    release.set()
    steps, usage = await task
    assert [step["title"] for step in steps] == ["b1", "b2", "b3"]
    assert usage == {"prompt_tokens": 3, "completion_tokens": 3, "total_tokens": 6}


@pytest.mark.asyncio
async def test_first_family_persists_before_other_branches_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Opening-family steps hit the manifesto so TTS can start mid-job."""
    persisted = asyncio.Event()
    hold_rest = asyncio.Event()
    saved: list[dict] = []

    async def _fake_chat(chat: object, *, prompt: str, settings: dict) -> tuple[list[dict], dict]:
        del prompt, settings
        branch = int(getattr(chat, "branch"))
        if branch == 1:
            return (
                [{"kind": "overview", "title": "开场", "caption": "欢迎来到这张图"}],
                {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            )
        await hold_rest.wait()
        return (
            [{"kind": "branch", "title": f"b{branch}", "caption": "后到"}],
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    async def _fake_persist(*_args: object, **kwargs: object) -> int:
        payload = kwargs.get("slots")
        if isinstance(payload, list):
            prefix = contiguous_raw_prefix(payload)
            if prefix:
                saved.extend(prefix)
                persisted.set()
            return len(prefix)
        persisted.set()
        return 1

    async def _fake_progress(*_args: object, **_kwargs: object) -> dict:
        raise ConnectionError("database unavailable")

    monkeypatch.setattr("services.mind_classroom.canvas_tour._chat_script", _fake_chat)
    monkeypatch.setattr("services.mind_classroom.canvas_tour.persist_ready_tour_prefix", _fake_persist)
    monkeypatch.setattr("services.mind_classroom.canvas_tour.patch_tour_progress", _fake_progress)
    tour_nodes = [
        {"id": "topic", "kind": "topic", "text": "主题", "stop": "trunk"},
        {"id": "b1", "kind": "branch", "text": "第一支", "stop": "trunk"},
        {"id": "b2", "kind": "branch", "text": "第二支", "stop": "trunk"},
    ]
    task = asyncio.create_task(
        generate_tour_steps(
            tour_nodes,
            settings={"tour_scope": "each_node"},
            user_id=3,
            organization_id=1,
            job_id="job-early-tts",
            spec={"nodes": tour_nodes},
        )
    )
    try:
        await asyncio.wait_for(persisted.wait(), timeout=1)
    except TimeoutError:
        if task.done():
            await task
        raise
    assert saved[0]["kind"] == "overview"
    assert not task.done()
    hold_rest.set()
    steps, _usage = await task
    assert steps[0]["kind"] == "overview"
    assert len(steps) == 2


def test_contiguous_raw_prefix_stops_at_first_hole() -> None:
    """TTS only sees finished families in order; a later hole does not jump ahead."""
    family_a = [{"kind": "overview", "title": "开场"}]
    family_b = [{"kind": "branch", "title": "第二支"}]
    family_c = [{"kind": "branch", "title": "第三支"}]
    assert not contiguous_raw_prefix([None, family_b, family_c])
    assert contiguous_raw_prefix([family_a, None, family_c]) == family_a
    assert contiguous_raw_prefix([family_a, family_b, family_c]) == family_a + family_b + family_c


def test_script_and_slides_use_separate_task_names() -> None:
    """Voice and slides must not share one long Celery task name."""
    assert _task_name("canvas_tour") == TASK_SCRIPT
    assert _task_name("slide_deck") == TASK_SLIDES
    assert TASK_SCRIPT != TASK_SLIDES
