"""Tests for mind map branch sub-graph expansion."""

from agents.mind_maps.mind_map_agent import MindMapAgent, build_mind_map_branch_expand_user_message


def test_build_branch_expand_user_message_includes_topic_and_reference_branches():
    """Branch expand prompt should include central topic and sibling branches."""
    message = build_mind_map_branch_expand_user_message(
        expand_branch="Light",
        mind_map_topic="Photosynthesis",
        reference_branches=["Calvin cycle"],
        existing_branch_children=["Chlorophyll"],
        parent_branch="",
        language="zh",
    )
    assert "中心主题：Photosynthesis" in message
    assert "要扩展的分支：Light" in message
    assert "图中其他分支（参考）：Calvin cycle" in message
    assert "该分支已有子节点（勿重复）：Chlorophyll" in message
    assert "直接子节点" in message


def test_build_branch_expand_user_message_uses_nested_wording_for_child_nodes():
    """Nested anchors should ask for direct sub-node children only."""
    message = build_mind_map_branch_expand_user_message(
        expand_branch="Dynasties",
        mind_map_topic="History",
        reference_branches=[],
        existing_branch_children=[],
        parent_branch="Ancient",
        language="zh",
    )
    assert "上级分支：Ancient" in message
    assert "直接下级节点" in message


def test_validate_branch_expand_output_accepts_valid_children():
    """Accept specs with at least two sub-branches under the expanded branch."""
    agent = MindMapAgent(model="qwen")
    spec = {
        "topic": "Light reactions",
        "children": [
            {"id": "a", "text": "Photosystem II"},
            {"id": "b", "text": "Electron transport"},
        ],
    }
    ok, msg = agent.validate_branch_expand_output(spec, "Light reactions")
    assert ok is True
    assert msg == "Valid branch expand specification"


def test_validate_branch_expand_output_rejects_too_few_children():
    """Reject branch expand output with fewer than two sub-branches."""
    agent = MindMapAgent(model="qwen")
    spec = {
        "topic": "Light reactions",
        "children": [{"id": "a", "text": "Only one"}],
    }
    ok, msg = agent.validate_branch_expand_output(spec, "Light reactions")
    assert ok is False
    assert "At least two" in msg


def test_validate_branch_expand_output_rejects_wrong_topic():
    """Reject when topic label does not match the branch being expanded."""
    agent = MindMapAgent(model="qwen")
    spec = {
        "topic": "Wrong label",
        "children": [
            {"id": "a", "text": "One"},
            {"id": "b", "text": "Two"},
        ],
    }
    ok, msg = agent.validate_branch_expand_output(spec, "Light reactions")
    assert ok is False
    assert "expanded branch" in msg
