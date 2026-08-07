"""generate_dingtalk short RLS sessions around LLM/Playwright."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    request.state.request_id = "req-dt"
    request.state.api_key_id = None
    request.url = MagicMock()
    request.url.scheme = "https"
    request.url.netloc = "example.com"
    return request


@pytest.mark.asyncio
async def test_generate_dingtalk_closes_rls_before_llm_and_screenshot() -> None:
    """Identity session must exit before LLM + Playwright hold no open txn."""
    session_open = {"value": False}
    llm_saw_closed: list[bool] = []
    shot_saw_closed: list[bool] = []

    fake_db = MagicMock()
    fake_cm = MagicMock()

    async def _enter(_self: object) -> MagicMock:
        session_open["value"] = True
        return fake_db

    async def _exit(_self: object, *_args: object) -> bool:
        session_open["value"] = False
        return False

    fake_cm.__aenter__ = _enter
    fake_cm.__aexit__ = _exit

    async def _chat(**_kwargs: object) -> tuple[str, dict]:
        llm_saw_closed.append(not session_open["value"])
        return (
            '{"diagram_type":"mind_map","spec":{"topic":"T","children":[]}}',
            {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        )

    async def _shot(**_kwargs: object) -> bytes:
        shot_saw_closed.append(not session_open["value"])
        return b"PNG"

    identity = DiagramSaveIdentity(user_id=7, organization_id=1, dify_user_key="")
    req = GenerateDingTalkRequest.model_validate({"prompt": "draw a map", "language": "zh"})

    with (
        patch.object(mod, "actor_rls_session", return_value=fake_cm),
        patch.object(mod, "system_rls_session", return_value=fake_cm),
        patch.object(
            mod,
            "resolve_diagram_save_identity",
            new=AsyncMock(return_value=identity),
        ),
        patch.object(mod, "get_prompt", return_value="User: {user_prompt}"),
        patch.object(mod.llm_service, "chat_with_usage", new=AsyncMock(side_effect=_chat)),
        patch.object(mod, "capture_diagram_screenshot", new=AsyncMock(side_effect=_shot)),
        patch.object(mod, "try_save_diagram_to_library", new=AsyncMock(return_value=None)),
        patch.object(
            mod,
            "store_generation_preview_outcome",
            new=AsyncMock(return_value=True),
        ),
        patch.object(mod, "build_public_temp_image_url", return_value="https://x/t.png"),
        patch.object(mod, "generate_signed_url", return_value="/temp_images/x.png?sig=1"),
        patch.object(mod.aiofiles, "open") as aio_open,
        patch.object(mod, "schedule_module_activity"),
        patch.object(mod, "schedule_user_usage_activity"),
        patch.object(mod, "TEMP_IMAGES_DIR") as temp_dir,
    ):
        temp_dir.mkdir = MagicMock()
        temp_dir.__truediv__ = MagicMock(return_value=MagicMock())
        file_cm = MagicMock()
        file_cm.__aenter__ = AsyncMock(return_value=AsyncMock(write=AsyncMock()))
        file_cm.__aexit__ = AsyncMock(return_value=False)
        aio_open.return_value = file_cm

        response = await mod.generate_dingtalk_png(req, _request(), None, _user())

    assert response is not None
    assert getattr(response, "status_code", None) == 200
    assert llm_saw_closed == [True]
    assert shot_saw_closed == [True]
    assert session_open["value"] is False
