"""Auto-complete tasks send native JSON Schema, not JSON Object."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from agents.core.llm_spec_stream import dispatch_llm_chat
from agents.core.structured_output import structured_output_scope
from clients.llm.structured_output import apply_structured_output
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
