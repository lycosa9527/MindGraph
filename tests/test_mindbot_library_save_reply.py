"""Tests for MindBot library save notice injection."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.mindbot.diagram.library_save_reply import (
    answer_has_library_diagram_uuid,
    answer_has_library_save_skip_notice,
    enrich_dingtalk_reply_with_library_save_notice,
    extract_dingtalk_preview_unique_id,
    extract_prepended_library_save_notice,
)


def test_extract_dingtalk_preview_unique_id() -> None:
    """Parse unique id from temp preview URL."""
    text = "![](https://host/temp_images/dingtalk_deadbeef_1710000000.png?sig=x)"
    assert extract_dingtalk_preview_unique_id(text) == "deadbeef"


def test_answer_has_library_diagram_uuid() -> None:
    """Detect mg alt text marker."""
    assert answer_has_library_diagram_uuid("![mg:abc-123](https://x/t.png)")


@pytest.mark.asyncio
async def test_enrich_prepends_notice_from_redis() -> None:
    """Prepend DingTalk notice when skip metadata exists."""
    answer = "![](https://host/temp_images/dingtalk_cafebabe_1710000000.png)"
    with patch(
        "services.mindbot.diagram.library_save_reply.get_generation_library_skip",
        new=AsyncMock(return_value={"reason": "unbound_staff", "language": "zh"}),
    ):
        enriched = await enrich_dingtalk_reply_with_library_save_notice(answer)
    assert enriched.startswith("导图仅预览")
    assert answer in enriched


@pytest.mark.asyncio
async def test_enrich_skips_when_library_uuid_present() -> None:
    """No injection when diagram was saved."""
    answer = "![mg:550e8400-e29b-41d4-a716-446655440000](https://host/temp_images/dingtalk_cafebabe_1.png)"
    with patch(
        "services.mindbot.diagram.library_save_reply.get_generation_library_skip",
        new=AsyncMock(),
    ) as mock_get:
        result = await enrich_dingtalk_reply_with_library_save_notice(answer)
    assert result == answer
    mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_enrich_skips_when_notice_already_present() -> None:
    """No duplicate when Dify answer already includes skip text."""
    answer = "![](https://host/temp_images/dingtalk_cafebabe_1710000000.png)\nDiagram preview only — bind DingTalk"
    with patch(
        "services.mindbot.diagram.library_save_reply.get_generation_library_skip",
        new=AsyncMock(),
    ) as mock_get:
        result = await enrich_dingtalk_reply_with_library_save_notice(answer)
    assert result == answer
    mock_get.assert_not_called()
    assert answer_has_library_save_skip_notice(answer)


@pytest.mark.asyncio
async def test_enrich_no_op_without_preview_url() -> None:
    """Unrelated answers are unchanged."""
    answer = "Hello from MindBot"
    result = await enrich_dingtalk_reply_with_library_save_notice(answer)
    assert result == answer


def test_extract_prepended_library_save_notice() -> None:
    """Detect notice prefix added by enrich."""
    original = "![](https://host/temp_images/dingtalk_abcd1234_1.png)"
    enriched = "导图仅预览，未绑定。\n\n" + original
    assert extract_prepended_library_save_notice(original, enriched) == "导图仅预览，未绑定。"
    assert extract_prepended_library_save_notice(original, original) is None
