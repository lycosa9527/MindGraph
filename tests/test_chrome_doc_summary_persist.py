"""Chrome / web PNG path binds extract to Document Summary COS session."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routers.api import web_content_generation as mod
from tests.typing_helpers import mock_await_kwargs


@pytest.mark.asyncio
async def test_persist_doc_summary_web_extract_binds_session_and_ingests() -> None:
    """Saved diagram gets a doc_summary package + web ingest (COS path)."""
    package = MagicMock()
    package.id = 42
    ensure = AsyncMock(return_value=package)
    ingest_text = AsyncMock()

    fake_db = MagicMock()
    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_db)
    fake_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(mod, "user_rls_session", return_value=fake_cm),
        patch.object(mod, "KnowledgePackageService") as pkg_cls,
        patch.object(mod, "DocSummaryIngestService") as ingest_cls,
    ):
        pkg_cls.return_value.ensure_doc_summary_session = ensure
        ingest_cls.return_value.ingest_text = ingest_text

        await mod.persist_doc_summary_web_extract_for_diagram(
            user_id=7,
            diagram_id="diag-1",
            page_content="# Hello web",
            page_title="Example Page",
            page_url="https://example.com/a",
            language="en",
            http_request_id="req-1",
        )

    ensure.assert_awaited_once_with(
        diagram_id="diag-1",
        diagram_title="Example Page",
        create_if_missing=True,
    )
    ingest_text.assert_awaited_once()
    kwargs = mock_await_kwargs(ingest_text)
    assert kwargs["package_id"] == 42
    assert kwargs["content"] == "# Hello web"
    assert kwargs["source_kind"] == "web"
    assert kwargs["page_url"] == "https://example.com/a"


@pytest.mark.asyncio
async def test_persist_doc_summary_web_extract_skips_empty() -> None:
    """Empty capture does not create a Document Summary session."""
    with (
        patch.object(mod, "user_rls_session") as session_cls,
        patch.object(mod, "KnowledgePackageService") as pkg_cls,
    ):
        await mod.persist_doc_summary_web_extract_for_diagram(
            user_id=7,
            diagram_id="diag-1",
            page_content="   ",
            page_title="Empty",
            page_url=None,
            language=None,
            http_request_id=None,
        )

    session_cls.assert_not_called()
    pkg_cls.assert_not_called()


@pytest.mark.asyncio
async def test_persist_doc_summary_web_extract_swallows_failures() -> None:
    """Extract persistence must not raise into the PNG response path."""
    fake_db = MagicMock()
    fake_cm = MagicMock()
    fake_cm.__aenter__ = AsyncMock(return_value=fake_db)
    fake_cm.__aexit__ = AsyncMock(return_value=False)

    with (
        patch.object(mod, "user_rls_session", return_value=fake_cm),
        patch.object(mod, "KnowledgePackageService") as pkg_cls,
    ):
        pkg_cls.return_value.ensure_doc_summary_session = AsyncMock(side_effect=ValueError("busy"))
        await mod.persist_doc_summary_web_extract_for_diagram(
            user_id=7,
            diagram_id="diag-1",
            page_content="body",
            page_title="T",
            page_url=None,
            language=None,
            http_request_id="r",
        )
