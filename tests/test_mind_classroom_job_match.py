"""Classroom jobs for the three LLM maps must not share one lookup."""

from services.mind_classroom.job_match import (
    classroom_ready_job_reusable,
    classroom_settings_match,
    job_matches_live_nodes,
    job_matches_llm_model,
    lecture_steps_bind_live,
    playable_result_json,
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


def test_playable_result_json_requires_steps_and_rejects_replaced() -> None:
    """COS-superseded or empty result_json must not stay green."""
    assert playable_result_json({"steps": [{"caption": "Hello"}]}) is True
    assert playable_result_json({"steps": [{"caption": "  "}]}) is False
    assert playable_result_json({"steps": [], "transcript_key": "k"}) is False
    assert playable_result_json({"steps": [{"caption": "Hello"}], "transcript_replaced": True}) is False


def test_ready_job_reuse_requires_hash_or_live_majority() -> None:
    """Kitty full id rewrite is a fresh Start; same ids or matching hash reuse."""
    steps = {"steps": [{"caption": "Hello"}]}
    assert (
        classroom_ready_job_reusable(
            spec_hash="aaa",
            wanted_hash="aaa",
            spec_node_ids=["old-a"],
            live_ids={"new-root"},
            result_json=steps,
        )
        is True
    )
    assert (
        classroom_ready_job_reusable(
            spec_hash="old",
            wanted_hash="new",
            spec_node_ids=["old-a", "old-b"],
            live_ids={"old-a", "extra"},
            result_json=steps,
        )
        is True
    )
    assert (
        classroom_ready_job_reusable(
            spec_hash="old",
            wanted_hash="new",
            spec_node_ids=["old-a", "old-b"],
            live_ids={"new-root"},
            result_json=steps,
        )
        is False
    )
    assert (
        classroom_ready_job_reusable(
            spec_hash="old",
            wanted_hash="new",
            spec_node_ids=["old-a", "old-b"],
            live_ids={"topic", "branch-1"},
            result_json={
                "steps": [{"caption": "Hello", "focus_node_ids": ["topic"]}],
            },
        )
        is True
    )


def test_classroom_settings_match_ignores_audience_title() -> None:
    """Reuse must not miss because the localized audience title string drifted."""
    stored = {
        "mode": "canvas_tour",
        "mastery": "first_look",
        "tone": "classroom",
        "tour_scope": "main_branch",
        "slide_style": "general",
        "audience_level": "general",
        "audience_title": "大众",
        "language": "zh-CN",
        "llm_model": "deepseek",
    }
    wanted = {
        **stored,
        "audience_title": "General public",
        "language": "zh",
    }
    assert classroom_settings_match(stored, wanted) is True
    assert classroom_settings_match(stored, {**wanted, "llm_model": "qwen"}) is False
    assert lecture_steps_bind_live(
        {"steps": [{"caption": "Hi", "focus_node_ids": ["topic"]}]},
        {"topic"},
    )
    assert not lecture_steps_bind_live(
        {"steps": [{"caption": "Hi", "focus_node_ids": ["old"]}]},
        {"topic"},
    )
