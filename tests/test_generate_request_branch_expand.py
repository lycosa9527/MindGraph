"""GenerateRequest branch-expand field validation."""

from models import GenerateRequest


def test_generate_request_accepts_expand_branch_without_prompt():
    """Branch expand may send expand_branch as the sole topic anchor."""
    req = GenerateRequest.model_validate(
        {
            "prompt": "",
            "diagram_type": "mind_map",
            "language": "zh",
            "expand_branch": "Light reactions",
            "mind_map_topic": "Photosynthesis",
            "reference_branches": ["Calvin cycle"],
        }
    )
    assert req.expand_branch == "Light reactions"
    assert req.mind_map_topic == "Photosynthesis"
    assert req.reference_branches == ["Calvin cycle"]


def test_generate_request_caps_branch_context_lists():
    """Oversized branch context lists should be trimmed server-side."""
    labels = [f"branch-{idx}" for idx in range(40)]
    req = GenerateRequest.model_validate(
        {
            "prompt": "Light",
            "diagram_type": "mind_map",
            "language": "en",
            "expand_branch": "Light",
            "reference_branches": labels,
        }
    )
    assert req.reference_branches is not None
    assert len(req.reference_branches) == 24
