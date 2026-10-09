"""Document-generation mind maps keep labels the model did not put in text."""

from agents.mind_maps.mind_map_agent import MindMapAgent
from agents.mind_maps.mind_map_spec_normalize import canonicalize_mind_map_spec


def _four_branches(first_children: list) -> dict:
    return {
        "topic": "八一精神",
        "children": [
            {"text": "八一精神的传承逻辑", "children": first_children},
            {"text": "听党指挥", "children": [{"text": "党的领导"}]},
            {"text": "能打胜仗", "children": [{"text": "战斗力"}]},
            {"text": "作风优良", "children": [{"text": "纪律"}]},
        ],
    }


def test_string_children_fail_raw_validation_and_pass_after_canonicalize() -> None:
    """Bare string children are the shape behind the invalid-spec error."""
    agent = MindMapAgent(model="qwen")
    raw = _four_branches(["历史渊源", "实践路径"])
    ok, msg = agent.validate_output(raw)
    assert ok is False
    assert "八一精神的传承逻辑" in msg
    assert "with text" in msg

    fixed = canonicalize_mind_map_spec(raw)
    ok, msg = agent.validate_output(fixed)
    assert ok is True
    assert fixed["children"][0]["children"] == [
        {"text": "历史渊源"},
        {"text": "实践路径"},
    ]


def test_name_and_title_children_become_text() -> None:
    """Models that use name or title still produce drawable nodes."""
    agent = MindMapAgent(model="qwen")
    raw = _four_branches([{"name": "南昌起义"}, {"title": "井冈山"}])
    assert agent.validate_output(raw)[0] is False
    fixed = canonicalize_mind_map_spec(raw)
    assert agent.validate_output(fixed)[0] is True
    labels = [child["text"] for child in fixed["children"][0]["children"]]
    assert labels == ["南昌起义", "井冈山"]


def test_existing_text_is_not_replaced() -> None:
    """A real text label wins over name/title on the same node."""
    raw = _four_branches([{"text": "听党指挥", "name": "其他", "title": "别的"}])
    fixed = canonicalize_mind_map_spec(raw)
    assert fixed["children"][0]["children"][0]["text"] == "听党指挥"
    assert fixed["topic"] == "八一精神"


def test_valid_tree_keeps_shape_and_ids() -> None:
    """A spec production already accepts is not rearranged."""
    raw = _four_branches([{"id": "c1", "text": "历史渊源", "textSecondary": "origin"}])
    fixed = canonicalize_mind_map_spec(raw)
    child = fixed["children"][0]["children"][0]
    assert child["id"] == "c1"
    assert child["text"] == "历史渊源"
    assert child["textSecondary"] == "origin"
    assert [branch["text"] for branch in fixed["children"]] == [
        "八一精神的传承逻辑",
        "听党指挥",
        "能打胜仗",
        "作风优良",
    ]


def test_missing_children_key_is_not_invented() -> None:
    """Left/right maps are not given an empty children list."""
    raw = {"topic": "八一精神", "left": [{"text": "听党指挥"}]}
    fixed = canonicalize_mind_map_spec(raw)
    assert "children" not in fixed
    assert fixed["left"][0]["text"] == "听党指挥"


def test_empty_children_still_fail_hierarchy() -> None:
    """A main branch with no recoverable labels is still rejected."""
    agent = MindMapAgent(model="qwen")
    raw = _four_branches([{"text": "  "}, {}])
    fixed = canonicalize_mind_map_spec(raw)
    ok, msg = agent.validate_output(fixed)
    assert ok is False
    assert "nested children" in msg


def test_textless_wrapper_is_not_hoisted() -> None:
    """An unlabeled wrapper stays put so a valid parent is not flattened."""
    agent = MindMapAgent(model="qwen")
    raw = _four_branches([{"children": [{"text": "听党指挥"}]}])
    fixed = canonicalize_mind_map_spec(raw)
    assert fixed["children"][0]["children"][0]["children"][0]["text"] == "听党指挥"
    assert agent.validate_output(fixed)[0] is False
