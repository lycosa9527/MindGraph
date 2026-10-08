"""Tests for optional single-LLM node palette batches."""

from agents.node_palette.base_palette_generator import BasePaletteGenerator
from models.requests.requests_thinking import NodePaletteNextRequest, NodePaletteStartRequest


class _StubPaletteGenerator(BasePaletteGenerator):
    """Minimal concrete generator for model-resolution tests."""

    def _build_prompt(self, center_topic, educational_context, count, batch_num):
        return center_topic


def test_resolve_batch_llm_models_honors_single_model():
    """Single-model requests should not fall back to the full trio."""
    generator = _StubPaletteGenerator()
    resolver = getattr(generator, "_resolve_batch_llm_models")
    assert resolver(["deepseek"]) == ["deepseek"]


def test_resolve_batch_llm_models_falls_back_when_empty():
    """Invalid model lists should use Express."""
    generator = _StubPaletteGenerator()
    resolver = getattr(generator, "_resolve_batch_llm_models")
    assert resolver(["unknown"]) == ["express"]


def test_resolve_batch_llm_models_honors_canvas_menu():
    """Brainstorm may ask for the model selected on the canvas."""
    generator = _StubPaletteGenerator()
    resolver = getattr(generator, "_resolve_batch_llm_models")
    assert resolver(["qwen3-max"]) == ["qwen3-max"]
    assert resolver(["qwen3.8-flash"]) == ["qwen3.8-flash"]
    assert resolver(["kimi"]) == ["kimi"]
    assert resolver(["doubao21"]) == ["doubao21"]


def test_palette_requests_keep_the_canvas_model() -> None:
    """Start and load-more accept the menu id and drop unknown names."""
    start = NodePaletteStartRequest.model_validate(
        {
            "session_id": "palette_test",
            "diagram_type": "mindmap",
            "diagram_data": {"topic": "water"},
            "llm_models": ["qwen3-max", "nope"],
        }
    )
    assert start.llm_models == ["qwen3-max"]
    nxt = NodePaletteNextRequest.model_validate(
        {
            "session_id": "palette_test",
            "diagram_type": "mindmap",
            "center_topic": "water",
            "llm_models": ["Kimi"],
        }
    )
    assert nxt.llm_models == ["kimi"]
