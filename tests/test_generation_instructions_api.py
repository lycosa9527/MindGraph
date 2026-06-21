"""Tests for generation_instructions prompt merge in diagram generation router."""

from __future__ import annotations

import pytest

from models import GenerateRequest
from models.common import LLMModel


def test_generate_request_accepts_generation_instructions() -> None:
    """GenerateRequest should expose optional generation_instructions."""
    req = GenerateRequest(
        prompt="中心主题",
        generation_instructions="四个分支：衣、食、住、行",
        language="zh",
        llm=LLMModel.QWEN,
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
    _ = language
    prompt = "Main topic"
    instructions = "Four branches: A, B, C, D"
    merged = f"{prompt}\n\n{marker}\n{instructions.strip()}"
    assert marker in merged
    assert instructions in merged
