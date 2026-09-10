"""OpenAI-compatible transcript helpers for the typed Kitty agent loop.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal

from services.kitty.agent_loop.results import encode_tool_content

LoopMode = Literal["edit", "general"]


def build_system_prompt(mode: LoopMode, *, lang: str) -> str:
    """Short identity only — tool schemas carry when-to-use."""
    if lang == "en":
        if mode == "edit":
            return (
                "You are Kitty's mind-map edit agent. "
                "Call tools to change the canvas. "
                "Prefer node_id from the Current diagram JSON for existing nodes. "
                "Never invent node_id for a new node; use created ids from tool results. "
                "Do not use path or leftover branch-* ids as keys. "
                "Greetings and vague asks (hi, change this) must call "
                "node_action.clarify_options with 2-3 short suggestions. "
                "If the user wants to add a branch but did not name it, ask for "
                "the name (ask_followup / add_node). Do not ask placement first. "
                "Never reply with only text when the intent is unclear. "
                "When the goal is done, reply with a short confirmation and no tools. "
                "If you cannot apply a change, say so briefly without pretending it applied."
            )
        return (
            "You are Kitty. Call tools for canvas or UI actions. "
            "Prefer node_id from the Current diagram JSON. "
            "Never invent node_id for a new node. "
            "If the user is only chatting, reply with text and no tools."
        )
    if mode == "edit":
        return (
            "你是 Kitty 的思维导图编辑代理。"
            "用工具修改画布。"
            "已有节点优先使用 Current diagram JSON 中的 node_id。"
            "不要为新节点编造 node_id，使用工具结果里的 created id。"
            "不要把 path 或遗留的 branch-* 当作主键。"
            "问候或「改一下/这个」等意图不清时，必须调用 node_action.clarify_options，"
            "给出 2–3 个短建议，不要只用纯文本回复。"
            "用户要加分支但没说名称时，问分支名（ask_followup / add_node），不要先问位置。"
            "完成后用一句短确认结束，不要再调用工具。"
            "无法修改时如实说明，不要假装已应用。"
        )
    return (
        "你是 Kitty。画布或界面操作请调用工具。"
        "已有节点优先使用 Current diagram JSON 中的 node_id。"
        "不要为新节点编造 node_id。"
        "若用户只是闲聊，用纯文本回复且不要调用工具。"
    )


def build_user_turn(
    user_text: str,
    *,
    snapshot: str,
    recent: str,
    lang: str,
    pending_clarify_note: str = "",
) -> str:
    """First user message: snapshot + compact memory + utterance."""
    if lang == "en":
        pending_label = "Unanswered clarify"
        compact_label = "Context"
        user_label = "User"
        empty = "(none)"
    else:
        pending_label = "未回答的确认"
        compact_label = "上下文"
        user_label = "用户"
        empty = "（无）"
    parts = [snapshot]
    if pending_clarify_note.strip():
        parts.append(f"{pending_label}:\n{pending_clarify_note.strip()}")
    parts.append(f"{compact_label}:\n{recent.strip() or empty}")
    parts.append(f"{user_label}: {user_text.strip()}")
    return "\n".join(parts)


def build_initial_messages(
    *,
    mode: LoopMode,
    user_text: str,
    snapshot: str,
    recent: str,
    lang: str,
    pending_clarify_note: str = "",
) -> List[Dict[str, Any]]:
    """system + user transcript for the first ``chat_raw`` call."""
    return [
        {"role": "system", "content": build_system_prompt(mode, lang=lang)},
        {
            "role": "user",
            "content": build_user_turn(
                user_text,
                snapshot=snapshot,
                recent=recent,
                lang=lang,
                pending_clarify_note=pending_clarify_note,
            ),
        },
    ]


def extract_assistant_text(result: Any) -> str:
    """Plain assistant text when the model stops without tools."""
    if not isinstance(result, dict):
        return ""
    content = result.get("content")
    if isinstance(content, str):
        return content.strip()
    return ""


def extract_tool_calls(result: Any) -> List[Dict[str, Any]]:
    """Normalize provider tool_calls to ``{id, name, arguments}``."""
    if not isinstance(result, dict):
        return []
    raw = result.get("tool_calls")
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            continue
        fn = entry.get("function")
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        args_raw = fn.get("arguments")
        if isinstance(args_raw, str):
            args_text = args_raw
        else:
            args_text = "{}"
        call_id = entry.get("id")
        if not isinstance(call_id, str) or not call_id.strip():
            call_id = f"call_{index}"
        out.append({"id": call_id.strip(), "name": name.strip(), "arguments": args_text})
    return out


def append_assistant_tool_calls(
    messages: List[Dict[str, Any]],
    tool_calls: List[Dict[str, Any]],
) -> None:
    """Append the assistant message that requested tools."""
    serialized: List[Dict[str, Any]] = []
    for item in tool_calls:
        serialized.append(
            {
                "id": item["id"],
                "type": "function",
                "function": {
                    "name": item["name"],
                    "arguments": item.get("arguments") or "{}",
                },
            }
        )
    messages.append({"role": "assistant", "content": None, "tool_calls": serialized})


def append_tool_message(
    messages: List[Dict[str, Any]],
    *,
    tool_call_id: str,
    payload: Dict[str, Any],
) -> None:
    """Append a standard ``role: tool`` row."""
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": encode_tool_content(payload),
        }
    )


def read_diagram_tool_schema() -> Dict[str, Any]:
    """Optional refresh tool (identity fields only in the returned snapshot)."""
    return {
        "type": "function",
        "function": {
            "name": "read_diagram",
            "description": (
                "Re-read the current diagram snapshot (id, text, type, path) "
                "when the last tool result is stale or a node id is missing."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }
