"""Library diagram embed: render PNG, store on COS, return download markdown URL."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.features.workshop_chat.diagram_embed import (
    load_library_diagram_spec,
    png_filename_from_title,
    store_library_diagram_png,
)
from tests.typing_helpers import as_type, mock_await_kwargs


def test_png_filename_from_title_keeps_cjk() -> None:
    """Chinese titles stay in the basename."""
    assert png_filename_from_title("背影") == "背影.png"
    assert png_filename_from_title("  a/b  ") == "a_b.png"


@pytest.mark.asyncio
async def test_load_library_diagram_spec() -> None:
    """Cache hit returns spec, type, and title."""
    record = {"spec": {"topic": "背影"}, "diagram_type": "mindmap", "title": "背影"}
    cache = SimpleNamespace(get_diagram=AsyncMock(return_value=record))
    with patch(
        "services.features.workshop_chat.diagram_embed.get_diagram_cache",
        return_value=cache,
    ):
        spec, diagram_type, title = await load_library_diagram_spec(
            3,
            "d1d7a7fc-eaa1-436d-abd2-2a7b1230c537",
        )
    assert spec == {"topic": "背影"}
    assert diagram_type == "mindmap"
    assert title == "背影"


@pytest.mark.asyncio
async def test_load_library_diagram_missing() -> None:
    """Unknown library ids raise LookupError."""
    cache = SimpleNamespace(get_diagram=AsyncMock(return_value=None))
    with (
        patch(
            "services.features.workshop_chat.diagram_embed.get_diagram_cache",
            return_value=cache,
        ),
        pytest.raises(LookupError, match="Diagram not found"),
    ):
        await load_library_diagram_spec(3, "missing")


@pytest.mark.asyncio
async def test_store_library_diagram_png() -> None:
    """Rendered bytes are persisted as a draft attachment."""
    png = b"\x89PNG" + b"x" * 80
    stored = {
        "file_path": "/api/chat/attachments/9/download",
        "filename": "背影.png",
    }
    with patch(
        "services.features.workshop_chat.diagram_embed.FileService.save_png_bytes",
        new=AsyncMock(return_value=stored),
    ) as save:
        result = await store_library_diagram_png(
            as_type(SimpleNamespace(), AsyncSession),
            3,
            "背影",
            png,
            "d1d7a7fc-eaa1-436d-abd2-2a7b1230c537",
        )
    assert result == stored
    save.assert_awaited_once()
    save_kwargs = mock_await_kwargs(save)
    assert save_kwargs["uploader_id"] == 3
    assert save_kwargs["data"] == png
    assert save_kwargs["filename"] == "背影.png"
