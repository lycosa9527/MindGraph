"""Unit tests for hand-drawn mind-map outline markdown."""

from services.knowledge.mindmap_outline_md import mindmap_spec_to_outline_markdown


def test_mindmap_spec_to_outline_markdown_nested() -> None:
    """Topic becomes H1; first-level children become H2; deeper levels bullets."""
    md = mindmap_spec_to_outline_markdown(
        {
            "topic": "Study Plan",
            "children": [
                {
                    "text": "Math",
                    "children": [
                        {"text": "Algebra"},
                        {"label": "Geometry", "children": [{"text": "Proofs"}]},
                    ],
                },
                {"text": "Science"},
            ],
        }
    )
    assert md.startswith("# Study Plan\n")
    assert "## Math" in md
    assert "- Algebra" in md
    assert "  - Proofs" in md
    assert "## Science" in md
    assert "hand-drawn" in md


def test_mindmap_spec_to_outline_markdown_empty_children() -> None:
    """Empty tree still yields a titled outline."""
    md = mindmap_spec_to_outline_markdown({"topic": "Solo"})
    assert "# Solo" in md
    assert md.endswith("\n")
