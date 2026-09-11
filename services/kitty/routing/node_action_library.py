"""Canonical node-action library for Kitty one-sentence mindmap edits.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, TypedDict

from services.kitty.routing.diagram_agent_context import serialize_diagram_for_node_action
from services.diagram_edit.schema import (
    diagram_edit_function_call_to_legacy_command,
    get_diagram_edit_tools,
)

Lang = Literal["zh", "en"]


class NodeActionRow(TypedDict):
    """One edit-relevant node action."""

    name: str
    tool_name: str
    description_zh: str
    description_en: str
    when_to_use_zh: str
    when_to_use_en: str
    examples_zh: List[str]
    examples_en: List[str]


NODE_ACTION_ROWS: List[NodeActionRow] = [
    {
        "name": "add_node",
        "tool_name": "diagram.add_node",
        "description_zh": "添加新的分支或子节点",
        "description_en": "Add a new branch or child node",
        "when_to_use_zh": "用户要新建一条还不存在的分支/子项",
        "when_to_use_en": "User wants a NEW branch/child that does not exist yet",
        "examples_zh": ["增加一个中国的分支", "在饮品分析下添加子项"],
        "examples_en": ["add a branch called China", "add a child under Beverages"],
    },
    {
        "name": "update_node",
        "tool_name": "diagram.update_node",
        "description_zh": "修改已有节点文字",
        "description_en": "Rename an existing node",
        "when_to_use_zh": "用户要改某个已有节点的名称",
        "when_to_use_en": "User wants to rename an existing node",
        "examples_zh": ["把饮品分析改成饮料分析", "把2.1改成绿茶"],
        "examples_en": ["rename Brewing Methods to Brew Methods", "rename 2.1 to green tea"],
    },
    {
        "name": "update_center",
        "tool_name": "diagram.update_center",
        "description_zh": "修改中心主题",
        "description_en": "Change the center/topic text",
        "when_to_use_zh": "用户要改导图主题/标题/中心",
        "when_to_use_en": "User wants to change the center topic/title",
        "examples_zh": ["主题改成茶叶"],
        "examples_en": ["change the topic to Tea"],
    },
    {
        "name": "delete_node",
        "tool_name": "diagram.delete_node",
        "description_zh": "删除分支或子节点",
        "description_en": "Delete a branch or child node",
        "when_to_use_zh": "用户要删除某个已有节点",
        "when_to_use_en": "User wants to remove an existing node",
        "examples_zh": ["删除饮品分析分支"],
        "examples_en": ["delete the branch called History"],
    },
    {
        "name": "auto_complete_branch",
        "tool_name": "node_action.auto_complete_branch",
        "description_zh": "自动补全已有分支的子节点",
        "description_en": "AI-fill children under an EXISTING branch",
        "when_to_use_zh": "用户要补全/填充/展开已存在的分支，不是新建分支",
        "when_to_use_en": "User asks to complete/fill/expand an EXISTING named branch",
        "examples_zh": ["补全中国这个分支", "把中国分支补全"],
        "examples_en": ["complete the China branch", "fill in the China branch"],
    },
    {
        "name": "auto_complete",
        "tool_name": "node_action.auto_complete",
        "description_zh": "自动补全整张导图",
        "description_en": "AI-fill the whole diagram",
        "when_to_use_zh": "用户要补全整张导图，未指定具体分支",
        "when_to_use_en": "User asks to auto-complete the whole diagram",
        "examples_zh": ["自动补全", "帮我补全导图"],
        "examples_en": ["auto-complete the diagram", "run auto-complete"],
    },
    {
        "name": "clarify_options",
        "tool_name": "node_action.clarify_options",
        "description_zh": "向用户确认意图（2–3个短选项）",
        "description_en": "Ask the user to pick among 2–3 short options",
        "when_to_use_zh": "问候、闲聊，或「改一下/这个」等意图不清时；添加 vs 补全也不确定时",
        "when_to_use_en": "Greetings, chitchat, vague edits, or add-new vs fill-existing",
        "examples_zh": ["中国 → 添加分支还是补全已有？"],
        "examples_en": ["China → add new branch or fill existing?"],
    },
    {
        "name": "set_content_level",
        "tool_name": "node_action.set_content_level",
        "description_zh": "把专业内容改成通用/小学/初中/高中/大学/成人/专家",
        "description_en": "Set AI content audience to general, primary, or expert",
        "when_to_use_zh": "用户要改底部「专业内容」受众难度",
        "when_to_use_en": "User wants to change the AI content audience level",
        "examples_zh": [
            "专业内容改成通用",
            "专业内容改成小学",
            "专业内容改成初中",
            "专业内容改成高中",
            "专业内容改成大学",
            "专业内容改成成人",
            "专业内容改成专家",
        ],
        "examples_en": [
            "set content to general",
            "set content to primary",
            "set content to middle school",
            "set content to high school",
            "set content to university",
            "set content to adult",
            "set content to expert",
        ],
    },
    {
        "name": "set_branch_numbering",
        "tool_name": "node_action.set_branch_numbering",
        "description_zh": "启用数字/中文/圆圈等编号，或隐藏编号",
        "description_en": "Enable decimal/Chinese/circled numbering, or hide numbers",
        "when_to_use_zh": "用户要启用某种编号风格，或隐藏编号；启用后可用 1、1.1、第2个 定位",
        "when_to_use_en": "User wants a numbering style, or to hide numbers for targeting",
        "examples_zh": [
            "启用编号",
            "启用数字编号",
            "启用中文编号",
            "启用圆圈编号",
            "隐藏编号",
        ],
        "examples_en": [
            "enable numbering",
            "enable decimal numbering",
            "enable Chinese numbering",
            "hide numbering",
        ],
    },
]


def _fn(
    name: str,
    description: str,
    properties: Dict[str, Any],
    required: List[str],
) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def build_node_action_tools() -> List[Dict[str, Any]]:
    """OpenAI tool schemas: structural diagram.* plus UI/clarify node_action.*."""
    structural = list(get_diagram_edit_tools())
    ui_and_meta = [
        _fn(
            "node_action.auto_complete_branch",
            (
                "Fill AI-generated children under an EXISTING branch. "
                "Use when the user asks to 补全/填充/expand a named branch that already exists. "
                "Require node_id from Current diagram JSON."
            ),
            {
                "node_id": {
                    "type": "string",
                    "description": "Stable branch node id from Current diagram JSON (preferred)",
                },
                "target": {
                    "type": "string",
                    "description": "Existing branch label (use when node_id unknown)",
                },
            },
            [],
        ),
        _fn(
            "node_action.auto_complete",
            (
                "Fill the whole diagram when the user asks to auto-complete the map "
                "and does not name a branch. Do not call this in the same turn as new-branch add_node."
            ),
            {},
            [],
        ),
        _fn(
            "node_action.set_content_level",
            (
                "Set the AI content audience (专业内容): general, primary, junior, "
                "senior, university, adult, or expert. Use when the user asks to "
                "change difficulty / school stage / professional level."
            ),
            {
                "level": {
                    "type": "string",
                    "enum": [
                        "general",
                        "primary",
                        "junior",
                        "senior",
                        "university",
                        "adult",
                        "expert",
                    ],
                    "description": "Audience level id",
                },
            },
            ["level"],
        ),
        _fn(
            "node_action.set_branch_numbering",
            (
                "Show or hide mind-map branch numbering, optionally choosing a "
                "prefix style (decimal, chinese, circled). Outline nos in the "
                "diagram JSON match painted chrome; 第2个 / 2.1 also work as "
                "spoken ordinals."
            ),
            {
                "enabled": {
                    "type": "boolean",
                    "description": "true to show numbers, false to hide",
                },
                "prefix": {
                    "type": "string",
                    "enum": [
                        "decimal",
                        "decimalParen",
                        "paren",
                        "circled",
                        "chinese",
                        "chineseParen",
                        "chineseChapter",
                        "chineseArticle",
                        "upperAlpha",
                        "lowerAlpha",
                        "lowerAlphaParen",
                    ],
                    "description": "L1 glyph style; setting a prefix also enables numbering",
                },
            },
            ["enabled"],
        ),
        _fn(
            "node_action.clarify_options",
            "Ask the user to pick one of 2–3 short next actions. Use for greetings (你好), "
            "chitchat, or vague edits (改一下 / this). Question is one line; labels stay short.",
            {
                "question": {
                    "type": "string",
                    "description": "Short question for the user",
                },
                "options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Short option label"},
                            "action": {
                                "type": "string",
                                "enum": [
                                    "add_node",
                                    "update_node",
                                    "update_center",
                                    "delete_node",
                                    "auto_complete_branch",
                                    "auto_complete",
                                    "ask_followup",
                                ],
                            },
                            "target": {"type": "string"},
                            "node_id": {
                                "type": "string",
                                "description": "Stable node id from diagram JSON (preferred)",
                            },
                            "node_identifier": {"type": "string"},
                            "new_text": {"type": "string"},
                            "parent_ref": {
                                "type": "string",
                                "description": "Parent branch label when adding a child node",
                            },
                            "side": {
                                "type": "string",
                                "enum": ["left", "right"],
                                "description": "Mind map side for a new top-level branch",
                            },
                            "followup": {
                                "type": "string",
                                "description": "Next question when action is ask_followup",
                            },
                            "slot_action": {
                                "type": "string",
                                "enum": [
                                    "update_center",
                                    "add_node",
                                    "update_node",
                                    "delete_node",
                                    "auto_complete_branch",
                                ],
                                "description": "Edit to apply after the user answers ask_followup",
                            },
                        },
                        "required": ["label", "action"],
                    },
                    "minItems": 2,
                    "maxItems": 3,
                },
            },
            ["question", "options"],
        ),
    ]
    return structural + ui_and_meta


def node_action_tool_names() -> set[str]:
    """Registered OpenAI tool names from ``build_node_action_tools``."""
    return {t["function"]["name"] for t in build_node_action_tools()}


def render_library_prompt(lang: Lang = "zh") -> str:
    """Short leftover catalog for the one-shot node-action parser (not the typed loop)."""
    use_zh = lang != "en"
    lines: List[str] = [
        "Node action tools:",
    ]
    for row in NODE_ACTION_ROWS:
        if row["name"] == "none":
            continue
        tool = row["tool_name"]
        desc = row["description_zh"] if use_zh else row["description_en"]
        when = row["when_to_use_zh"] if use_zh else row["when_to_use_en"]
        lines.append(f"- {tool}: {desc}. {when}.")
    lines.extend(
        [
            "Prefer node_id from Current diagram JSON. Never invent node_id for a new node.",
            "If ambiguous, call node_action.clarify_options.",
        ]
    )
    return "\n".join(lines)


def _option_to_command(option: Dict[str, Any]) -> Dict[str, Any]:
    action = str(option.get("action") or "").strip()
    cmd: Dict[str, Any] = {"action": action, "confidence": 0.9}
    for key in (
        "target",
        "node_identifier",
        "new_text",
        "parent_ref",
        "side",
        "node_id",
        "followup",
        "slot_action",
    ):
        val = option.get(key)
        if isinstance(val, str) and val.strip():
            cmd[key] = val.strip()
    # update_node legacy execute path keys off ``target``; clarify may only set new_text.
    if action == "update_node":
        target = cmd.get("target")
        new_text = cmd.get("new_text")
        if not (isinstance(target, str) and target.strip()) and isinstance(new_text, str):
            cmd["target"] = new_text
    return cmd


def command_from_tool_call(name: str, arguments_json: str) -> Dict[str, Any]:
    """Map node-action tool call to legacy Kitty command dict."""
    if name.startswith("diagram."):
        return diagram_edit_function_call_to_legacy_command(name, arguments_json)

    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        args = {}
    if not isinstance(args, dict):
        args = {}

    if name == "node_action.auto_complete_branch":
        target = args.get("target") or args.get("node_label") or args.get("text")
        node_id = args.get("node_id")
        cmd: Dict[str, Any] = {"action": "auto_complete_branch", "confidence": 0.95}
        if isinstance(node_id, str) and node_id.strip():
            cmd["node_id"] = node_id.strip()
        if isinstance(target, str) and target.strip():
            cmd["target"] = target.strip()
        return cmd

    if name == "node_action.auto_complete":
        return {"action": "auto_complete", "confidence": 0.95}

    if name == "node_action.set_content_level":
        level = args.get("level")
        cmd = {"action": "set_content_level", "confidence": 0.95}
        if isinstance(level, str) and level.strip():
            cmd["level"] = level.strip()
        return cmd

    if name == "node_action.set_branch_numbering":
        prefix = args.get("prefix") or args.get("style")
        enabled = args.get("enabled")
        if isinstance(prefix, str) and prefix.strip() and enabled is not False:
            enabled_flag = True
        else:
            enabled_flag = enabled is True
        numbering: Dict[str, Any] = {
            "action": "set_branch_numbering",
            "enabled": enabled_flag,
            "confidence": 0.95,
        }
        if enabled_flag and isinstance(prefix, str) and prefix.strip():
            numbering["prefix"] = prefix.strip()
        return numbering

    if name == "node_action.clarify_options":
        question = args.get("question")
        raw_options = args.get("options")
        options: List[Dict[str, Any]] = []
        labels: List[str] = []
        if isinstance(raw_options, list):
            for item in raw_options[:3]:
                if not isinstance(item, dict):
                    continue
                label = item.get("label")
                if not isinstance(label, str) or not label.strip():
                    continue
                labels.append(label.strip())
                options.append(_option_to_command(item))
        cmd = {
            "action": "clarify_options",
            "confidence": 0.85,
            "options": labels,
            "option_commands": options,
        }
        if isinstance(question, str) and question.strip():
            cmd["question"] = question.strip()
        return cmd

    return {"action": "none", "confidence": 0.0}


def extract_mindmap_topic(diagram_data: Dict[str, Any]) -> str:
    """Extract center/topic text from mindmap diagram_data."""
    ctr = diagram_data.get("center")
    if isinstance(ctr, dict):
        text = ctr.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    topic_raw = diagram_data.get("topic")
    if isinstance(topic_raw, str) and topic_raw.strip():
        return topic_raw.strip()
    if ctr and not isinstance(ctr, dict):
        return str(ctr).strip()
    return ""


def extract_branch_labels(diagram_data: Dict[str, Any], limit: int = 20) -> List[str]:
    """Top-level branch labels from mindmap children."""
    children = diagram_data.get("children")
    if not isinstance(children, list):
        return []
    labels: List[str] = []
    for node in children[:limit]:
        if isinstance(node, str) and node.strip():
            labels.append(node.strip())
        elif isinstance(node, dict):
            text = node.get("text") or node.get("label")
            if isinstance(text, str) and text.strip():
                labels.append(text.strip())
    return labels


def render_diagram_snapshot_block(
    session_context: Dict[str, Any],
    *,
    diagram_type: str,
    lang: Lang = "zh",
) -> str:
    """Full diagram JSON snapshot for the node-action agent user prompt."""
    block, _truncated = serialize_diagram_for_node_action(
        session_context,
        diagram_type=diagram_type,
        lang=lang,
    )
    return block
