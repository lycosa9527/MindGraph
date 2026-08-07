"""Tests for POST /api/generate-text-to-image (ZhiHui / MindT2I merge)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from pydantic import ValidationError

from models.requests.requests_t2i import GenerateTextToImageRequest
from routers.api import image_generation
from services.diagram.dify_user_resolve import DiagramSaveIdentity
from services.infrastructure.http.error_handler import LLMContentFilterError
from services.t2i.image_client import normalize_size
from services.t2i.image_service import T2IGenerationResult
from utils.auth import get_current_user_or_api_key


def _fake_rls_session_cm(db: MagicMock | None = None) -> MagicMock:
    """Async context manager stub for actor/system RLS sessions."""
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=db if db is not None else MagicMock())
    session_cm.__aexit__ = AsyncMock(return_value=None)
    return session_cm


def _build_client() -> TestClient:
    """Minimal FastAPI app with auth override (no request-scoped DB)."""
    app = FastAPI()
    app.include_router(image_generation.router, prefix="/api")

    async def _fake_user():
        return None

    app.dependency_overrides[get_current_user_or_api_key] = _fake_user
    return TestClient(app)


def test_generate_text_to_image_request_accepts_dify_fields() -> None:
    """Dify body fields validate like generate_dingtalk."""
    req = GenerateTextToImageRequest.model_validate(
        {
            "prompt": "一只猫",
            "language": "zh",
            "conversation_id": "conv-1",
            "dify_user_id": "user-1",
        }
    )
    assert req.prompt == "一只猫"
    assert req.conversation_id == "conv-1"
    assert req.dify_user_id == "user-1"


def test_generate_text_to_image_request_defaults_to_qwen_image_3() -> None:
    """Endpoint defaults model to qwen-image-3.0 when omitted."""
    req = GenerateTextToImageRequest.model_validate({"prompt": "一只猫"})
    assert req.model == "qwen-image-3.0"


def test_generate_text_to_image_request_accepts_qwen_image_models() -> None:
    """Only Qwen Image 3.0 multimodal models are allowed."""
    req = GenerateTextToImageRequest.model_validate({"prompt": "一只猫", "model": "qwen-image-3.0-pro"})
    assert req.model == "qwen-image-3.0-pro"
    with pytest.raises(ValidationError):
        GenerateTextToImageRequest.model_validate({"prompt": "一只猫", "model": "wan2.5-t2i-preview"})


def test_generate_text_to_image_request_accepts_reference_images() -> None:
    """I2I reference images accept data URIs; reject over-limit lists."""
    data_uri = "data:image/png;base64,iVBORw0KGgo="
    req = GenerateTextToImageRequest.model_validate({"prompt": "一只猫", "reference_images": [data_uri]})
    assert req.reference_images == [data_uri]
    with pytest.raises(ValidationError):
        GenerateTextToImageRequest.model_validate(
            {
                "prompt": "一只猫",
                "reference_images": [data_uri, data_uri, data_uri, data_uri],
            }
        )


def test_generate_text_to_image_requires_auth() -> None:
    """Missing JWT/API key returns 401."""
    app = FastAPI()
    app.include_router(image_generation.router, prefix="/api")
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/generate-text-to-image", json={"prompt": "test prompt here"})
    assert response.status_code == 401


def test_generate_text_to_image_jwt_without_zhihui_cap_forbidden() -> None:
    """Browser JWT without feature.zhihui (e.g. teacher) cannot use ZhiHui T2I."""
    app = FastAPI()
    app.include_router(image_generation.router, prefix="/api")

    teacher = MagicMock()
    teacher.id = 9
    teacher.role = "teacher"
    teacher.name = "Teacher"

    async def _teacher_user():
        return teacher

    app.dependency_overrides[get_current_user_or_api_key] = _teacher_user
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post("/api/generate-text-to-image", json={"prompt": "一只猫在草地上"})

    assert response.status_code == 403
    assert "ZhiHui" in response.json()["detail"]


def test_generate_text_to_image_success_markdown() -> None:
    """Happy path returns plain-text markdown with signed ZhiHui asset URL."""
    client = _build_client()
    result = T2IGenerationResult(
        generation_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        logical_key="zhihui/generations/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jpg",
        content_type="image/jpeg",
        original_prompt="一只猫",
        enhanced_prompt=None,
        size="1280*960",
        usage_data=None,
        image_bytes_len=12,
    )
    identity = DiagramSaveIdentity(user_id=7, organization_id=1, dify_user_key="mg_user_7")

    with (
        patch.object(
            image_generation,
            "resolve_diagram_save_identity",
            new=AsyncMock(return_value=identity),
        ),
        patch.object(
            image_generation,
            "generate_and_store_image",
            new=AsyncMock(return_value=result),
        ),
        patch.object(image_generation, "schedule_module_activity"),
        patch.object(image_generation, "schedule_user_usage_activity"),
        patch.object(
            image_generation,
            "get_token_tracker",
            return_value=MagicMock(track_usage=AsyncMock()),
        ),
        patch.object(
            image_generation,
            "get_activity_stream_service",
            return_value=MagicMock(broadcast_activity=AsyncMock()),
        ),
        patch.object(
            image_generation,
            "system_rls_session",
            return_value=_fake_rls_session_cm(),
        ),
        patch.object(
            image_generation,
            "actor_rls_session",
            return_value=_fake_rls_session_cm(),
        ),
        patch.object(image_generation, "ZhihuiConversationRepository") as mock_conv_cls,
        patch.object(image_generation, "ZhihuiGenerationRepository") as mock_repo_cls,
        patch.object(
            image_generation,
            "generate_signed_url",
            return_value="zhihui/generations/x.jpg?sig=abc&exp=1",
        ),
        patch.object(
            image_generation,
            "build_public_zhihui_asset_url",
            return_value="https://mg.example/api/zhihui/assets/zhihui/generations/x.jpg?sig=abc&exp=1",
        ),
    ):
        mock_conv = MagicMock()
        mock_conv.create_conversation = AsyncMock(
            return_value=MagicMock(id="conv-aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        )
        mock_conv_cls.return_value = mock_conv
        mock_repo = MagicMock()
        mock_repo.create_generation = AsyncMock()
        mock_repo_cls.return_value = mock_repo

        response = client.post(
            "/api/generate-text-to-image",
            json={
                "prompt": "一只猫",
                "language": "zh",
                "conversation_id": "c1",
                "dify_user_id": "mg_user_7",
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.startswith("![](https://mg.example/api/zhihui/assets/")
    mock_conv.create_conversation.assert_awaited()
    mock_repo.create_generation.assert_awaited()


def test_generate_text_to_image_validation_error() -> None:
    """Service ValueError becomes 400 plain text."""
    client = _build_client()
    with (
        patch.object(
            image_generation,
            "system_rls_session",
            return_value=_fake_rls_session_cm(),
        ),
        patch.object(
            image_generation,
            "resolve_diagram_save_identity",
            new=AsyncMock(return_value=DiagramSaveIdentity(None, None, "")),
        ),
        patch.object(
            image_generation,
            "generate_and_store_image",
            new=AsyncMock(side_effect=ValueError("Prompt is required")),
        ),
    ):
        response = client.post("/api/generate-text-to-image", json={"prompt": "ok prompt"})
    assert response.status_code == 400
    assert "Error:" in response.text


def test_generate_text_to_image_content_filter_maps_to_400() -> None:
    """DashScope DataInspectionFailed surfaces as 400 with user message."""
    client = _build_client()
    filtered = LLMContentFilterError("Content filter: blocked")
    setattr(filtered, "user_message", "内容可能包含不当信息，请修改输入内容")
    with (
        patch.object(
            image_generation,
            "system_rls_session",
            return_value=_fake_rls_session_cm(),
        ),
        patch.object(
            image_generation,
            "resolve_diagram_save_identity",
            new=AsyncMock(return_value=DiagramSaveIdentity(None, None, "")),
        ),
        patch.object(
            image_generation,
            "generate_and_store_image",
            new=AsyncMock(side_effect=filtered),
        ),
    ):
        response = client.post("/api/generate-text-to-image", json={"prompt": "ok prompt"})
    assert response.status_code == 400
    assert "不当" in response.text or "Error:" in response.text


@pytest.mark.asyncio
async def test_generate_text_to_image_closes_rls_before_generation() -> None:
    """Identity short session must exit before DashScope/COS generation."""
    session_open = {"value": False}
    generate_saw_closed: list[bool] = []

    fake_cm = MagicMock()

    async def _enter(_self: object) -> MagicMock:
        session_open["value"] = True
        return MagicMock()

    async def _exit(_self: object, *_args: object) -> bool:
        session_open["value"] = False
        return False

    fake_cm.__aenter__ = _enter
    fake_cm.__aexit__ = _exit

    async def _generate(*_args: object, **_kwargs: object) -> T2IGenerationResult:
        generate_saw_closed.append(not session_open["value"])
        return T2IGenerationResult(
            generation_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            logical_key="zhihui/generations/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jpg",
            content_type="image/jpeg",
            original_prompt="一只猫",
            enhanced_prompt=None,
            size="1280*960",
            usage_data=None,
            image_bytes_len=12,
        )

    request = MagicMock(spec=Request)
    request.state = MagicMock()
    request.state.api_key_id = None
    request.headers = {}
    req = GenerateTextToImageRequest.model_validate({"prompt": "一只猫"})

    with (
        patch.object(image_generation, "system_rls_session", return_value=fake_cm),
        patch.object(image_generation, "actor_rls_session", return_value=fake_cm),
        patch.object(
            image_generation,
            "resolve_diagram_save_identity",
            new=AsyncMock(return_value=DiagramSaveIdentity(None, None, "")),
        ),
        patch.object(
            image_generation,
            "generate_and_store_image",
            new=AsyncMock(side_effect=_generate),
        ),
        patch.object(
            image_generation,
            "get_token_tracker",
            return_value=MagicMock(track_usage=AsyncMock()),
        ),
        patch.object(
            image_generation,
            "ZhihuiConversationRepository",
            return_value=MagicMock(create_conversation=AsyncMock(return_value=MagicMock(id="c1"))),
        ),
        patch.object(
            image_generation,
            "ZhihuiGenerationRepository",
            return_value=MagicMock(create_generation=AsyncMock()),
        ),
        patch.object(image_generation, "generate_signed_url", return_value="x?sig=1"),
        patch.object(
            image_generation,
            "build_public_zhihui_asset_url",
            return_value="https://x/img",
        ),
    ):
        response = await image_generation.generate_text_to_image(req, request, None)

    assert response.status_code == 200
    assert generate_saw_closed == [True]
    assert session_open["value"] is False


def test_normalize_size_rejects_out_of_range() -> None:
    """Qwen Image 3.0 size limits are enforced before the API call."""
    assert normalize_size(None) is None
    assert normalize_size("1024*1024") == "1024*1024"
    with pytest.raises(ValueError):
        normalize_size("64*64")
    with pytest.raises(ValueError):
        normalize_size("not-a-size")
