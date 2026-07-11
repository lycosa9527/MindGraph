"""LLM node-action agent for one-sentence mindmap edits.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from services.infrastructure.http.error_handler import LLMServiceError, LLMTimeoutError
from services.kitty.context.messaging import resolve_voice_interaction_language
from services.kitty.routing.diagram_agent_context import enrich_node_action_command
from services.kitty.routing.node_action_debug import (
    build_diagram_snapshot_meta,
    clip_node_action_text,
    log_node_action,
    log_node_action_debug,
    summarize_legacy_command,
)
from services.kitty.routing.node_action_library import (
    Lang,
    build_node_action_tools,
    command_from_tool_call,
    render_diagram_snapshot_block,
    render_library_prompt,
)
from services.kitty.session.memory import get_session_memory
from services.llm import llm_service
from services.utils.error_types import LLM_PIPELINE_ERRORS

ONE_SENTENCE_EDIT_DASHSCOPE_MODEL = "qwen3.6-flash"

_STRUCTURAL_ACTIONS = frozenset(
    {
        "update_center",
        "update_node",
        "add_node",
        "delete_node",
    }
)
_AUTOCOMPLETE_ACTIONS = frozenset({"auto_complete", "auto_complete_branch"})
_ALSO_AUTOCOMPLETE_RE = re.compile(
    r"(?:并|然后|再|and\s+then|then)?\s*"
    r"(?:自动)?(?:补全|补完|完善|填充|auto[-\s]?complete)",
    re.IGNORECASE,
)


def _extract_tool_call_entry(
    entry: Any,
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    """Return (tool_name, raw_arguments_json, legacy_command) for one tool_calls item."""
    if not isinstance(entry, dict):
        return None, None, None
    fn = entry.get("function")
    if not isinstance(fn, dict):
        return None, None, None
    name = fn.get("name")
    args_raw = fn.get("arguments") or "{}"
    if not isinstance(name, str):
        return None, None, None
    args_text = str(args_raw)
    cmd = command_from_tool_call(name, args_text)
    return name, args_text, cmd


def _action_sort_key(cmd: Dict[str, Any]) -> Tuple[int, int]:
    """Structural edits before auto-complete; preserve relative order within a tier."""
    action = str(cmd.get("action") or "")
    if action in _STRUCTURAL_ACTIONS:
        return (0, 0)
    if action in _AUTOCOMPLETE_ACTIONS:
        return (1, 0)
    if action == "clarify_options":
        return (2, 0)
    return (3, 0)


def _merge_tool_call_commands(
    commands: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Collapse one or more tool-call commands into a primary + follow_up_actions.

    Clarify-only responses stay single. Structural + auto-complete become two steps.
    """
    usable = [dict(cmd) for cmd in commands if isinstance(cmd, dict) and cmd.get("action") not in (None, "none")]
    if not usable:
        return None
    if any(str(cmd.get("action") or "") == "clarify_options" for cmd in usable):
        for cmd in usable:
            if str(cmd.get("action") or "") == "clarify_options":
                return cmd
    ordered = sorted(enumerate(usable), key=lambda item: (_action_sort_key(item[1]), item[0]))
    ordered_cmds = [item[1] for item in ordered]
    primary = dict(ordered_cmds[0])
    follow_ups = [dict(cmd) for cmd in ordered_cmds[1:]]
    if follow_ups:
        primary["follow_up_actions"] = follow_ups
    return primary


def _user_also_asks_autocomplete(user_line: str) -> bool:
    """True when the utterance also asks for auto-complete / 补全."""
    text = (user_line or "").strip()
    if not text:
        return False
    return bool(_ALSO_AUTOCOMPLETE_RE.search(text))


def attach_autocomplete_follow_up_if_needed(
    command: Dict[str, Any],
    user_line: str,
) -> Dict[str, Any]:
    """
    If the model returned only a structural edit but the user also asked to
    auto-complete, append the matching follow-up action.
    """
    action = str(command.get("action") or "")
    if action not in _STRUCTURAL_ACTIONS:
        return command
    existing = command.get("follow_up_actions")
    if isinstance(existing, list) and existing:
        return command
    if not _user_also_asks_autocomplete(user_line):
        return command
    out = dict(command)
    if action == "update_center":
        out["follow_up_actions"] = [{"action": "auto_complete", "confidence": 0.9}]
        return out
    if action in ("add_node", "update_node"):
        follow: Dict[str, Any] = {"action": "auto_complete_branch", "confidence": 0.9}
        target = command.get("target")
        if isinstance(target, str) and target.strip():
            follow["target"] = target.strip()
        node_id = command.get("node_id")
        if isinstance(node_id, str) and node_id.strip():
            follow["node_id"] = node_id.strip()
        elif action == "update_node":
            ident = command.get("node_identifier")
            if isinstance(ident, str) and ident.strip() and "target" not in follow:
                follow["target"] = ident.strip()
        out["follow_up_actions"] = [follow]
        return out
    return command


def _empty_llm_hint(result: Any) -> str:
    if not isinstance(result, dict):
        return "non-dict result"
    content = result.get("content")
    if isinstance(content, str) and content.strip():
        return f"content={clip_node_action_text(content.strip(), 80)}"
    tool_calls = result.get("tool_calls")
    if isinstance(tool_calls, list):
        return f"tool_calls={len(tool_calls)}"
    return "no tool_calls"


async def parse_node_action_intent(
    command_text: str,
    *,
    voice_session_id: str,
    diagram_type: str,
    session_context: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Parse one-sentence edit via node-action library + diagram snapshot.

    Returns a legacy command dict on success (optionally with
    ``follow_up_actions``), or ``None`` when no tool call (caller should fall
    back to heuristics).
    """
    ctx = dict(session_context or {})
    lang_code = resolve_voice_interaction_language(ctx)
    lang: Lang = "en" if lang_code == "en" else "zh"
    memory = get_session_memory(voice_session_id)
    recent = memory.summarize_for_parser(5)
    library = render_library_prompt(lang)
    snapshot = render_diagram_snapshot_block(ctx, diagram_type=diagram_type, lang=lang)
    snapshot_meta = build_diagram_snapshot_meta(ctx, diagram_type=diagram_type)
    user_line = command_text.strip()

    log_node_action(
        "agent_start",
        voice_session_id=voice_session_id,
        detail=f"text={clip_node_action_text(user_line)} lang={lang} model={ONE_SENTENCE_EDIT_DASHSCOPE_MODEL}",
        extra={
            "snapshot": snapshot_meta,
            "recent_turns": len(recent.splitlines()) if recent else 0,
        },
    )
    log_node_action_debug(
        "agent_prompt_snapshot",
        voice_session_id=voice_session_id,
        detail=clip_node_action_text(snapshot, 200),
    )

    if lang == "en":
        system = (
            "You are Kitty's mind map edit router. "
            "The user wants a canvas change. "
            "Call one or more tools from the library in execution order. "
            "If the user asks to change the topic/center AND auto-complete, "
            "call diagram.update_center first, then node_action.auto_complete "
            "(two separate tool calls). "
            "If the user asks to add a NEW branch AND auto-complete/fill it, "
            "call diagram.add_node first, then node_action.auto_complete_branch "
            "with the same branch label (two separate tool calls). "
            "Never reply with plain text.\n\n" + library
        )
        user_prompt = f"{snapshot}\nRecent turns:\n{recent or '(none)'}\nUser: {user_line}"
    else:
        system = (
            "你是 Kitty 的思维导图编辑路由。 "
            "用户想要修改画布。 "
            "从动作库中按执行顺序调用一个或多个工具。 "
            "若用户同时要求改主题/中心并自动补全，先调用 diagram.update_center，"
            "再调用 node_action.auto_complete（两次独立工具调用）。 "
            "若用户要求新增分支并补全/填充该分支，先调用 diagram.add_node，"
            "再调用 node_action.auto_complete_branch（同一分支名，两次独立工具调用）。 "
            "不要用纯文本回复。\n\n" + library
        )
        user_prompt = f"{snapshot}\n最近对话:\n{recent or '（无）'}\n用户: {user_line}"

    try:
        result = await llm_service.chat_raw(
            prompt=user_prompt,
            model=ONE_SENTENCE_EDIT_DASHSCOPE_MODEL,
            temperature=0.0,
            max_tokens=400,
            timeout=10.0,
            tools=build_node_action_tools(),
            tool_choice="auto",
            system_message=system,
            user_id=user_id,
            organization_id=organization_id,
            request_type="node_action_agent",
            diagram_type=diagram_type,
            session_id=voice_session_id,
            endpoint_path="/ws/kitty",
            use_knowledge_base=False,
        )
        raw_calls = result.get("tool_calls") if isinstance(result, dict) else None
        extracted: List[Dict[str, Any]] = []
        tool_names: List[str] = []
        if isinstance(raw_calls, list):
            for entry in raw_calls:
                tool_name, tool_args, cmd = _extract_tool_call_entry(entry)
                if tool_name:
                    tool_names.append(tool_name)
                    log_node_action_debug(
                        "agent_tool_call",
                        voice_session_id=voice_session_id,
                        detail=f"tool={tool_name}",
                        extra={"arguments": clip_node_action_text(tool_args or "{}", 200)},
                    )
                if cmd and cmd.get("action") not in (None, "none"):
                    extracted.append(cmd)

        cmd = _merge_tool_call_commands(extracted)
        if cmd is not None:
            cmd = attach_autocomplete_follow_up_if_needed(cmd, user_line)
            cmd = enrich_node_action_command(cmd, ctx)
            act = str(cmd.get("action") or "")
            log_node_action(
                "agent_mapped",
                voice_session_id=voice_session_id,
                detail=summarize_legacy_command(cmd),
                action=act,
                extra={
                    "tools": tool_names,
                    "follow_ups": len(cmd.get("follow_up_actions") or []),
                    "snapshot": snapshot_meta,
                },
            )
            return cmd

        hint = _empty_llm_hint(result)
        log_node_action(
            "agent_no_tool",
            voice_session_id=voice_session_id,
            detail=hint,
            extra={"snapshot": snapshot_meta},
        )
    except (
        LLMTimeoutError,
        LLMServiceError,
        *LLM_PIPELINE_ERRORS,
    ) as exc:
        log_node_action(
            "agent_failed",
            voice_session_id=voice_session_id,
            detail=f"{type(exc).__name__}: {exc}",
            extra={"snapshot": snapshot_meta},
        )
        return None

    return None
