"""Tests for generation_instructions prompt merge in diagram generation router."""

from __future__ import annotations

import pytest

from models import GenerateRequest
from models.common import LLMModel
from models.requests.requests_thinking import NodePaletteStartRequest
from prompts.ai_content_level import merge_generation_instructions
from routers.node_palette_streaming import _merged_educational_context


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


def test_node_palette_start_accepts_generation_instructions() -> None:
    """Brainstorm / palette start keeps 专业内容 on the request model."""
    req = NodePaletteStartRequest.model_validate(
        {
            "session_id": "palette_abc12345",
            "diagram_type": "mindmap",
            "diagram_data": {"center": {"text": "茶叶"}},
            "language": "zh",
            "generation_instructions": "请按「初中」专业程度生成内容。",
        }
    )
    assert req.generation_instructions == "请按「初中」专业程度生成内容。"


def test_palette_merge_copies_generation_instructions_into_raw_message() -> None:
    """Palette prompt builder reads audience text from educational_context.raw_message."""
    req = NodePaletteStartRequest.model_validate(
        {
            "session_id": "palette_abc12345",
            "diagram_type": "mindmap",
            "diagram_data": {"center": {"text": "茶叶"}},
            "language": "zh",
            "generation_instructions": "请按「初中」专业程度生成内容。",
        }
    )
    edu = _merged_educational_context(req, "zh")
    assert edu is not None
    assert edu["raw_message"] == "请按「初中」专业程度生成内容。"
