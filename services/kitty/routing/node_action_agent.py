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
from services.kitty.routing.node_action_order import order_node_action_commands
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


def _merge_tool_call_commands(
    commands: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    Collapse one or more tool-call commands into a primary + follow_up_actions.

    Clarify-only responses stay single. Mixed tools are ordered by
    ``order_node_action_commands`` (structure before auto-complete).
    """
    usable = [dict(cmd) for cmd in commands if isinstance(cmd, dict) and cmd.get("action") not in (None, "none")]
    if not usable:
        return None
    if any(str(cmd.get("action") or "") == "clarify_options" for cmd in usable):
        for cmd in usable:
            if str(cmd.get("action") or "") == "clarify_options":
                return cmd
    ordered_cmds = order_node_action_commands(usable)
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
            "Exact NEW branch labels require diagram.add_node; "
            "node_action.auto_complete_branch only fills children under an EXISTING node. "
            "If the user changes the topic/center AND wants whole-map fill only, "
            "call diagram.update_center then node_action.auto_complete. "
            "If the user adds ONE new branch (optionally asking to fill it), "
            "prefer diagram.add_node only — the canvas fills new branches after apply. "
            "If the user adds MULTIPLE new named branches (optionally after changing "
            "the topic), call diagram.update_center first when needed, then one "
            "diagram.add_node per branch label in order. Do NOT call "
            "auto_complete_branch between or after those adds, and do NOT call "
            "whole-map auto_complete in the same turn (it would wipe new children); "
            "the server fills those new branches after all structural edits finish. "
            "Always emit tools in this order: update_center, delete_node, "
            "update_node, add_node, then auto_complete_branch / auto_complete last "
            "(and only when needed for EXISTING nodes or whole-map-only requests). "
            "Do not invent node_id for new branches. "
            "Never reply with plain text.\n\n" + library
        )
        user_prompt = f"{snapshot}\nRecent turns:\n{recent or '(none)'}\nUser: {user_line}"
    else:
        system = (
            "你是 Kitty 的思维导图编辑路由。 "
            "用户想要修改画布。 "
            "从动作库中按执行顺序调用一个或多个工具。 "
            "精确的新分支名必须用 diagram.add_node；"
            "node_action.auto_complete_branch 只用于给已存在的分支补子节点。 "
            "若用户只改主题/中心并要求整图补全，先 diagram.update_center，"
            "再 node_action.auto_complete。 "
            "若用户新增一个分支（即使说要补全），优先只调用 diagram.add_node——"
            "画布会在结构修改完成后自动补全新分支。 "
            "若用户一次新增多个命名分支（可同时改主题），需要时先 "
            "diagram.update_center，再按顺序为每个分支名各调用一次 diagram.add_node；"
            "不要在 add_node 之间或之后调用 auto_complete_branch，"
            "也不要在同一轮调用整图 auto_complete（会冲掉刚加的子节点）；"
            "服务端会在全部结构修改完成后为这些新分支补全。 "
            "工具顺序固定为：update_center → delete_node → update_node → "
            "add_node → 最后才是 auto_complete_branch / auto_complete"
            "（且仅在针对已有节点或纯整图补全时需要）。 "
            "不要为新分支编造 node_id。"
            "不要用纯文本回复。\n\n" + library
        )
        user_prompt = f"{snapshot}\n最近对话:\n{recent or '（无）'}\n用户: {user_line}"

    try:
        result = await llm_service.chat_raw(
            prompt=user_prompt,
            model=ONE_SENTENCE_EDIT_DASHSCOPE_MODEL,
            temperature=0.0,
            max_tokens=600,
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
