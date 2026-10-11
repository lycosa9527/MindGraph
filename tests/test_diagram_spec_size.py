"""Diagram save size: the canvas stays at 500KB; saved model diagrams use 4000KB."""

import json

from services.redis.cache._redis_diagram_cache_helpers import diagram_spec_size_error


def test_canvas_over_500kb_is_rejected() -> None:
    """A diagram with no saved models still stops at 500KB."""
    spec = {"topic": "t", "pad": "x" * (501 * 1024)}
    error = diagram_spec_size_error(spec, json.dumps(spec))
    assert error is not None
    assert "500KB" in error


def test_saved_models_fit_above_the_canvas_cap() -> None:
    """Model diagrams may ride along once the canvas itself is under 500KB."""
    canvas = {"topic": "t", "pad": "x" * 1000}
    spec = {
        **canvas,
        "llm_results": {
            "selectedModel": "kimi",
            "results": {
                "express": {"success": True, "spec": {"topic": "e"}},
                "kimi": {"success": True, "spec": {"topic": "k"}},
            },
        },
    }
    assert diagram_spec_size_error(spec, json.dumps(spec)) is None


def test_canvas_body_over_500kb_is_rejected_even_with_model_results() -> None:
    """Saved models do not raise the limit of the diagram the user is editing."""
    spec = {
        "topic": "t",
        "pad": "x" * (501 * 1024),
        "llm_results": {"selectedModel": "express", "results": {}},
    }
    error = diagram_spec_size_error(spec, json.dumps(spec))
    assert error is not None
    assert "500KB" in error
