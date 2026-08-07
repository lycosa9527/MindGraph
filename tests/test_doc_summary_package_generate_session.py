"""Doc Summary package → mindmap: RLS session exits before COS/LLM."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import OperationalError

from models.requests.requests_diagram import GenerateMindmapFromPackageRequest
from routers.api import web_content_generation as mod
from services.infrastructure.http.error_handler import LLMAccessDeniedError


def _user() -> MagicMock:
    user = MagicMock()
    user.id = 7
    user.organization_id = 1
    return user


def _request() -> MagicMock:
    request = MagicMock()
    request.headers = {}
    request.state = MagicMock()
    request.state.request_id = "req-test"
    return request


@pytest.mark.asyncio
async def test_package_generate_exits_rls_before_cos_and_llm() -> None:
    """Lite path must not keep actor_rls_session open across COS + generation."""
    package = MagicMock()
    package.id = 11
    package.source = "doc_summary"
    candidates = [MagicMock()]
    session_open = {"value": False}
    generate_saw_closed: list[bool] = []

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

    async def _generate(**_kwargs: object) -> dict:
        generate_saw_closed.append(not session_open["value"])
        return {"diagram_type": "mind_map", "spec": {"topic": "T", "children": []}}

    req = GenerateMindmapFromPackageRequest(package_id=11, language="zh")

    with (
        patch.object(mod, "actor_rls_session", return_value=fake_cm),
        patch.object(mod, "KnowledgePackageService") as pkg_cls,
        patch.object(mod, "DocSummaryIngestService") as ingest_cls,
        patch.object(
            mod,
            "_generate_mindmap_from_resolved_content",
            new=AsyncMock(side_effect=_generate),
        ),
    ):
        pkg_cls.return_value.resolve_package_for_mindmap_generate = AsyncMock(return_value=package)
        ingest_cls.return_value.list_completed_extract_candidates = AsyncMock(return_value=candidates)
        ingest_cls.read_candidates_markdown = AsyncMock(return_value="# hello")

        result = await mod.canvas_generate_mindmap_from_package(req, _request(), _user())

    assert result["diagram_type"] == "mind_map"
    assert generate_saw_closed == [True]
    assert session_open["value"] is False
    ingest_cls.read_candidates_markdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_package_generate_db_error_on_resolve_is_503() -> None:
    """SQLAlchemy failures during resolve map to 503, not package-context 500."""
    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(side_effect=OperationalError("stmt", {}, Exception("idle")))
    fake_cm.__aexit__ = AsyncMock(return_value=False)
    req = GenerateMindmapFromPackageRequest(package_id=11, language="zh")

    with patch.object(mod, "actor_rls_session", return_value=fake_cm):
        with pytest.raises(HTTPException) as exc_info:
            await mod.canvas_generate_mindmap_from_package(req, _request(), _user())

    assert exc_info.value.status_code == 503
    assert "package context" not in str(exc_info.value.detail).lower()
    assert "Database temporarily unavailable" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_package_generate_domain_miss_is_404() -> None:
    """Domain ValueError from package resolve maps to 404."""
    fake_db = MagicMock()
    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_db)
    fake_cm.__aexit__ = AsyncMock(return_value=False)
    req = GenerateMindmapFromPackageRequest(package_id=99, language="zh")

    with (
        patch.object(mod, "actor_rls_session", return_value=fake_cm),
        patch.object(mod, "KnowledgePackageService") as pkg_cls,
    ):
        pkg_cls.return_value.resolve_package_for_mindmap_generate = AsyncMock(
            side_effect=ValueError("Package not found")
        )
        with pytest.raises(HTTPException) as exc_info:
            await mod.canvas_generate_mindmap_from_package(req, _request(), _user())

    assert exc_info.value.status_code == 404
    assert "Package not found" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_package_generate_llm_access_denied_maps_to_502() -> None:
    """Typed LLM failures after session exit use the shared HTTP mapper (not opaque 500)."""
    package = MagicMock()
    package.id = 11
    package.source = "doc_summary"
    fake_db = MagicMock()
    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_db)
    fake_cm.__aexit__ = AsyncMock(return_value=False)
    req = GenerateMindmapFromPackageRequest(package_id=11, language="zh")

    with (
        patch.object(mod, "actor_rls_session", return_value=fake_cm),
        patch.object(mod, "KnowledgePackageService") as pkg_cls,
        patch.object(mod, "DocSummaryIngestService") as ingest_cls,
        patch.object(mod, "check_endpoint_rate_limit", new=AsyncMock()),
        patch.object(mod, "get_rate_limit_identifier", return_value="u7"),
        patch.object(mod, "WebContentMindMapAgent") as agent_cls,
    ):
        pkg_cls.return_value.resolve_package_for_mindmap_generate = AsyncMock(return_value=package)
        ingest_cls.return_value.list_completed_extract_candidates = AsyncMock(return_value=[MagicMock()])
        ingest_cls.read_candidates_markdown = AsyncMock(return_value="# hello")
        agent_cls.return_value.generate_from_page_content = AsyncMock(
            side_effect=LLMAccessDeniedError("Invalid API-key provided.")
        )
        with pytest.raises(HTTPException) as exc_info:
            await mod.canvas_generate_mindmap_from_package(req, _request(), _user())

    assert exc_info.value.status_code == 502
    assert "Invalid API-key" in str(exc_info.value.detail)
