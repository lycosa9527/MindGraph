"""Unit tests for Document Summary session clear (COS package delete)."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest


def _package_service_cls():
    """Import KnowledgePackageService without pulling KnowledgeSpaceService → LLM."""
    sys.modules.setdefault("services.knowledge.knowledge_space_service", MagicMock())
    module = importlib.import_module("services.knowledge.knowledge_package_service")
    return module.KnowledgePackageService


@pytest.mark.asyncio
async def test_clear_doc_summary_session_deletes_by_package_id() -> None:
    """clear_doc_summary_session deletes a doc_summary package by id."""
    service_cls = _package_service_cls()
    db = MagicMock()
    service = service_cls(db, user_id=7)
    package = SimpleNamespace(id=11, source="doc_summary", diagram_id=None)
    service.get_package = AsyncMock(return_value=package)
    service.delete_package = AsyncMock()

    deleted = await service.clear_doc_summary_session(package_id=11)

    assert deleted is True
    service.delete_package.assert_awaited_once_with(11)


@pytest.mark.asyncio
async def test_clear_doc_summary_session_rejects_non_doc_summary() -> None:
    """Knowledge Space packages cannot be cleared via Document Summary session."""
    service_cls = _package_service_cls()
    db = MagicMock()
    service = service_cls(db, user_id=7)
    package = SimpleNamespace(id=11, source="knowledge_space", diagram_id=None)
    service.get_package = AsyncMock(return_value=package)
    service.delete_package = AsyncMock()

    with pytest.raises(ValueError, match="not a Document Summary"):
        await service.clear_doc_summary_session(package_id=11)

    service.delete_package.assert_not_awaited()


@pytest.mark.asyncio
async def test_clear_doc_summary_session_falls_back_to_diagram() -> None:
    """When package_id misses, resolve by diagram_id then delete."""
    service_cls = _package_service_cls()
    db = MagicMock()
    service = service_cls(db, user_id=7)
    package = SimpleNamespace(id=22, source="doc_summary", diagram_id="diag-1")
    service.get_package = AsyncMock(return_value=None)
    service.find_doc_summary_package_for_diagram = AsyncMock(return_value=package)
    service.delete_package = AsyncMock()

    deleted = await service.clear_doc_summary_session(
        package_id=99,
        diagram_id="diag-1",
    )

    assert deleted is True
    service.find_doc_summary_package_for_diagram.assert_awaited_once_with("diag-1")
    service.delete_package.assert_awaited_once_with(22)


@pytest.mark.asyncio
async def test_clear_doc_summary_session_noop_when_absent() -> None:
    """Missing session is a successful no-op."""
    service_cls = _package_service_cls()
    db = MagicMock()
    service = service_cls(db, user_id=7)
    service.find_doc_summary_package_for_diagram = AsyncMock(return_value=None)
    service.delete_package = AsyncMock()

    deleted = await service.clear_doc_summary_session(diagram_id="diag-empty")

    assert deleted is False
    service.delete_package.assert_not_awaited()
