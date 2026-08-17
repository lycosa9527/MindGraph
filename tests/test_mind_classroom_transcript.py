"""Lecture markdown transcript render, keys, and COS attach."""

from __future__ import annotations

import pytest

from services.mind_classroom.storage_keys import (
    build_transcript_key,
    is_classroom_logical_key,
    job_id_from_transcript_key,
    parse_diagram_transcript_key,
)
from services.mind_classroom.transcript_md import render_transcript_markdown
from services.mind_classroom.transcript_persist import (
    attach_transcript_md,
    ensure_transcript_on_server,
    plan_transcript_replacement,
    transcript_key_from_result,
)


def test_transcript_key_round_trip() -> None:
    """Job id is recoverable from the markdown object key."""
    job_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    key = build_transcript_key(job_id)
    assert key == f"mind_classroom/transcripts/{job_id}.md"
    assert is_classroom_logical_key(key)
    assert job_id_from_transcript_key(key) == job_id
    assert is_classroom_logical_key("mind_classroom/generations/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.png")
    assert not is_classroom_logical_key("mind_classroom/transcripts/../secret.md")


def test_render_transcript_markdown_includes_captions() -> None:
    """Markdown is the archived script; captions are the spoken lines."""
    text = render_transcript_markdown(
        job_id="job-1",
        settings={"mode": "canvas_tour", "mastery": "review", "tone": "fast", "language": "zh"},
        steps=[
            {
                "kind": "overview",
                "title": "光合作用",
                "caption": "先看整张图。",
                "bullets": ["光反应", "暗反应"],
                "focus_node_ids": ["topic"],
            }
        ],
    )
    assert "# Mind Classroom script / lesson plan" in text
    assert "mastery: review" in text
    assert "tone: fast" in text
    assert "## 1. overview · 光合作用" in text
    assert "先看整张图。" in text
    assert "- 光反应" in text


@pytest.mark.asyncio
async def test_attach_transcript_md_sets_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Successful upload stores transcript_key on result_json."""

    async def fake_put(logical_key: str, data: bytes, *, content_type: str | None = None) -> str:
        assert logical_key.endswith(".md")
        assert b"overview" in data
        assert content_type and "markdown" in content_type
        return logical_key

    monkeypatch.setattr("services.mind_classroom.transcript_persist.put_local_and_cos", fake_put)
    job_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    result = await attach_transcript_md(
        job_id=job_id,
        settings={"mode": "canvas_tour"},
        steps=[{"kind": "overview", "title": "Hi", "caption": "Hello"}],
        result_json={"steps": [{"kind": "overview"}]},
    )
    assert result["transcript_uploaded"] is True
    assert result["transcript_key"] == build_transcript_key(job_id)
    assert transcript_key_from_result(result) == result["transcript_key"]


@pytest.mark.asyncio
async def test_attach_transcript_md_survives_upload_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """COS failure must not drop the in-memory steps."""

    async def boom(_logical_key: str, _data: bytes, *, content_type: str | None = None) -> str:
        raise RuntimeError("cos down")

    monkeypatch.setattr("services.mind_classroom.transcript_persist.put_local_and_cos", boom)
    result = await attach_transcript_md(
        job_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        settings={},
        steps=[{"kind": "overview", "caption": "Hello"}],
        result_json={"steps": [{"caption": "Hello"}]},
    )
    assert result["transcript_uploaded"] is False
    assert "transcript_key" not in result
    assert result["steps"][0]["caption"] == "Hello"


@pytest.mark.asyncio
async def test_ensure_transcript_on_server_hydrates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Return visits pull the markdown from COS onto this server."""
    seen: list[str] = []

    async def fake_hydrate(logical_key: str) -> bytes:
        seen.append(logical_key)
        return b"# transcript\n"

    monkeypatch.setattr(
        "services.mind_classroom.transcript_persist.hydrate_local_from_cos",
        fake_hydrate,
    )
    job_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    key = build_transcript_key(job_id)
    await ensure_transcript_on_server({"transcript_key": key, "steps": []})
    assert seen == [key]


def test_transcript_key_stable_per_diagram() -> None:
    """Library maps keep one replaceable markdown backup per user+diagram+mode."""
    job_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    diagram_id = "11111111-2222-3333-4444-555555555555"
    key = build_transcript_key(
        job_id,
        user_id=7,
        diagram_id=diagram_id,
        mode="slide_deck",
    )
    assert key == f"mind_classroom/transcripts/7/{diagram_id}/slide_deck.md"
    assert is_classroom_logical_key(key)
    assert job_id_from_transcript_key(key) is None
    assert parse_diagram_transcript_key(key) == (7, diagram_id, "slide_deck", "")


def test_transcript_key_isolates_llm_slots() -> None:
    """Qwen and DeepSeek lectures must not share one markdown backup."""
    job_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    diagram_id = "11111111-2222-3333-4444-555555555555"
    qwen = build_transcript_key(
        job_id,
        user_id=7,
        diagram_id=diagram_id,
        mode="canvas_tour",
        llm_model="qwen",
    )
    deepseek = build_transcript_key(
        job_id,
        user_id=7,
        diagram_id=diagram_id,
        mode="canvas_tour",
        llm_model="deepseek",
    )
    assert qwen == f"mind_classroom/transcripts/7/{diagram_id}/canvas_tour/qwen.md"
    assert deepseek == f"mind_classroom/transcripts/7/{diagram_id}/canvas_tour/deepseek.md"
    assert qwen != deepseek
    assert is_classroom_logical_key(qwen)
    assert parse_diagram_transcript_key(qwen) == (7, diagram_id, "canvas_tour", "qwen")
    assert not is_classroom_logical_key(f"mind_classroom/transcripts/7/{diagram_id}/../secret.md")


def test_plan_transcript_replacement_deletes_old_job_file() -> None:
    """A new generation drops the previous job-id markdown and clears its pointer."""
    keep_key = "mind_classroom/transcripts/7/11111111-2222-3333-4444-555555555555/canvas_tour.md"
    old_key = "mind_classroom/transcripts/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.md"
    stale_keys, updates = plan_transcript_replacement(
        current_job_id="new-job",
        keep_key=keep_key,
        siblings=[
            ("old-job", {"transcript_key": old_key, "steps": [{"kind": "overview"}]}),
            ("new-job", {"transcript_key": keep_key}),
        ],
    )
    assert stale_keys == [old_key]
    assert len(updates) == 1
    assert updates[0][0] == "old-job"
    assert "transcript_key" not in updates[0][1]
    assert updates[0][1]["transcript_replaced"] is True
    assert updates[0][1]["steps"][0]["kind"] == "overview"


def test_plan_transcript_replacement_keeps_shared_stable_key() -> None:
    """Overwriting the same COS path must not delete the file being replaced."""
    keep_key = "mind_classroom/transcripts/7/11111111-2222-3333-4444-555555555555/canvas_tour.md"
    stale_keys, updates = plan_transcript_replacement(
        current_job_id="new-job",
        keep_key=keep_key,
        siblings=[("old-job", {"transcript_key": keep_key, "steps": []})],
    )
    assert not stale_keys
    assert "transcript_key" not in updates[0][1]


@pytest.mark.asyncio
async def test_attach_transcript_md_uses_diagram_backup_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Diagram-backed jobs write one .md path and retire the previous backup."""
    put_keys: list[str] = []
    retired: list[dict[str, object]] = []
    order: list[str] = []

    async def fake_put(logical_key: str, data: bytes, *, content_type: str | None = None) -> str:
        assert logical_key.endswith(".md")
        assert b"diagram_id:" in data
        assert content_type and "markdown" in content_type
        put_keys.append(logical_key)
        order.append("put")
        return logical_key

    async def fake_retire(**kwargs: object) -> None:
        order.append("retire")
        retired.append(kwargs)

    monkeypatch.setattr("services.mind_classroom.transcript_persist.put_local_and_cos", fake_put)
    monkeypatch.setattr(
        "services.mind_classroom.transcript_persist.retire_superseded_transcripts",
        fake_retire,
    )
    job_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    diagram_id = "11111111-2222-3333-4444-555555555555"
    result = await attach_transcript_md(
        job_id=job_id,
        settings={"mode": "canvas_tour"},
        steps=[{"kind": "overview", "title": "Hi", "caption": "Hello"}],
        result_json={"steps": [{"kind": "overview"}]},
        user_id=7,
        diagram_id=diagram_id,
    )
    expected = build_transcript_key(
        job_id,
        user_id=7,
        diagram_id=diagram_id,
        mode="canvas_tour",
    )
    assert result["transcript_uploaded"] is True
    assert result["transcript_key"] == expected
    assert put_keys == [expected]
    assert order == ["put", "retire"]
    assert retired[0]["keep_key"] == expected
    assert retired[0]["job_id"] == job_id
