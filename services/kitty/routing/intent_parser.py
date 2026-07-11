"""Thin tool-calling intent parser (replaces mega JSON prompt for typed text).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from services.infrastructure.http.error_handler import LLMServiceError, LLMTimeoutError
from services.kitty.infra.bootstrap.kitty_diagram_vocabulary import (
    KITTY_DIAGRAM_CATALOG_PROMPT,
    KITTY_VOICE_COMMAND_PROMPT,
)
from services.kitty.infra.bootstrap.kitty_unsupported_diagram_types import (
    resolve_unsupported_diagram_type,
)
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.omni.tools import build_omni_diagram_tools, omni_function_call_to_command
from services.kitty.routing.diagram_agent_context import enrich_node_action_command
from services.kitty.routing.node_action_agent import parse_node_action_intent
from services.kitty.routing.node_action_debug import (
    log_node_action,
    summarize_legacy_command,
)
from services.kitty.routing.one_sentence_edit_heuristics import (
    heuristic_one_sentence_edit_command,
)
from services.kitty.session.memory import get_session_memory
from services.llm import llm_service
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)


def _tools_for_chat() -> List[Dict[str, Any]]:
    """Tools for chat."""
    return build_omni_diagram_tools()


def _extract_tool_call(result: Any) -> Optional[Dict[str, Any]]:
    """Extract tool call."""
    if not isinstance(result, dict):
        return None
    tool_calls = result.get("tool_calls")
    if not isinstance(tool_calls, list) or not tool_calls:
        return None
    first = tool_calls[0]
    if not isinstance(first, dict):
        return None
    fn = first.get("function")
    if not isinstance(fn, dict):
        return None
    name = fn.get("name")
    args_raw = fn.get("arguments") or "{}"
    if not isinstance(name, str):
        return None
    return omni_function_call_to_command(name, str(args_raw))


async def parse_voice_intent_with_tools(
    command_text: str,
    *,
    voice_session_id: str,
    diagram_type: str,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Parse a short voice/text command via qwen-turbo tool calling.

    Used for typed text inbound; voice audio path prefers Omni native tool calls.
    """
    memory = get_session_memory(voice_session_id)
    recent = memory.summarize_for_parser(5)
    system = (
        "You are a diagram voice command router. "
        "Call exactly one tool when the user wants a canvas/UI action. "
        "If the user is only chatting, do not call any tool."
        + KITTY_DIAGRAM_CATALOG_PROMPT
        + KITTY_VOICE_COMMAND_PROMPT
    )
    user_prompt = f"Diagram type: {diagram_type}\nRecent turns:\n{recent or '(none)'}\nUser: {command_text.strip()}"

    try:
        result = await llm_service.chat_raw(
            prompt=user_prompt,
            model="qwen-turbo",
            temperature=0.1,
            max_tokens=200,
            timeout=5.0,
            tools=_tools_for_chat(),
            tool_choice="auto",
            system_message=system,
            user_id=user_id,
            organization_id=organization_id,
            request_type="voice_command_tools",
            diagram_type=diagram_type,
            session_id=voice_session_id,
            endpoint_path="/ws/kitty",
            use_knowledge_base=False,
        )
        cmd = _extract_tool_call(result)
        if cmd and cmd.get("action") not in (None, "none"):
            act = str(cmd.get("action") or "")
            kitty_wf_log(
                "intent_parse",
                f"tool action={act} conf={cmd.get('confidence', '?')}",
                voice_session_id=voice_session_id,
                action=act,
            )
            return cmd

        content = result.get("content") if isinstance(result, dict) else None
        if isinstance(content, str) and content.strip():
            try:
                parsed = json.loads(content.strip())
                if isinstance(parsed, dict) and parsed.get("action"):
                    act = str(parsed.get("action") or "")
                    kitty_wf_log(
                        "intent_parse",
                        f"json action={act}",
                        voice_session_id=voice_session_id,
                        action=act,
                    )
                    return parsed
            except json.JSONDecodeError:
                pass
    except (
        LLMTimeoutError,
        LLMServiceError,
        *LLM_PIPELINE_ERRORS,
    ) as exc:
        logger.debug("Tool intent parse failed: %s", exc)
        kitty_wf_log(
            "intent_parse",
            f"failed {exc}",
            voice_session_id=voice_session_id,
        )

    kitty_wf_log(
        "intent_parse",
        "no tool match → conversational",
        voice_session_id=voice_session_id,
    )
    unsupported = resolve_unsupported_diagram_type(text=command_text.strip())
    if unsupported is not None:
        kitty_wf_log(
            "intent_parse",
            f"unsupported diagram {unsupported.get('entry_id')}",
            voice_session_id=voice_session_id,
            action="unsupported_diagram_type",
        )
        return {
            "action": "unsupported_diagram_type",
            "requested_label": unsupported.get("requested_type"),
            "confidence": 0.85,
        }
    return {"action": "none", "confidence": 0.0}


async def parse_one_sentence_edit_intent(
    command_text: str,
    *,
    voice_session_id: str,
    diagram_type: str,
    session_context: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
    organization_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Parse one-sentence EDIT phase text via node-action agent.

    Uses ``qwen3.6-flash`` (text chat, not Omni). The LLM agent is primary;
    regex heuristics run only on timeout or empty tool result. Compound
    intents may include ``follow_up_actions`` (e.g. update_center then
    auto_complete).
    """
    cmd = await parse_node_action_intent(
        command_text,
        voice_session_id=voice_session_id,
        diagram_type=diagram_type,
        session_context=session_context,
        user_id=user_id,
        organization_id=organization_id,
    )
    if cmd is not None:
        log_node_action(
            "parse_agent_hit",
            voice_session_id=voice_session_id,
            detail=summarize_legacy_command(cmd),
            action=str(cmd.get("action") or "") or None,
        )
        return cmd

    heuristic = heuristic_one_sentence_edit_command(command_text)
    if heuristic is not None:
        if session_context:
            heuristic = enrich_node_action_command(heuristic, session_context)
        act = str(heuristic.get("action") or "")
        log_node_action(
            "parse_heuristic_fallback",
            voice_session_id=voice_session_id,
            detail=summarize_legacy_command(heuristic),
            action=act,
        )
        return heuristic

    log_node_action(
        "parse_none",
        voice_session_id=voice_session_id,
        detail=f"text={command_text.strip()[:80]}",
    )
    return {"action": "none", "confidence": 0.0}
