"""Optional LLM fill must not fail the Word export."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.infrastructure.http.error_handler import LLMServiceError
from services.mindmate.teaching_design_llm import complete_teaching_design_spec
from services.mindmate.teaching_design_models import TeachingDesignSpec


@pytest.mark.asyncio
async def test_llm_service_error_keeps_parsed_lesson() -> None:
    """Provider failures fall back to the parsed reply and still name the teacher."""
    parsed = TeachingDesignSpec(leftover="没有标题的课例正文")
    with patch(
        "services.mindmate.teaching_design_llm.fill_teaching_design_with_llm",
        new_callable=AsyncMock,
        side_effect=LLMServiceError("Chat failed for model qwen"),
    ):
        spec = await complete_teaching_design_spec(
            parsed,
            "没有标题的课例正文",
            user_id=1,
            organization_id=1,
            teacher_name="王老师",
        )
    assert "没有标题的课例正文" in spec.summary
    assert spec.teacher == "王老师"
