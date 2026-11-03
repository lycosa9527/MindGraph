"""Reciprocal rank fusion keeps a section that both channels return ahead of a vector-only hit."""

from services.knowledge.vibeflow_rrf import reciprocal_rank_fusion


def test_overlap_outranks_a_single_list_hit() -> None:
    """A key returned by both lists ranks ahead of a key from one list."""
    fused = reciprocal_rank_fusion(
        [
            ["section-2", "section-2.1", "section-2.2"],
            ["china", "section-2", "section-3"],
        ]
    )
    assert fused[0] == "section-2"
    assert "section-2.1" in fused
    assert fused.index("section-2") < fused.index("china")


def test_one_empty_channel_keeps_the_other_order() -> None:
    """An empty channel leaves the other channel's order unchanged."""
    fused = reciprocal_rank_fusion([[], ["china", "sweden"]])
    assert fused == ["china", "sweden"]
