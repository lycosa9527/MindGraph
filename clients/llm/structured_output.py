"""JSON output for chat completions and the Responses API.

Both APIs accept ``json_object`` and ``json_schema``. Chat completions put the
choice in ``response_format``. The Responses API puts the same choice in
``text.format``.

DashScope ``deepseek-v4.1-flash`` chat completions reject ``json_schema``
(``This response_format type is unavailable now``). That model id uses
``json_object`` on both APIs. Qwen and Volcengine DeepSeek keep ``json_schema``.

A token cap truncates the JSON object. Chat calls that asked for
``json_schema`` omit ``max_tokens``, including the flash rewrite to
``json_object``. An explicit ``json_object`` request keeps its cap.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


JSON_OBJECT_RESPONSE_FORMAT: dict[str, str] = {"type": "json_object"}

# Physical DashScope id for Express and the DashScope DeepSeek leg.
DASHSCOPE_DEEPSEEK_V41_FLASH = "deepseek-v4.1-flash"


def is_json_schema_format(response_format: Any) -> bool:
    """True when the caller asked for native JSON Schema output."""
    return isinstance(response_format, dict) and response_format.get("type") == "json_schema"


def is_json_object_format(response_format: Any) -> bool:
    """True when the caller asked for JSON object mode."""
    return isinstance(response_format, dict) and response_format.get("type") == "json_object"


def dashscope_deepseek_flash_uses_json_object(model: str | None) -> bool:
    """True for the DashScope model id that rejects ``json_schema``."""
    return (model or "").strip() == DASHSCOPE_DEEPSEEK_V41_FLASH


def response_format_for_dashscope_deepseek(response_format: Any, model: str | None) -> Any:
    """Keep the requested format, except DashScope ``deepseek-v4.1-flash``.

    That id receives ``json_object`` when the caller asked for ``json_schema``.
    Every other model, including Volcengine DeepSeek, keeps ``json_schema``.
    """
    if dashscope_deepseek_flash_uses_json_object(model) and is_json_schema_format(response_format):
        return dict(JSON_OBJECT_RESPONSE_FORMAT)
    return response_format


def _format_kind(response_format: Any) -> str:
    """Short label for logs: ``json_object`` or ``json_schema:<name>``."""
    if not isinstance(response_format, dict):
        return "none"
    kind = response_format.get("type")
    if kind == "json_object":
        return "json_object"
    if kind != "json_schema":
        return "other"
    nested = response_format.get("json_schema")
    name = ""
    if isinstance(nested, dict) and isinstance(nested.get("name"), str):
        name = nested["name"].strip()
    elif isinstance(response_format.get("name"), str):
        name = str(response_format["name"]).strip()
    if name:
        return f"json_schema:{name}"
    return "json_schema"


@dataclass
class _LlmCall:
    """The job in flight: which task, which diagram, which route, which wire id."""

    task: str
    subject: str
    route: str
    wire: str = ""


_CALL: ContextVar[_LlmCall | None] = ContextVar("llm_call", default=None)
_TOPIC: ContextVar[str] = ContextVar("llm_log_topic", default="")
_TOPIC_LIMIT = 80


def _piece(value: str | None) -> str:
    """One log token, or empty when the caller has nothing to name."""
    return (value or "").strip()


def one_line(value: str | None, limit: int = _TOPIC_LIMIT) -> str:
    """Collapse whitespace so a topic cannot split a log record."""
    text = " ".join((value or "").split())
    text = text.replace('"', "'")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


@contextmanager
def bind_llm_log_topic(topic: str | None) -> Iterator[None]:
    """Pin the diagram topic for every LLM log in this task."""
    token = _TOPIC.set(one_line(topic))
    try:
        yield
    finally:
        _TOPIC.reset(token)


def push_llm_log_topic(topic: str | None) -> Token[str]:
    """Pin the topic and return the token that restores the previous one."""
    return _TOPIC.set(one_line(topic))


def reset_llm_log_topic(token: Token[str]) -> None:
    """Restore the topic pinned before ``push_llm_log_topic``."""
    _TOPIC.reset(token)


def note_llm_log_topic(topic: str | None) -> None:
    """Replace the pinned topic after requirements extraction resolves it."""
    _TOPIC.set(one_line(topic))


def _topic_clause() -> str:
    """``topic="..."`` or empty when this call has no topic."""
    topic = _TOPIC.get()
    if not topic:
        return ""
    return f'topic="{topic}"'


def _actor(task: str, subject: str) -> str:
    """Task and diagram, the thing this user is doing."""
    parts = [part for part in (task, subject) if part]
    return " ".join(parts)


def _using(route: str, wire: str, api: str) -> str:
    """Route and physical model, and the API when this is the outbound call."""
    if route and wire and route != wire:
        whom = f"{route} -> {wire}"
    else:
        whom = wire or route or "missing"
    if api:
        return f"{whom} via {api}"
    return whom


@contextmanager
def bind_llm_call(task: str | None, subject: str | None, route: str | None) -> Iterator[_LlmCall]:
    """Pin the current job so client logs can name the task and the route."""
    call = _LlmCall(_piece(task), _piece(subject), _piece(route))
    token = _CALL.set(call)
    try:
        yield call
    finally:
        _CALL.reset(token)


def _whom(route: str | None, actual: str | None, wire: str | None) -> str:
    """Prefer the id posted to the provider, then the routed client."""
    return _using(_piece(route), _piece(wire) or _piece(actual), "")


def _actor_with_topic(task: str | None, subject: str | None) -> str:
    """Task, diagram, and topic, each already a single token or short phrase."""
    return " ".join(part for part in (_actor(_piece(task), _piece(subject)), _topic_clause()) if part)


def llm_finished_message(
    task: str | None,
    subject: str | None,
    route: str | None,
    actual: str | None,
    duration: float,
    wire: str | None = None,
) -> str:
    """One finish line: which task, how long, which model served it."""
    actor = _actor_with_topic(task, subject)
    whom = _whom(route, actual, wire)
    if actor:
        return f"[LLM] {actor} finished in {duration:.2f}s using {whom}"
    return f"[LLM] finished in {duration:.2f}s using {whom}"


def llm_failed_message(
    task: str | None,
    subject: str | None,
    route: str | None,
    actual: str | None,
    duration: float,
    detail: str,
    wire: str | None = None,
) -> str:
    """One failure line. The provider text is collapsed so it cannot wrap."""
    actor = _actor_with_topic(task, subject)
    whom = _whom(route, actual, wire)
    if actor:
        head = f"[LLM] {actor} failed in {duration:.2f}s using {whom}"
    else:
        head = f"[LLM] failed in {duration:.2f}s using {whom}"
    reason = one_line(detail, 160)
    if reason:
        return f"{head}: {reason}"
    return head


def _log_json_output(
    api: str,
    model: str | None,
    asked: Any,
    sent: Any,
    *,
    max_tokens: str,
) -> None:
    """Record who asked for which format, and which model received it."""
    wire = (model or "").strip()
    call = _CALL.get()
    if call is not None and wire:
        call.wire = wire
    task = call.task if call is not None else ""
    subject = call.subject if call is not None else ""
    route = call.route if call is not None else ""
    actor = " ".join(part for part in (_actor(task, subject), _topic_clause()) if part)
    whom = _using(route, wire, api)
    action = f"asked {_format_kind(asked)} sent {_format_kind(sent)} using {whom}"
    if max_tokens == "omitted":
        action = f"{action}, max_tokens omitted"
    if not wire and is_json_schema_format(asked):
        action = f"{action}, model id missing"
    message = f"[LLM] {actor} {action}" if actor else f"[LLM] {action}"
    logger.info("%s", " ".join(message.split()))


def apply_structured_output(
    payload: dict[str, Any],
    response_format: Any,
    *,
    model: str | None = None,
) -> None:
    """Attach chat-completions ``response_format``.

    ``model`` is the physical id on the wire. A ``json_schema`` request drops
    ``max_tokens`` even when flash is rewritten to ``json_object``.
    """
    asked_schema = is_json_schema_format(response_format)
    chosen = response_format_for_dashscope_deepseek(response_format, model)
    if chosen is None:
        return
    payload["response_format"] = chosen
    if asked_schema:
        payload.pop("max_tokens", None)
    _log_json_output(
        "chat",
        model,
        response_format,
        chosen,
        max_tokens="omitted" if asked_schema else "kept",
    )


def responses_text_format(response_format: Any, model: str | None) -> dict[str, Any] | None:
    """Map a chat ``response_format`` onto Responses ``text.format``.

    ``json_object`` stays ``{"type": "json_object"}``. ``json_schema`` becomes
    the Responses object (``name``, ``schema``, ``strict`` at the top level).
    DashScope ``deepseek-v4.1-flash`` is forced to ``json_object``.
    """
    chosen = response_format_for_dashscope_deepseek(response_format, model)
    if is_json_object_format(chosen):
        return dict(JSON_OBJECT_RESPONSE_FORMAT)
    if not is_json_schema_format(chosen):
        return None
    schema = chosen.get("json_schema")
    if not isinstance(schema, dict):
        return dict(JSON_OBJECT_RESPONSE_FORMAT)
    name = schema.get("name")
    body = schema.get("schema")
    if not isinstance(name, str) or not name.strip() or not isinstance(body, dict):
        return dict(JSON_OBJECT_RESPONSE_FORMAT)
    return {
        "type": "json_schema",
        "name": name.strip(),
        "schema": body,
        "strict": schema.get("strict") is not False,
    }


def apply_responses_text_format(
    payload: dict[str, Any],
    response_format: Any,
    *,
    model: str | None,
) -> None:
    """Set Responses ``text.format`` when the caller asked for JSON output."""
    text_format = responses_text_format(response_format, model)
    if text_format is None:
        return
    text = payload.get("text")
    if not isinstance(text, dict):
        text = {}
        payload["text"] = text
    text["format"] = text_format
    _log_json_output("responses", model, response_format, text_format, max_tokens="unchanged")
