"""Archived MindMate replies get a short document title, not 基本信息.docx."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.mindmate.reply_docx import resolve_reply_docx_stem
from services.mindmate.reply_markdown_docx import reply_docx_filename


def test_lesson_name_line_becomes_the_stem() -> None:
    """A 课例名称 field is more specific than the 基本信息 heading."""
    source = "## 基本信息\n课例名称：小数的意义\n学段年级：四年级"
    assert reply_docx_filename(source, "研讨文档") == "小数的意义.docx"


@pytest.mark.asyncio
async def test_specific_title_does_not_call_the_model() -> None:
    """《课名》教学设计 is enough; skip the extra LLM round-trip."""
    with patch("services.mindmate.reply_docx.llm_service.chat", AsyncMock()) as chat:
        stem = await resolve_reply_docx_stem(
            "# 基本信息\n\n《勾股定理》教学设计\n",
            fallback="研讨文档",
            user_id=4,
            organization_id=1,
        )
    assert stem == "勾股定理教学设计"
    chat.assert_not_called()


@pytest.mark.asyncio
async def test_generic_heading_asks_the_model_for_a_short_title() -> None:
    """When the body has no lesson title, a short model title is used."""
    with patch(
        "services.mindmate.reply_docx.llm_service.chat",
        AsyncMock(return_value="直角三角形面积关系"),
    ) as chat:
        stem = await resolve_reply_docx_stem(
            "# 基本信息\n",
            fallback="研讨文档",
            user_id=4,
            organization_id=1,
        )
    assert stem == "直角三角形面积关系"
    chat.assert_awaited_once()
