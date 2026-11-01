"""HTTP checks for the seminar minutes route that do not call a model."""

from __future__ import annotations

from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.api.mindmate_seminar_minutes import router as minutes_router
from utils.auth import get_current_user

app = FastAPI()
app.include_router(minutes_router, prefix="/api/mindmate/seminar")


def _user() -> SimpleNamespace:
    user = SimpleNamespace()
    user.id = 7
    user.organization_id = None
    return user


@pytest.fixture(name="client")
def fixture_client() -> Iterator[TestClient]:
    """Authenticated client. Body validation runs before the model call."""
    app.dependency_overrides[get_current_user] = _user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_minutes_rejects_a_blank_transcript(client: TestClient) -> None:
    """Whitespace is not a seminar slice."""
    response = client.post(
        "/api/mindmate/seminar/room-1/minutes",
        json={"transcript": "   ", "zh": True},
    )
    assert response.status_code == 422


def test_minutes_rejects_an_empty_body(client: TestClient) -> None:
    """The route requires a transcript."""
    response = client.post("/api/mindmate/seminar/room-1/minutes", json={})
    assert response.status_code == 422


def test_minutes_rejects_too_many_quotes(client: TestClient) -> None:
    """Highlights stay at the card limit of three lines."""
    response = client.post(
        "/api/mindmate/seminar/room-1/minutes",
        json={
            "transcript": "王雅萱：一句。",
            "quotes": ["一", "二", "三", "四"],
        },
    )
    assert response.status_code == 422
