"""Auto-complete tasks send native JSON Schema, not JSON Object."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agents.core.llm_spec_stream import dispatch_llm_chat
from agents.core.structured_output import structured_output_scope
from clients.llm.structured_output import (
    DASHSCOPE_DEEPSEEK_V41_FLASH,
    apply_responses_text_format,
    apply_structured_output,
    bind_llm_call,
    bind_llm_log_topic,
    llm_failed_message,
    llm_finished_message,
    response_format_for_dashscope_deepseek,
)
from prompts.autocomplete_json_schema import (
    branch_expand_response_format,
    diagram_spec_response_format,
    requirements_response_format,
)


def test_bilingual_mind_map_schema_requires_secondary() -> None:
    """A bilingual mind map schema requires a matching secondary object."""
    envelope = diagram_spec_response_format("mindmap", bilingual=True)
    assert envelope is not None
    schema = envelope["json_schema"]["schema"]
    assert envelope["type"] == "json_schema"
    assert envelope["json_schema"]["strict"] is True
    assert "secondary" in schema["required"]
    secondary = schema["properties"]["secondary"]
    assert "topic" in secondary["required"]
    assert "children" in secondary["required"]
    assert "secondary" not in secondary["properties"]


def test_single_language_circle_schema_has_no_secondary() -> None:
    """A single-language circle map schema does not require secondary."""
    envelope = diagram_spec_response_format("circle_map", bilingual=False)
    assert envelope is not None
    assert "secondary" not in envelope["json_schema"]["schema"]["required"]


def test_requirements_and_branch_expand_are_schema_tasks() -> None:
    """Requirements and branch expand use a fixed JSON schema."""
    requirements = requirements_response_format("flow_map")
    expand = branch_expand_response_format()
    assert requirements is not None
    assert requirements["json_schema"]["name"] == "flow_map_requirements"
    assert "title" in requirements["json_schema"]["schema"]["required"]
    child = expand["json_schema"]["schema"]["properties"]["children"]["items"]
    assert "children" not in child["properties"]


def test_json_schema_call_omits_max_tokens() -> None:
    """A JSON Schema call drops max_tokens so the provider can finish the object."""
    payload: dict[str, Any] = {"max_tokens": 1000, "model": "qwen"}
    apply_structured_output(
        payload,
        {"type": "json_schema", "json_schema": {"name": "circle_map_spec", "strict": True, "schema": {}}},
    )
    assert "max_tokens" not in payload
    assert payload["response_format"]["type"] == "json_schema"


def test_json_object_call_keeps_max_tokens() -> None:
    """A JSON Object call keeps the caller max_tokens."""
    payload: dict[str, Any] = {"max_tokens": 1000}
    apply_structured_output(payload, {"type": "json_object"})
    assert payload["max_tokens"] == 1000


def _bubble_schema() -> dict[str, Any]:
    envelope = diagram_spec_response_format("bubble_map", bilingual=False)
    assert envelope is not None
    return envelope


def test_dashscope_deepseek_flash_chat_uses_json_object() -> None:
    """DashScope deepseek-v4.1-flash keeps JSON mode and drops the schema."""
    payload: dict[str, Any] = {"max_tokens": 1000, "model": DASHSCOPE_DEEPSEEK_V41_FLASH}
    apply_structured_output(payload, _bubble_schema(), model=DASHSCOPE_DEEPSEEK_V41_FLASH)
    assert payload["response_format"] == {"type": "json_object"}
    assert "max_tokens" not in payload


def test_json_output_log_names_task_format_and_model(caplog: pytest.LogCaptureFixture) -> None:
    """The line names the task, the format change, and the route that served it."""
    payload: dict[str, Any] = {"max_tokens": 1000}
    with caplog.at_level(logging.INFO, logger="clients.llm.structured_output"):
        with bind_llm_log_topic("苹果\n脆甜"):
            with bind_llm_call("autocomplete", "bubble_map", "express"):
                apply_structured_output(payload, _bubble_schema(), model=DASHSCOPE_DEEPSEEK_V41_FLASH)
    message = caplog.records[-1].getMessage()
    assert "\n" not in message
    assert (
        '[LLM] autocomplete bubble_map topic="苹果 脆甜" asked json_schema:bubble_map_spec '
        "sent json_object using express -> deepseek-v4.1-flash via chat, max_tokens omitted"
    ) == message


def test_finish_and_failure_lines_name_the_wire_model() -> None:
    """Finish and failure stay one line and name the id that was posted."""
    with bind_llm_log_topic("苹果"):
        finished = llm_finished_message(
            "autocomplete",
            "bubble_map",
            "express",
            "express",
            1.2,
            DASHSCOPE_DEEPSEEK_V41_FLASH,
        )
        failed = llm_failed_message(
            "autocomplete",
            "bubble_map",
            "express",
            "express",
            0.4,
            "This response_format type\nis unavailable now",
            DASHSCOPE_DEEPSEEK_V41_FLASH,
        )
    assert "\n" not in finished
    assert "\n" not in failed
    assert finished == (
        '[LLM] autocomplete bubble_map topic="苹果" finished in 1.20s using express -> deepseek-v4.1-flash'
    )
    assert failed == (
        '[LLM] autocomplete bubble_map topic="苹果" failed in 0.40s '
        "using express -> deepseek-v4.1-flash: This response_format type is unavailable now"
    )


def test_explicit_json_object_on_flash_keeps_max_tokens() -> None:
    """A caller that asked for json_object keeps the cap on the flash id."""
    payload: dict[str, Any] = {"max_tokens": 1000}
    apply_structured_output(
        payload,
        {"type": "json_object"},
        model=DASHSCOPE_DEEPSEEK_V41_FLASH,
    )
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["max_tokens"] == 1000


def test_other_models_keep_json_schema_on_chat() -> None:
    """Qwen and any non-flash id still send native json_schema."""
    payload: dict[str, Any] = {"max_tokens": 1000, "model": "qwen3.8-flash"}
    apply_structured_output(payload, _bubble_schema(), model="qwen3.8-flash")
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["name"] == "bubble_map_spec"
    assert "max_tokens" not in payload


def test_dashscope_deepseek_flash_responses_uses_json_object() -> None:
    """The same flash id uses json_object on the Responses API."""
    payload: dict[str, Any] = {"model": DASHSCOPE_DEEPSEEK_V41_FLASH}
    apply_responses_text_format(payload, _bubble_schema(), model=DASHSCOPE_DEEPSEEK_V41_FLASH)
    assert payload["text"]["format"] == {"type": "json_object"}


def test_qwen_responses_keeps_json_schema() -> None:
    """Responses text.format carries name, schema, and strict for Qwen."""
    payload: dict[str, Any] = {"model": "qwen3.8-flash"}
    apply_responses_text_format(payload, _bubble_schema(), model="qwen3.8-flash")
    text_format = payload["text"]["format"]
    assert text_format["type"] == "json_schema"
    assert text_format["name"] == "bubble_map_spec"
    assert text_format["strict"] is True
    assert "topic" in text_format["schema"]["properties"]


def test_volcengine_deepseek_endpoint_keeps_schema() -> None:
    """An endpoint id is not DashScope deepseek-v4.1-flash, so the schema stays."""
    chosen = response_format_for_dashscope_deepseek(_bubble_schema(), "ep-20250101000000-dummy")
    assert chosen["type"] == "json_schema"


@pytest.mark.asyncio
async def test_dispatch_uses_schema_scope_for_autocomplete() -> None:
    """Auto-complete dispatch sends the schema that the scope installed."""
    envelope = diagram_spec_response_format("bubble_map", bilingual=False)
    with patch(
        "agents.core.llm_spec_stream.llm_service.chat",
        new=AsyncMock(return_value="{}"),
    ) as mock_chat:
        with structured_output_scope(envelope):
            await dispatch_llm_chat(phase_emit=None, prompt="topic", model="qwen", max_tokens=1000)

    call = mock_chat.await_args
    assert call is not None
    sent = call.kwargs["response_format"]
    assert sent["type"] == "json_schema"
    assert sent["json_schema"]["name"] == "bubble_map_spec"
