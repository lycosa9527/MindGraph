"""Unit tests for prompt requirements extraction helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agents.core.prompt_requirements import (
    build_agent_context,
    map_to_agent_params,
    merge_agent_params,
    parse_requirements_for_type,
)
from prompts import get_prompt

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "prompt_requirements"


@pytest.mark.parametrize(
    ("diagram_type", "fixture_name"),
    [
        ("mind_map", "mind_map_fixed.json"),
        ("flow_map", "flow_map_fixed.json"),
        ("double_bubble_map", "double_bubble_fixed.json"),
        ("brace_map", "brace_map_fixed.json"),
        ("bridge_map", "bridge_map_fixed.json"),
    ],
)
def test_parse_requirements_case2_per_type(diagram_type: str, fixture_name: str) -> None:
    """Fixed-structure fixtures parse to structure_mode fixed with nodes."""
    raw = json.loads((FIXTURES_DIR / fixture_name).read_text(encoding="utf-8"))
    parsed = parse_requirements_for_type(diagram_type, raw, fallback_prompt="fallback")
    assert parsed.structure_mode == "fixed"
    assert parsed.central
    assert parsed.fixed_nodes


def test_parse_requirements_case1_free() -> None:
    """Free-mode requirements keep central topic without fixed nodes."""
    raw = {"topic": "人工智能", "structure_mode": "free", "clarity": "clear"}
    parsed = parse_requirements_for_type("mind_map", raw, fallback_prompt="raw prompt")
    assert parsed.structure_mode == "free"
    assert parsed.central == "人工智能"
    assert parsed.fixed_nodes == {}


def test_alias_normalization() -> None:
    """Double bubble left/right topic aliases normalize to fixed nodes."""
    raw = {
        "left_topic": "苹果",
        "right_topic": "橙子",
        "structure_mode": "free",
        "clarity": "clear",
    }
    parsed = parse_requirements_for_type("double_bubble_map", raw, fallback_prompt="")
    assert parsed.structure_mode == "fixed"
    assert parsed.fixed_nodes["left"] == "苹果"
    assert parsed.fixed_nodes["right"] == "橙子"


def test_flow_map_title_alias_from_topic() -> None:
    """Flow map topic alias maps to central title and fixed steps."""
    raw = {"topic": "制作咖啡", "steps": ["磨豆", "萃取"], "structure_mode": "fixed"}
    parsed = parse_requirements_for_type("flow_map", raw, fallback_prompt="")
    assert parsed.central == "制作咖啡"
    assert parsed.fixed_nodes["steps"] == ["磨豆", "萃取"]


def test_brace_map_whole_alias_from_topic() -> None:
    """Brace map topic alias maps to whole and fixed parts."""
    raw = {"topic": "汽车", "parts": ["引擎", "底盘"], "structure_mode": "fixed"}
    parsed = parse_requirements_for_type("brace_map", raw, fallback_prompt="")
    assert parsed.central == "汽车"
    assert parsed.fixed_nodes["parts"] == ["引擎", "底盘"]


def test_empty_fixed_list_downgrades_to_free() -> None:
    """Empty fixed children list downgrades structure_mode to free."""
    raw = {"topic": "主题", "structure_mode": "fixed", "children": []}
    parsed = parse_requirements_for_type("mind_map", raw, fallback_prompt="主题")
    assert parsed.structure_mode == "free"


def test_list_present_forces_fixed_even_when_llm_says_free() -> None:
    """Non-empty fixed lists force fixed mode even when LLM says free."""
    raw = {"topic": "北京三日游", "structure_mode": "free", "children": ["衣", "食", "住", "行"]}
    parsed = parse_requirements_for_type("mind_map", raw, fallback_prompt="")
    assert parsed.structure_mode == "fixed"
    assert parsed.fixed_nodes["children"] == ["衣", "食", "住", "行"]


def test_merge_agent_params_skips_dimension_pref_when_fixed_lists_present() -> None:
    """Fixed lists suppress dimension preference in merged agent params."""
    extracted = map_to_agent_params(
        "tree_map",
        parse_requirements_for_type(
            "tree_map",
            {
                "topic": "动物",
                "structure_mode": "fixed",
                "children": ["鱼类", "哺乳类"],
                "dimension": "栖息地",
            },
            "",
        ),
    )
    merged = merge_agent_params({"dimension_preference": "分类方式"}, extracted)
    assert merged.fixed_dimension is None
    assert merged.structure_mode == "fixed"
    assert merged.fixed_nodes["children"] == ["鱼类", "哺乳类"]


def test_merge_agent_params_api_fixed_dimension_wins() -> None:
    """API fixed_dimension overrides extracted dimension for free mode."""
    extracted = map_to_agent_params(
        "tree_map",
        parse_requirements_for_type(
            "tree_map",
            {"topic": "动物", "dimension": "栖息地", "structure_mode": "free"},
            "",
        ),
    )
    merged = merge_agent_params({"fixed_dimension": "分类方式"}, extracted)
    assert merged.fixed_dimension == "分类方式"


def test_merge_agent_params_api_analogies_win() -> None:
    """API existing_analogies override extracted bridge map analogies."""
    extracted = map_to_agent_params(
        "bridge_map",
        parse_requirements_for_type(
            "bridge_map",
            {
                "structure_mode": "fixed",
                "analogies": [{"left": "巴黎", "right": "法国"}],
            },
            "",
        ),
    )
    merged = merge_agent_params(
        {"existing_analogies": [{"left": "东京", "right": "日本"}]},
        extracted,
    )
    assert merged.existing_analogies == [{"left": "东京", "right": "日本"}]
    assert merged.structure_mode == "fixed"


def test_build_agent_context_empty_for_free_mode() -> None:
    """Free mode context omits fixed-structure block but keeps constraints."""
    parsed = parse_requirements_for_type(
        "mind_map",
        {"topic": "AI", "structure_mode": "free", "constraints": "简洁"},
        "",
    )
    context = build_agent_context("mind_map", parsed)
    assert "User-specified structure" not in context
    assert "简洁" in context or "constraints" in context.lower()


def test_mind_map_fixed_children_prompt_registered() -> None:
    """Mind map fixed_children prompt template is registered for zh."""
    prompt = get_prompt("mind_map", "zh", "fixed_children")
    assert prompt
    assert "分支" in prompt or "branch" in prompt.lower()
