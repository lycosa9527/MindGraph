"""Unit tests for unified Kitty conversation image processing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
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
async def test_process_conversation_image_canvas_only_handdrawn() -> None:
    """Empty diagram_id returns rebuilt spec without Doc Summary / library."""
    vision = SimpleNamespace(
        is_mindmap=True,
        confidence=0.91,
        reason="radial",
        spec={"topic": "Sky", "children": [{"text": "Cloud"}]},
    )
    enhanced = {"topic": "Sky", "children": [{"text": "Cloud"}]}

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
            new=AsyncMock(),
        ) as apply_mock,
    ):
        agent = MagicMock()
        agent.diagram_type = "mindmap"
        agent.validate_output.return_value = (True, "")
        agent.enhance_spec = AsyncMock(return_value=enhanced)
        agent_cls.return_value = agent

        result = await process_conversation_image(
            user_id=1,
            organization_id=None,
            image_bytes=b"fake-image",
            mime_type="image/jpeg",
            filename="map.jpg",
            language="zh",
            diagram_id="",
            apply_to_library=True,
        )

    assert result["mode"] == "handdrawn"
    assert result["topic"] == "Sky"
    assert result["spec"] == enhanced
    assert result["package_id"] is None
    assert result["doc_summary_saved"] is False
    assert result["library"] == {}
    persist_mock.assert_not_awaited()
    apply_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_conversation_image_canvas_only_not_mindmap() -> None:
    """Canvas-only import rejects images that are not hand-drawn mind maps."""
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
            return_value="should not run",
        ),
        patch(
            "services.knowledge.conversation_image._persist_doc_summary_markdown",
            new=AsyncMock(return_value=7),
        ) as persist_mock,
    ):
        with pytest.raises(ValueError, match="No hand-drawn mind map detected"):
            await process_conversation_image(
                user_id=1,
                organization_id=None,
                image_bytes=b"fake-image",
                mime_type="image/jpeg",
                filename="notes.jpg",
                language="zh",
                diagram_id="",
            )
    persist_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_conversation_image_canvas_only_unauthorized() -> None:
    """Canvas-only import surfaces DashScope 401 as an actionable error."""
    request = httpx.Request("POST", "https://dashscope.aliyuncs.com/api/v1/x")
    response = httpx.Response(401, request=request)
    with patch(
        "services.knowledge.conversation_image.detect_and_rebuild_mindmap_from_image",
        new=AsyncMock(side_effect=httpx.HTTPStatusError("401", request=request, response=response)),
    ):
        with pytest.raises(ValueError, match="QWEN_API_KEY"):
            await process_conversation_image(
                user_id=1,
                organization_id=None,
                image_bytes=b"fake-image",
                mime_type="image/jpeg",
                filename="map.jpg",
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


@pytest.mark.asyncio
async def test_process_conversation_image_canvas_review_returns_typed_spec() -> None:
    """Toolbar import waits for a manual confirm and does not write the library."""
    vision = SimpleNamespace(
        recognized=True,
        diagram_type="flow_map",
        confidence=0.95,
        reason="chain",
        spec={"title": "接收SSTV", "steps": ["准备阶段"], "substeps": []},
        topic="接收SSTV",
    )
    with (
        patch(
            "services.knowledge.conversation_image.detect_and_rebuild_diagram_from_image",
            new=AsyncMock(return_value=vision),
        ) as detect_mock,
        patch(
            "services.knowledge.conversation_image.detect_and_rebuild_mindmap_from_image",
            new=AsyncMock(),
        ) as mindmap_mock,
        patch(
            "services.knowledge.conversation_image._persist_doc_summary_markdown",
            new=AsyncMock(return_value=7),
        ) as persist_mock,
    ):
        result = await process_conversation_image(
            user_id=1,
            organization_id=None,
            image_bytes=b"fake-image",
            mime_type="image/png",
            filename="flow.png",
            language="zh",
            diagram_id="",
            canvas_review=True,
        )
    assert result["mode"] == "review"
    assert result["diagram_type"] == "flow_map"
    assert result["spec"]["title"] == "接收SSTV"
    assert result["doc_summary_saved"] is False
    detect_mock.assert_awaited()
    mindmap_mock.assert_not_awaited()
    persist_mock.assert_not_awaited()
