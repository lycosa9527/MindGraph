"""Tests for optional single-LLM node palette batches."""

from agents.node_palette.base_palette_generator import BasePaletteGenerator


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
    """Invalid model lists should use the default palette trio."""
    generator = _StubPaletteGenerator()
    resolver = getattr(generator, "_resolve_batch_llm_models")
    assert resolver(["unknown"]) == ["qwen", "deepseek", "doubao"]
