"""HTTP tests for Knowledge Space settings endpoints."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.api.knowledge_space.settings import router
from services.knowledge.knowledge_settings import EffectiveKnowledgeSettings, SettingsUpdateResult
from utils.auth import get_current_user

app = FastAPI()
app.include_router(router, prefix="/api/knowledge-space")


def _make_user(user_id: int = 7) -> SimpleNamespace:
    user = SimpleNamespace()
    user.id = user_id
    user.role = "teacher"
    user.organization_id = 1
    return user


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """FastAPI test client for settings routes."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Reset auth overrides after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_get_settings_requires_auth(client: TestClient) -> None:
    """Unauthenticated requests are rejected."""
    response = client.get("/api/knowledge-space/settings")
    assert response.status_code in (401, 403)


def test_get_settings_returns_effective_values(client: TestClient) -> None:
    """GET returns merged effective settings for the current user."""
    app.dependency_overrides[get_current_user] = _make_user
    effective = EffectiveKnowledgeSettings(
        default_method="hybrid",
        top_k=5,
        score_threshold=0.5,
        chunk_size=500,
        chunk_overlap=50,
        vector_weight=0.5,
        keyword_weight=0.5,
        reranking_mode="reranking_model",
        wiki_compile_enabled=True,
        chunking_engine="semchunk",
        has_user_overrides=False,
    )
    with (
        patch("routers.api.knowledge_space.settings.KnowledgeSpaceService") as service_cls,
        patch("routers.api.knowledge_space.settings.get_space_settings", new=AsyncMock(return_value=effective)),
    ):
        service_cls.return_value.create_knowledge_space = AsyncMock()
        response = client.get("/api/knowledge-space/settings")
    assert response.status_code == 200
    body = response.json()
    assert body["score_threshold"] == 0.5
    assert body["chunk_size"] == 500
    assert body["wiki_compile_enabled"] is True


def test_put_settings_returns_reindex_flag(client: TestClient) -> None:
    """PUT reports when chunking changes require reindex."""
    app.dependency_overrides[get_current_user] = _make_user
    effective = EffectiveKnowledgeSettings(
        default_method="semantic",
        top_k=10,
        score_threshold=0.4,
        chunk_size=600,
        chunk_overlap=80,
        vector_weight=0.5,
        keyword_weight=0.5,
        reranking_mode="reranking_model",
        wiki_compile_enabled=True,
        chunking_engine="semchunk",
        has_user_overrides=True,
    )
    with patch(
        "routers.api.knowledge_space.settings.update_space_settings",
        new=AsyncMock(return_value=SettingsUpdateResult(settings=effective, reindex_required=True)),
    ):
        response = client.put(
            "/api/knowledge-space/settings",
            json={
                "default_method": "semantic",
                "top_k": 10,
                "score_threshold": 0.4,
                "chunk_size": 600,
                "chunk_overlap": 80,
            },
        )
    assert response.status_code == 200
    body = response.json()
    assert body["reindex_required"] is True
    assert body["settings"]["default_method"] == "semantic"
