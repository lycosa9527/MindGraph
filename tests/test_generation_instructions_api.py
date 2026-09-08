"""Tests for generation_instructions prompt merge in diagram generation router."""

from __future__ import annotations

import pytest

from models import GenerateRequest
from models.common import LLMModel
from prompts.ai_content_level import merge_generation_instructions


def test_generate_request_accepts_generation_instructions() -> None:
    """GenerateRequest should expose optional generation_instructions."""
    req = GenerateRequest.model_validate(
        {
            "prompt": "中心主题",
            "generation_instructions": "四个分支：衣、食、住、行",
            "language": "zh",
            "llm": LLMModel.QWEN,
        }
    )
    assert req.generation_instructions == "四个分支：衣、食、住、行"


@pytest.mark.parametrize(
    ("language", "marker"),
    [
        ("zh", "【用户要求】"),
        ("en", "User requirements:"),
    ],
)
def test_generation_instructions_merge_marker(language: str, marker: str) -> None:
    """Merged prompt uses locale-appropriate requirement marker."""
    prompt = "Main topic"
    instructions = "Four branches: A, B, C, D"
    merged = merge_generation_instructions(prompt, instructions, language)
    assert marker in merged
    assert instructions in merged
