"""HTTP tests for teaching-design Word export."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.api.teaching_design_docx_export import router
from services.mindmate.teaching_design_models import TeachingDesignSpec
from utils.auth import get_current_user

app = FastAPI()
app.include_router(router, prefix="/api")

_MARKED = "课例正文\n<!-- mg-reply-kind:teaching_instruction -->"


def _make_user() -> SimpleNamespace:
    user = SimpleNamespace()
    user.id = 42
    user.name = "王老师"
    user.organization_id = 1
    user.role = "teacher"
    return user


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """Return a TestClient bound to the teaching-design export router."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Reset FastAPI dependency overrides before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_export_requires_auth(client: TestClient) -> None:
    """Unauthenticated callers cannot mint the official form."""
    response = client.post(
        "/api/export_teaching_design_docx",
        json={"assistant_markdown": _MARKED},
    )
    assert response.status_code in {401, 403}


def test_export_rejects_unmarked_markdown(client: TestClient) -> None:
    """Plain chat replies cannot use the BNU template."""
    app.dependency_overrides[get_current_user] = _make_user
    response = client.post(
        "/api/export_teaching_design_docx",
        json={"assistant_markdown": "普通问答，没有标记"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "teaching_design_not_flagged"


def test_export_rejects_oversized_markdown(client: TestClient) -> None:
    """Huge bodies are rejected before parse or LLM work."""
    app.dependency_overrides[get_current_user] = _make_user
    response = client.post(
        "/api/export_teaching_design_docx",
        json={
            "assistant_markdown": "x" * 200_001 + "\n<!-- mg-reply-kind:teaching_instruction -->",
            "reply_kind": "teaching_instruction",
        },
    )
    assert response.status_code == 413
    assert response.json()["detail"] == "teaching_design_too_large"


def test_export_accepts_flagged_markdown(client: TestClient) -> None:
    """Marked replies return a DOCX attachment."""
    app.dependency_overrides[get_current_user] = _make_user
    with patch(
        "routers.api.teaching_design_docx_export.complete_teaching_design_spec",
        new_callable=AsyncMock,
    ) as complete_mock:
        complete_mock.return_value = TeachingDesignSpec(
            title="《呼吸作用》教学设计",
            summary="摘要正文",
        )
        response = client.post(
            "/api/export_teaching_design_docx",
            json={"assistant_markdown": _MARKED, "reply_kind": "teaching_instruction"},
        )
    assert response.status_code == 200
    assert "wordprocessingml" in response.headers.get("content-type", "")
    assert response.content[:2] == b"PK"
