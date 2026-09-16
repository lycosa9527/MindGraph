"""generate_png / DingTalk share run_prompt_to_diagram_llm prep."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from agents.core import prompt_to_diagram_run as p2d


@pytest.mark.asyncio
async def test_run_prompt_to_diagram_merges_nl_audience() -> None:
    """PNG and DingTalk both get the canvas 小学 block in the one-shot prompt."""
    captured: dict[str, str] = {}

    async def _chat(**kwargs: object) -> tuple[str, dict[str, int]]:
        captured["prompt"] = str(kwargs["prompt"])
        return ('{"diagram_type":"mind_map","spec":{"topic":"T"}}', {"total_tokens": 1})

    with (
        patch.object(p2d, "get_prompt", return_value="User: {user_prompt}"),
        patch.object(p2d.llm_service, "chat_with_usage", new=AsyncMock(side_effect=_chat)),
    ):
        run = await p2d.run_prompt_to_diagram_llm(
            prompt="画一个光合作用的思维导图，小学水平",
            language="zh",
            user_id=None,
            organization_id=None,
            api_key_id=None,
            endpoint_path="/api/generate_png",
        )

    assert run.missing_template is False
    assert run.empty_response is False
    assert run.prepared.ai_content_level == "primary"
    assert "请按「小学」专业程度生成内容。" in captured["prompt"]
    topic_part = captured["prompt"].split("【用户要求】", maxsplit=1)[0]
    assert "小学水平" not in topic_part


@pytest.mark.asyncio
async def test_run_prompt_to_diagram_uses_org_cache_namespace() -> None:
    """PNG / DingTalk share orgllm:prompt_to_diagram and skip a second LLM call."""
    chat = AsyncMock(side_effect=AssertionError("LLM should not run on cache hit"))
    captured: dict[str, object] = {}

    async def _cached(namespace: str, organization_id: object, payload: dict, generate):
        """Record the cache key and return a stored spec without calling generate."""
        captured["namespace"] = namespace
        captured["organization_id"] = organization_id
        captured["payload"] = payload
        del generate
        return {"raw_result": {"diagram_type": "mind_map", "spec": {"topic": "T"}}}

    with (
        patch.object(p2d, "get_prompt", return_value="User: {user_prompt}"),
        patch.object(p2d.llm_service, "chat_with_usage", chat),
        patch.object(p2d, "load_or_generate_org_llm_result", new=_cached),
    ):
        run = await p2d.run_prompt_to_diagram_llm(
            prompt="光合作用",
            language="zh",
            user_id=3,
            organization_id=9,
            api_key_id=None,
            endpoint_path="/api/generate_png",
        )

    assert captured["namespace"] == "prompt_to_diagram"
    assert captured["organization_id"] == 9
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["endpoint"] == "prompt_to_diagram"
    assert payload["prompt"]
    chat.assert_not_awaited()
    assert run.raw_result == {"diagram_type": "mind_map", "spec": {"topic": "T"}}
    assert run.empty_response is False
