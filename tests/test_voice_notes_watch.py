"""Watch Voice Notes finish helper and HTTP path."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from routers.api.voice_notes_watch import VoiceNotesWatchFinishRequest, voice_notes_watch_finish
from services.features.voice_notes_watch import (
    blank_watch_mindmap_spec,
    default_watch_title,
    finish_watch_voice_note,
    normalize_watch_transcript,
)


def test_default_watch_title_stamp() -> None:
    """Title matches the mobile voice recording_YYYYMMDDHHMM shape."""
    stamp = datetime(2026, 9, 11, 15, 4, tzinfo=timezone.utc)
    assert default_watch_title(stamp) == "voice recording_202609111504"


def test_normalize_watch_transcript_strips_and_clamps() -> None:
    """Empty after strip is empty; long text is clamped."""
    assert normalize_watch_transcript("  \n  ") == ""
    assert normalize_watch_transcript("hello") == "hello"
    huge = "字" * 900_010
    assert len(normalize_watch_transcript(huge)) == 900_000


def test_blank_watch_mindmap_spec_shape() -> None:
    """Placeholder spec has a topic and four branches."""
    spec = blank_watch_mindmap_spec()
    assert spec["topic"] == "中心主题"
    assert len(spec["children"]) == 4
    assert spec["children"][0]["children"][0]["label"].startswith("子项")


def _user() -> MagicMock:
    user = MagicMock()
    user.id = 7
    user.organization_id = 1
    return user


def _request() -> MagicMock:
    request = MagicMock()
    request.headers = {}
    return request


@pytest.mark.asyncio
async def test_finish_watch_ingests_without_generate() -> None:
    """Stop-only finish creates a voice_notes diagram and ingests markdown."""
    cache = MagicMock()
    cache.save_diagram = AsyncMock(return_value=(True, "diag-1", None))
    package = MagicMock()
    package.id = 11

    with (
        patch("services.features.voice_notes_watch.get_diagram_cache", return_value=cache),
        patch("services.features.voice_notes_watch.actor_rls_session") as rls,
        patch("services.features.voice_notes_watch.max_diagrams_for_user", new=AsyncMock(return_value=50)),
        patch("services.features.voice_notes_watch.KnowledgePackageService") as pkg_cls,
        patch("services.features.voice_notes_watch.DocSummaryIngestService") as ingest_cls,
        patch("services.features.voice_notes_watch.schedule_module_activity"),
        patch("services.features.voice_notes_watch.WebContentMindMapAgent") as agent_cls,
    ):
        fake_cm = MagicMock()
        fake_cm.__aenter__ = AsyncMock(return_value=MagicMock())
        fake_cm.__aexit__ = AsyncMock(return_value=False)
        rls.return_value = fake_cm
        pkg_cls.return_value.ensure_doc_summary_session = AsyncMock(return_value=package)
        ingest_cls.return_value.ingest_text = AsyncMock()

        result = await finish_watch_voice_note(
            _user(),
            _request(),
            transcript="会议先定三个目标",
            generate=False,
        )

    assert result.diagram_id == "diag-1"
    assert result.generated is False
    agent_cls.assert_not_called()
    ingest_cls.return_value.ingest_text.assert_awaited_once()
    save_call = cache.save_diagram.await_args
    ingest_call = ingest_cls.return_value.ingest_text.await_args
    assert save_call is not None
    assert ingest_call is not None
    assert save_call.kwargs["source_channel"] == "voice_notes"
    assert save_call.kwargs["diagram_type"] == "mindmap"
    ingested = ingest_call.kwargs["content"]
    assert "会议先定三个目标" in ingested
    assert "mg-voice-notes:1" in ingested
    assert ingest_call.kwargs["source_kind"] == "voice_notes"


@pytest.mark.asyncio
async def test_finish_watch_generate_persists_spec() -> None:
    """Generate path writes the LLM spec back onto the same diagram."""
    cache = MagicMock()
    cache.save_diagram = AsyncMock(
        side_effect=[
            (True, "diag-2", None),
            (True, "diag-2", None),
        ]
    )
    cache.get_diagram = AsyncMock(
        return_value={
            "id": "diag-2",
            "title": "voice recording_202609111504",
            "diagram_type": "mindmap",
            "language": "zh",
            "thumbnail": None,
        }
    )
    package = MagicMock()
    package.id = 22
    agent = MagicMock()
    agent.generate_from_page_content = AsyncMock(
        return_value={"success": True, "spec": {"topic": "目标", "children": []}}
    )

    with (
        patch("services.features.voice_notes_watch.get_diagram_cache", return_value=cache),
        patch("services.features.voice_notes_watch.actor_rls_session") as rls,
        patch("services.features.voice_notes_watch.max_diagrams_for_user", new=AsyncMock(return_value=50)),
        patch("services.features.voice_notes_watch.KnowledgePackageService") as pkg_cls,
        patch("services.features.voice_notes_watch.DocSummaryIngestService") as ingest_cls,
        patch("services.features.voice_notes_watch.schedule_module_activity"),
        patch("services.features.voice_notes_watch.WebContentMindMapAgent", return_value=agent),
    ):
        fake_cm = MagicMock()
        fake_cm.__aenter__ = AsyncMock(return_value=MagicMock())
        fake_cm.__aexit__ = AsyncMock(return_value=False)
        rls.return_value = fake_cm
        pkg_cls.return_value.ensure_doc_summary_session = AsyncMock(return_value=package)
        ingest_cls.return_value.ingest_text = AsyncMock()

        result = await finish_watch_voice_note(
            _user(),
            _request(),
            transcript="会议先定三个目标",
            generate=True,
        )

    assert result.generated is True
    assert cache.save_diagram.await_count == 2
    persist_kwargs = cache.save_diagram.await_args_list[1].kwargs
    assert persist_kwargs["spec"]["topic"] == "目标"


@pytest.mark.asyncio
async def test_finish_watch_rejects_empty_transcript() -> None:
    """Whitespace-only transcript is a client error."""
    with pytest.raises(ValueError, match="empty"):
        await finish_watch_voice_note(_user(), _request(), transcript="   ")


@pytest.mark.asyncio
async def test_watch_finish_route_maps_value_error() -> None:
    """Router turns empty-transcript ValueError into HTTP 400."""
    with patch(
        "routers.api.voice_notes_watch.finish_watch_voice_note",
        new=AsyncMock(side_effect=ValueError("Transcript is empty")),
    ):
        with pytest.raises(HTTPException) as exc:
            await voice_notes_watch_finish(
                VoiceNotesWatchFinishRequest(transcript="x"),
                _request(),
                _user(),
            )
    assert exc.value.status_code == 400
    assert exc.value.detail == "Transcript is empty"
