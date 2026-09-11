"""Content-level and branch-numbering Kitty actions."""

from __future__ import annotations

from services.kitty.routing.command_grounding import apply_command_grounding
from services.kitty.routing.diagram_agent_context import (
    build_diagram_agent_payload,
    resolve_diagram_node_ref,
)
from services.kitty.routing.mindmap_branch_numbers import (
    build_outline_number_by_id,
    normalize_spoken_outline,
)
from services.kitty.routing.node_action_library import command_from_tool_call
from services.kitty.routing.one_sentence_edit_heuristics import heuristic_one_sentence_edit_command
from services.kitty.routing.preference_action_heuristics import (
    CONTENT_LEVEL_IDS,
    TOOLBAR_NUMBERING_PREFIX_IDS,
    normalize_content_level,
    normalize_numbering_style,
)


_DROPDOWN_ZH = (
    ("通用", "general"),
    ("小学", "primary"),
    ("初中", "junior"),
    ("高中", "senior"),
    ("大学", "university"),
    ("成人", "adult"),
    ("专家", "expert"),
)


def test_content_level_has_seven_dropdown_titles() -> None:
    """Voice phrases use the same seven titles as the 专业内容 dropdown."""
    assert len(CONTENT_LEVEL_IDS) == 7
    assert len(_DROPDOWN_ZH) == 7
    for title, level in _DROPDOWN_ZH:
        cmd = heuristic_one_sentence_edit_command(f"专业内容改成{title}")
        assert cmd == {"action": "set_content_level", "level": level, "confidence": 0.95}
    for title, level in (
        ("General", "general"),
        ("Primary", "primary"),
        ("Middle school", "junior"),
        ("High school", "senior"),
        ("University", "university"),
        ("Adult", "adult"),
        ("Expert", "expert"),
    ):
        cmd = heuristic_one_sentence_edit_command(f"set content to {title}")
        assert cmd is not None
        assert cmd.get("level") == level


def test_heuristic_set_content_level_and_numbering() -> None:
    """专业内容 / 启用编号 skip the LLM."""
    primary = heuristic_one_sentence_edit_command("专业内容改成小学")
    assert primary == {"action": "set_content_level", "level": "primary", "confidence": 0.95}
    expert = heuristic_one_sentence_edit_command("改成专家水平")
    assert expert is not None
    assert expert.get("level") == "expert"
    professional = heuristic_one_sentence_edit_command("set content to professional")
    assert professional is not None
    assert professional.get("level") == "expert"
    assert heuristic_one_sentence_edit_command("启用编号") == {
        "action": "set_branch_numbering",
        "enabled": True,
        "confidence": 0.95,
    }
    assert heuristic_one_sentence_edit_command("启用数字编号") == {
        "action": "set_branch_numbering",
        "enabled": True,
        "prefix": "decimal",
        "confidence": 0.95,
    }
    chinese = heuristic_one_sentence_edit_command("启用中文编号")
    assert chinese is not None
    assert chinese["prefix"] == "chinese"
    circled = heuristic_one_sentence_edit_command("编号改成圆圈")
    assert circled is not None
    assert circled["prefix"] == "circled"
    english = heuristic_one_sentence_edit_command("enable Chinese numbering")
    assert english is not None
    assert english["prefix"] == "chinese"
    hidden = heuristic_one_sentence_edit_command("隐藏编号")
    assert hidden is not None
    assert hidden["enabled"] is False


def test_normalize_numbering_style_aliases() -> None:
    """Spoken 数字 / 中文 map onto toolbar prefix ids."""
    assert normalize_numbering_style("数字") == "decimal"
    assert normalize_numbering_style("chinese") == "chinese"
    assert normalize_numbering_style("章节编号") == "chineseChapter"
    assert normalize_numbering_style("not-a-style") is None
    assert "decimal" in TOOLBAR_NUMBERING_PREFIX_IDS
    assert "chinese" in TOOLBAR_NUMBERING_PREFIX_IDS
    assert len(TOOLBAR_NUMBERING_PREFIX_IDS) == 11


def test_normalize_content_level_aliases() -> None:
    """School-stage aliases map onto catalog ids."""
    assert normalize_content_level("小学") == "primary"
    assert normalize_content_level("general") == "general"
    assert normalize_content_level("专业") == "expert"
    assert normalize_content_level("not-a-level") is None


def test_tool_call_preference_actions() -> None:
    """Library tools map to legacy preference commands."""
    level = command_from_tool_call("node_action.set_content_level", '{"level":"junior"}')
    assert level["action"] == "set_content_level"
    assert level["level"] == "junior"
    numbering = command_from_tool_call("node_action.set_branch_numbering", '{"enabled":true}')
    assert numbering["action"] == "set_branch_numbering"
    assert numbering["enabled"] is True
    styled = command_from_tool_call(
        "node_action.set_branch_numbering",
        '{"enabled":true,"prefix":"chinese"}',
    )
    assert styled["prefix"] == "chinese"


def test_outline_numbers_follow_canvas_clockwise() -> None:
    """Voice 1 / 第N个 match painted chrome, not raw connection-list order."""
    diagram = {
        "_mindmap_branch_numbering": True,
        "nodes": [
            {"id": "topic", "text": "T", "type": "topic", "position": {"x": 0, "y": 0}},
            {"id": "uid-r-bot", "text": "右下", "position": {"x": 10, "y": 10}},
            {"id": "uid-r-top", "text": "右上", "position": {"x": 10, "y": -10}},
            {"id": "uid-l-bot", "text": "左下", "position": {"x": -10, "y": 10}},
            {"id": "uid-l-top", "text": "左上", "position": {"x": -10, "y": -10}},
        ],
        "connections": [
            {"source": "topic", "target": "uid-l-bot"},
            {"source": "topic", "target": "uid-r-bot"},
            {"source": "topic", "target": "uid-l-top"},
            {"source": "topic", "target": "uid-r-top"},
        ],
    }
    numbers = build_outline_number_by_id(diagram)
    assert numbers["uid-r-top"] == "1"
    assert numbers["uid-r-bot"] == "2"
    assert numbers["uid-l-bot"] == "3"
    assert numbers["uid-l-top"] == "4"
    assert resolve_diagram_node_ref(diagram, label="第3个") == {
        "node_id": "uid-l-bot",
        "node_label": "左下",
    }


def test_outline_numbers_and_spoken_resolve() -> None:
    """When numbering is on, 第2个 / 1.1 bind the live UUID."""
    diagram = {
        "_mindmap_branch_numbering": True,
        "nodes": [
            {"id": "topic", "text": "茶"},
            {"id": "uid-a", "text": "中国"},
            {"id": "uid-b", "text": "日本"},
            {"id": "uid-c", "text": "绿茶"},
        ],
        "connections": [
            {"source": "topic", "target": "uid-a"},
            {"source": "topic", "target": "uid-b"},
            {"source": "uid-a", "target": "uid-c"},
        ],
    }
    numbers = build_outline_number_by_id(diagram)
    assert numbers["uid-a"] == "1"
    assert numbers["uid-b"] == "2"
    assert numbers["uid-c"] == "1.1"
    assert normalize_spoken_outline("第2个") == "2"
    assert resolve_diagram_node_ref(diagram, label="第2个") == {
        "node_id": "uid-b",
        "node_label": "日本",
    }
    dotted = resolve_diagram_node_ref(diagram, label="1.1")
    assert dotted is not None
    assert dotted["node_id"] == "uid-c"
    payload = build_diagram_agent_payload(
        {"diagram_data": diagram},
        diagram_type="mindmap",
    )
    assert payload.get("numbering") is True
    by_id = {node["id"]: node for node in payload["nodes"] if isinstance(node, dict)}
    assert by_id["uid-b"]["no"] == "2"


def test_rename_by_outline_number_is_grounded() -> None:
    """把2.1改成X binds the live UUID even when the spoken text is not the label."""
    ctx = {
        "diagram_data": {
            "_mindmap_branch_numbering": True,
            "nodes": [
                {"id": "topic", "text": "茶"},
                {"id": "uid-a", "text": "中国"},
                {"id": "uid-b", "text": "日本"},
                {"id": "uid-d", "text": "抹茶"},
            ],
            "connections": [
                {"source": "topic", "target": "uid-a"},
                {"source": "topic", "target": "uid-b"},
                {"source": "uid-b", "target": "uid-d"},
            ],
        },
    }
    command = heuristic_one_sentence_edit_command("把2.1改成新名")
    assert command is not None
    assert command.get("target") == "2.1"
    assert command.get("new_text") == "新名"
    decision = apply_command_grounding(
        command,
        user_text="把2.1改成新名",
        session_context=ctx,
        source="fast_structural",
    )
    assert decision.allowed is True
    assert command.get("node_id") == "uid-d"
    mapped = command_from_tool_call(
        "diagram.update_node",
        '{"node_identifier":"2.1","new_text":"新名"}',
    )
    assert mapped.get("new_text") == "新名"
    assert mapped.get("node_identifier") == "2.1"
    dotted = {
        "diagram_data": {
            **ctx["diagram_data"],
            "_mindmap_branch_numbering": False,
        },
    }
    off = heuristic_one_sentence_edit_command("把2.1改成新名")
    assert off is not None
    dotted_decision = apply_command_grounding(
        off,
        user_text="把2.1改成新名",
        session_context=dotted,
        source="fast_structural",
    )
    assert dotted_decision.allowed is True
    assert off.get("node_id") == "uid-d"


def test_number_delete_is_grounded_when_numbering_on() -> None:
    """删除第2个分支 is allowed even when the spoken text is not the label."""
    ctx = {
        "diagram_data": {
            "_mindmap_branch_numbering": True,
            "nodes": [
                {"id": "topic", "text": "茶"},
                {"id": "uid-a", "text": "中国"},
                {"id": "uid-b", "text": "日本"},
            ],
            "connections": [
                {"source": "topic", "target": "uid-a"},
                {"source": "topic", "target": "uid-b"},
            ],
        },
    }
    command = heuristic_one_sentence_edit_command("删除第2个分支")
    assert command is not None
    decision = apply_command_grounding(
        command,
        user_text="删除第2个分支",
        session_context=ctx,
        source="fast_structural",
    )
    assert decision.allowed is True
    assert command.get("node_id") == "uid-b"


def test_explicit_ordinal_resolves_when_numbering_off() -> None:
    """第2个 / 2.1 name a tree slot; bare 2 does not unless chrome is on."""
    diagram = {
        "_mindmap_branch_numbering": False,
        "nodes": [
            {"id": "topic", "text": "茶"},
            {"id": "uid-a", "text": "中国"},
            {"id": "uid-b", "text": "日本"},
        ],
        "connections": [
            {"source": "topic", "target": "uid-a"},
            {"source": "topic", "target": "uid-b"},
        ],
    }
    assert resolve_diagram_node_ref(diagram, label="第2个") == {
        "node_id": "uid-b",
        "node_label": "日本",
    }
    assert resolve_diagram_node_ref(diagram, label="2") is None
    command = heuristic_one_sentence_edit_command("删除第2个分支")
    assert command is not None
    decision = apply_command_grounding(
        command,
        user_text="删除第2个分支",
        session_context={"diagram_data": diagram},
        source="fast_structural",
    )
    assert decision.allowed is True
    assert command.get("node_id") == "uid-b"
