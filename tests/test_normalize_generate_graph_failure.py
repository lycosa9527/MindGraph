"""Tests for generate_graph failure normalization."""

from agents.core.utils import create_error_response, normalize_generate_graph_failure


def test_normalize_promotes_nested_spec_error() -> None:
    """Nested create_error_response fields surface at top level."""
    result = {
        "success": False,
        "spec": create_error_response("Invalid input: empty prompt", "validation", {}),
        "diagram_type": "mind_map",
    }
    normalized = normalize_generate_graph_failure(result)
    assert normalized["error"] == "Invalid input: empty prompt"
    assert normalized["error_type"] == "validation"
    assert normalized["show_guidance"] is True


def test_normalize_keeps_existing_top_level_error() -> None:
    """Existing top-level error is not overwritten by spec."""
    result = {
        "success": False,
        "error": "Top-level message",
        "error_type": "generation",
        "spec": create_error_response("Nested message", "validation", {}),
    }
    normalized = normalize_generate_graph_failure(result)
    assert normalized["error"] == "Top-level message"
    assert normalized["error_type"] == "generation"


def test_normalize_success_payload_unchanged() -> None:
    """Successful results pass through unchanged."""
    result = {"success": True, "spec": {"topic": "Photosynthesis"}}
    assert normalize_generate_graph_failure(result) == result
