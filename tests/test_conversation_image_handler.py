"""Unit tests for Kitty conversation image HTTP handler gates."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from models.domain.auth import User
from services.knowledge.conversation_image_upload import (
    normalize_conversation_image_content_type,
    validate_conversation_image_bytes,
)
from services.kitty.http.conversation_image_handler import kitty_rest_conversation_image
from tests.typing_helpers import as_user, mock_await_kwargs


def _upload(
    *,
    filename: str,
    content: bytes,
    content_type: str | None,
) -> MagicMock:
    """Build an UploadFile-like mock for handler tests."""
    upload = MagicMock()
    upload.filename = filename
    upload.content_type = content_type
    upload.read = AsyncMock(return_value=content)
    return upload


def test_normalize_conversation_image_content_type() -> None:
    """Accept image/jpg and infer type from filename when needed."""
    assert (
        normalize_conversation_image_content_type(
            content_type="image/jpg",
            filename="a.jpg",
        )
        == "image/jpeg"
    )
    assert (
        normalize_conversation_image_content_type(
            content_type="application/octet-stream",
            filename="shot.webp",
        )
        == "image/webp"
    )
    assert (
        normalize_conversation_image_content_type(
            content_type="image/gif",
            filename="notes.gif",
        )
        == ""
    )


def test_validate_conversation_image_bytes() -> None:
    """Empty and oversized bodies raise ValueError."""
    with pytest.raises(ValueError, match="Empty file"):
        validate_conversation_image_bytes(b"")
    with pytest.raises(ValueError, match="Image too large"):
        validate_conversation_image_bytes(b"x" * (10 * 1024 * 1024 + 1))
    validate_conversation_image_bytes(b"ok")


def _kitty_user(user_id: int, organization_id: int | None = None) -> User:
    """Typed User stand-in for handler tests."""
    return as_user(SimpleNamespace(id=user_id, organization_id=organization_id))


@pytest.mark.asyncio
async def test_handler_rejects_unsupported_type() -> None:
    """GIF is not accepted on the conversation image path."""
    with pytest.raises(HTTPException) as exc:
        await kitty_rest_conversation_image(
            _kitty_user(1),
            file=_upload(filename="x.gif", content=b"gif-bytes", content_type="image/gif"),
            diagram_id="diag-1",
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_handler_rejects_empty_and_too_large() -> None:
    """Empty and oversized bodies map to 400 / 413."""
    with pytest.raises(HTTPException) as empty_exc:
        await kitty_rest_conversation_image(
            _kitty_user(1),
            file=_upload(filename="x.jpg", content=b"", content_type="image/jpeg"),
            diagram_id="diag-1",
        )
    assert empty_exc.value.status_code == 400

    huge = b"x" * (10 * 1024 * 1024 + 1)
    with pytest.raises(HTTPException) as large_exc:
        await kitty_rest_conversation_image(
            _kitty_user(1),
            file=_upload(filename="x.jpg", content=huge, content_type="image/jpeg"),
            diagram_id="diag-1",
        )
    assert large_exc.value.status_code == 413


@pytest.mark.asyncio
async def test_handler_happy_path_delegates_to_processor() -> None:
    """Valid upload hits process_conversation_image."""
    payload = {
        "success": True,
        "mode": "text",
        "package_id": 11,
        "doc_summary_saved": True,
        "ocr_excerpt": "hi",
    }
    with patch(
        "services.kitty.http.conversation_image_handler.process_conversation_image",
        new=AsyncMock(return_value=payload),
    ) as process_mock:
        result = await kitty_rest_conversation_image(
            _kitty_user(7, organization_id=3),
            file=_upload(
                filename="notes.png",
                content=b"png-bytes",
                content_type="image/png",
            ),
            language="en",
            diagram_id="diag-9",
            diagram_title="Notes",
            apply_to_library=False,
        )

    assert result is payload
    process_mock.assert_awaited_once()
    kwargs = mock_await_kwargs(process_mock)
    assert kwargs["user_id"] == 7
    assert kwargs["organization_id"] == 3
    assert kwargs["mime_type"] == "image/png"
    assert kwargs["diagram_id"] == "diag-9"
    assert kwargs["apply_to_library"] is False
