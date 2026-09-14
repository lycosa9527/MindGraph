"""generate_dingtalk merges canvas 专业程度 when the prompt requests a level."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.core import prompt_to_diagram_run as p2d
from models.requests.requests_diagram import GenerateDingTalkRequest
from routers.api import png_export as mod
from services.diagram.dify_user_resolve import DiagramSaveIdentity


def _user() -> MagicMock:
    user = MagicMock()
    user.id = 7
    user.organization_id = 1
    user.name = "tester"
    return user


def _request() -> MagicMock:
    request = MagicMock()
    request.headers = {"Accept-Language": "zh"}
    request.state = MagicMock()
    request.state.request_id = "req-dt-aud"
    request.state.api_key_id = None
    request.url = MagicMock()
    request.url.scheme = "https"
    request.url.netloc = "example.com"
    return request


async def _run_generate(prompt: str, language: str, captured: dict[str, Any]) -> None:
    async def _chat(**kwargs: object) -> tuple[str, dict[str, int]]:
        captured["prompt"] = kwargs["prompt"]
        return (
            '{"diagram_type":"mind_map","spec":{"topic":"T","children":[]}}',
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    identity = DiagramSaveIdentity(user_id=7, organization_id=1, dify_user_key="")
    req = GenerateDingTalkRequest.model_validate({"prompt": prompt, "language": language})
    with (
        patch.object(mod, "actor_rls_session", return_value=AsyncMock()),
        patch.object(mod, "system_rls_session", return_value=AsyncMock()),
        patch.object(mod, "resolve_diagram_save_identity", new=AsyncMock(return_value=identity)),
        patch.object(p2d, "get_prompt", return_value="User: {user_prompt}"),
        patch.object(p2d.llm_service, "chat_with_usage", new=AsyncMock(side_effect=_chat)),
        patch.object(mod, "capture_diagram_screenshot", new=AsyncMock(return_value=b"PNG")),
        patch.object(mod, "try_save_diagram_to_library", new=AsyncMock(return_value=None)),
        patch.object(mod, "store_generation_preview_outcome", new=AsyncMock(return_value=True)),
        patch.object(mod, "build_public_temp_image_url", return_value="https://x/t.png"),
        patch.object(mod, "generate_signed_url", return_value="/temp_images/x.png?sig=1"),
        patch.object(mod, "persist_dingtalk_temp_png", new=AsyncMock()),
        patch.object(mod, "schedule_module_activity"),
        patch.object(mod, "schedule_user_usage_activity"),
        patch.object(mod, "temp_images_signed_ttl", return_value=86400),
    ):
        response = await mod.generate_dingtalk_png(req, _request(), None, _user())
    assert getattr(response, "status_code", None) == 200


@pytest.mark.asyncio
async def test_generate_dingtalk_merges_canvas_audience_when_prompt_names_level() -> None:
    """小学水平 uses the same canvas instruction block as new-canvas generate."""
    captured: dict[str, Any] = {}
    await _run_generate("画一个光合作用的思维导图，小学水平", "zh", captured)
    prompt = str(captured["prompt"])
    assert "User: 画一个光合作用的思维导图" in prompt
    assert "【用户要求】" in prompt
    assert "请按「小学」专业程度生成内容。" in prompt
    assert "用语：" in prompt
    assert "小学水平" not in prompt.replace("请按「小学」专业程度生成内容。", "")


@pytest.mark.asyncio
async def test_generate_dingtalk_keeps_general_when_prompt_omits_level() -> None:
    """No professional-level phrase means default general and no audience block."""
    captured: dict[str, Any] = {}
    await _run_generate("比较猫和狗", "zh", captured)
    prompt = str(captured["prompt"])
    assert prompt == "User: 比较猫和狗"
    assert "【用户要求】" not in prompt
    assert "专业程度" not in prompt
