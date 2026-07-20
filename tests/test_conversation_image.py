"""Unit tests for unified Kitty conversation image processing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.knowledge.conversation_image import process_conversation_image
from tests.typing_helpers import mock_await_kwargs


@pytest.mark.asyncio
async def test_process_conversation_image_handdrawn_path() -> None:
    """Vision mind map → outline ingest + library apply."""
    vision = SimpleNamespace(
        is_mindmap=True,
        confidence=0.92,
        reason="radial",
        spec={"topic": "Trees", "children": [{"text": "Oak"}]},
    )
    enhanced = {"topic": "Trees", "children": [{"text": "Oak", "children": []}]}

    with (
        patch(
            "services.knowledge.conversation_image.detect_and_rebuild_mindmap_from_image",
            new=AsyncMock(return_value=vision),
        ),
        patch(
            "services.knowledge.conversation_image.MindMapAgent",
        ) as agent_cls,
        patch(
            "services.knowledge.conversation_image._persist_doc_summary_markdown",
            new=AsyncMock(return_value=42),
        ) as persist_mock,
        patch(
            "services.knowledge.conversation_image.apply_rebuilt_mindmap_to_library",
            new=AsyncMock(return_value={"saved": True, "desktop_queued": True}),
        ) as apply_mock,
    ):
        agent = MagicMock()
        agent.diagram_type = "mind_map"
        agent.validate_output.return_value = (True, "")
        agent.enhance_spec = AsyncMock(return_value=enhanced)
        agent_cls.return_value = agent

        result = await process_conversation_image(
            user_id=1,
            organization_id=None,
            image_bytes=b"fake-image",
            mime_type="image/jpeg",
            filename="map.jpg",
            language="en",
            diagram_id="diag-1",
            diagram_title="My Map",
        )

    assert result["mode"] == "handdrawn"
    assert result["topic"] == "Trees"
    assert result["package_id"] == 42
    assert result["doc_summary_saved"] is True
    assert result["library"]["saved"] is True
    persist_mock.assert_awaited_once()
    assert mock_await_kwargs(persist_mock)["source_kind"] == "handdrawn_mindmap"
    apply_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_conversation_image_ocr_fallback() -> None:
    """Non-mindmap / failed vision → OCR extract path."""
    vision = SimpleNamespace(
        is_mindmap=False,
        confidence=0.8,
        reason="document",
        spec=None,
    )

    with (
        patch(
            "services.knowledge.conversation_image.detect_and_rebuild_mindmap_from_image",
            new=AsyncMock(return_value=vision),
        ),
        patch(
            "services.knowledge.conversation_image._ocr_image_bytes",
            return_value="Hello from photo",
        ),
        patch(
            "services.knowledge.conversation_image._persist_doc_summary_markdown",
            new=AsyncMock(return_value=7),
        ) as persist_mock,
        patch(
            "services.knowledge.conversation_image.apply_rebuilt_mindmap_to_library",
            new=AsyncMock(),
        ) as apply_mock,
    ):
        result = await process_conversation_image(
            user_id=2,
            organization_id=3,
            image_bytes=b"fake-image",
            mime_type="image/png",
            filename="notes.png",
            language="zh",
            diagram_id="diag-2",
        )

    assert result["mode"] == "text"
    assert result["ocr_excerpt"] == "Hello from photo"
    assert result["package_id"] == 7
    assert result["doc_summary_saved"] is True
    persist_mock.assert_awaited_once()
    assert mock_await_kwargs(persist_mock)["source_kind"] == "image_ocr"
    apply_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_conversation_image_requires_diagram_id() -> None:
    """Missing diagram_id is a client error."""
    with pytest.raises(ValueError, match="diagram_id"):
        await process_conversation_image(
            user_id=1,
            organization_id=None,
            image_bytes=b"x",
            mime_type="image/jpeg",
            filename="x.jpg",
            language="zh",
            diagram_id="",
        )


@pytest.mark.asyncio
async def test_process_conversation_image_persist_failure_raises() -> None:
    """Doc Summary persist failure must not look like success."""
    vision = SimpleNamespace(
        is_mindmap=False,
        confidence=0.8,
        reason="document",
        spec=None,
    )
    with (
        patch(
            "services.knowledge.conversation_image.detect_and_rebuild_mindmap_from_image",
            new=AsyncMock(return_value=vision),
        ),
        patch(
            "services.knowledge.conversation_image._ocr_image_bytes",
            return_value="Hello",
        ),
        patch(
            "services.knowledge.conversation_image._persist_doc_summary_markdown",
            new=AsyncMock(return_value=None),
        ),
    ):
        with pytest.raises(RuntimeError, match="Document Summary"):
            await process_conversation_image(
                user_id=2,
                organization_id=None,
                image_bytes=b"fake-image",
                mime_type="image/png",
                filename="notes.png",
                language="zh",
                diagram_id="diag-2",
            )
