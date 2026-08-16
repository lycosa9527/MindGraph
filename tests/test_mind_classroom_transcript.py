"""Lecture markdown transcript render, keys, and COS attach."""

from __future__ import annotations

import pytest

from services.mind_classroom.storage_keys import (
    build_transcript_key,
    is_classroom_logical_key,
    job_id_from_transcript_key,
)
from services.mind_classroom.transcript_md import render_transcript_markdown
from services.mind_classroom.transcript_persist import (
    attach_transcript_md,
    ensure_transcript_on_server,
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
