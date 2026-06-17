"""Thin tool-calling intent parser (replaces mega JSON prompt for typed text)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from services.kitty.infra.bootstrap.kitty_diagram_vocabulary import (
    KITTY_DIAGRAM_CATALOG_PROMPT,
    KITTY_VOICE_COMMAND_PROMPT,
)
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.omni.tools import build_omni_diagram_tools, omni_function_call_to_command
from services.kitty.session.memory import get_session_memory
from services.llm import llm_service

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
        result = await llm_service.chat(
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
    except (RuntimeError, ValueError, TypeError, KeyError) as exc:
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
    return {"action": "none", "confidence": 0.0}
