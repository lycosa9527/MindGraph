"""Classroom jobs for the three LLM maps must not share one lookup."""

from services.mind_classroom.job_match import (
    job_matches_live_nodes,
    job_matches_llm_model,
    spec_snapshot_node_ids,
)


def test_job_matches_llm_model_filters_multi_llm_maps() -> None:
    """Three LLM variants share one diagram id; lookup must stay on the selected model."""
    assert job_matches_llm_model({"llm_model": "qwen"}, "qwen") is True
    assert job_matches_llm_model({"llm_model": "deepseek"}, "qwen") is False
    assert job_matches_llm_model({"llm_model": ""}, "qwen") is False
    assert job_matches_llm_model({}, None) is True


def test_job_matches_the_visible_spec_nodes() -> None:
    """Script reuse is only for the map currently on the canvas."""
    spec = {"nodes": [{"id": "qwen-a"}, {"id": "qwen-b"}], "connections": []}
    assert spec_snapshot_node_ids(spec) == ["qwen-a", "qwen-b"]
    assert job_matches_live_nodes(["qwen-a", "qwen-b"], {"qwen-a"}) is True
    assert job_matches_live_nodes(["deepseek-a"], {"qwen-a", "qwen-b"}) is False
    assert job_matches_live_nodes([], {"qwen-a"}) is False
    assert job_matches_live_nodes(["a", "b", "c", "d"], {"a"}) is False
