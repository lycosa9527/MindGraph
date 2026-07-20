"""Document Summary session must stay synced to the active diagram's COS package."""

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


def _pkg(
    package_id: int,
    *,
    diagram_id: str | None,
    source: str = "doc_summary",
) -> SimpleNamespace:
    return SimpleNamespace(id=package_id, diagram_id=diagram_id, source=source)


@pytest.mark.asyncio
async def test_ensure_ignores_stale_package_id_for_other_diagram() -> None:
    """Stale package_id from diagram A must not bind session for diagram B."""
    service_cls = _package_service_cls()
    db = MagicMock()
    service = service_cls(db, user_id=7)
    stale = _pkg(11, diagram_id="diag-a")
    fresh = _pkg(22, diagram_id="diag-b")
    service.get_package = AsyncMock(return_value=stale)
    service.find_doc_summary_package_for_diagram = AsyncMock(return_value=fresh)
    service.update_package = AsyncMock()
    service.create_package = AsyncMock()

    result = await service.ensure_doc_summary_session(
        diagram_id="diag-b",
        package_id=11,
        create_if_missing=False,
    )

    assert result.id == 22
    service.find_doc_summary_package_for_diagram.assert_awaited_once_with("diag-b")
    service.update_package.assert_not_awaited()
    service.create_package.assert_not_awaited()


@pytest.mark.asyncio
async def test_ensure_links_unbound_package_to_diagram() -> None:
    """Pending package without diagram_id can be attached to the active diagram."""
    service_cls = _package_service_cls()
    db = MagicMock()
    service = service_cls(db, user_id=7)
    pending = _pkg(11, diagram_id=None)
    linked = _pkg(11, diagram_id="diag-b")
    service.get_package = AsyncMock(return_value=pending)
    service.update_package = AsyncMock(return_value=linked)

    result = await service.ensure_doc_summary_session(
        diagram_id="diag-b",
        package_id=11,
        create_if_missing=False,
    )

    assert result.diagram_id == "diag-b"
    service.update_package.assert_awaited_once_with(11, diagram_id="diag-b")


@pytest.mark.asyncio
async def test_clear_ignores_stale_package_id_and_uses_diagram() -> None:
    """Clear must delete the active diagram's package, not a mismatched package_id."""
    service_cls = _package_service_cls()
    db = MagicMock()
    service = service_cls(db, user_id=7)
    stale = _pkg(11, diagram_id="diag-a")
    target = _pkg(22, diagram_id="diag-b")
    service.get_package = AsyncMock(return_value=stale)
    service.find_doc_summary_package_for_diagram = AsyncMock(return_value=target)
    service.delete_package = AsyncMock()

    deleted = await service.clear_doc_summary_session(
        package_id=11,
        diagram_id="diag-b",
    )

    assert deleted is True
    service.delete_package.assert_awaited_once_with(22)


@pytest.mark.asyncio
async def test_resolve_generate_prefers_doc_summary_over_ks() -> None:
    """Generate-by-diagram resolves Document Summary before Knowledge Space."""
    service_cls = _package_service_cls()
    db = MagicMock()
    service = service_cls(db, user_id=7)
    doc_summary = _pkg(22, diagram_id="diag-1")
    service.get_package = AsyncMock(return_value=None)
    service.find_doc_summary_package_for_diagram = AsyncMock(return_value=doc_summary)
    service.find_package_for_diagram = AsyncMock(return_value=_pkg(99, diagram_id="diag-1", source="knowledge_space"))

    package = await service.resolve_package_for_mindmap_generate(diagram_id="diag-1")

    assert package is not None
    assert package.id == 22
    service.find_package_for_diagram.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_generate_ignores_stale_package_id() -> None:
    """Generate with stale package_id + diagram_id uses the diagram's COS package."""
    service_cls = _package_service_cls()
    db = MagicMock()
    service = service_cls(db, user_id=7)
    stale = _pkg(11, diagram_id="diag-a")
    fresh = _pkg(22, diagram_id="diag-b")
    service.get_package = AsyncMock(return_value=stale)
    service.find_doc_summary_package_for_diagram = AsyncMock(return_value=fresh)

    package = await service.resolve_package_for_mindmap_generate(
        package_id=11,
        diagram_id="diag-b",
    )

    assert package is not None
    assert package.id == 22


@pytest.mark.asyncio
async def test_ensure_create_double_checks_before_insert() -> None:
    """Create path re-checks for an existing diagram package before insert."""
    service_cls = _package_service_cls()
    db = MagicMock()
    service = service_cls(db, user_id=7)
    existing = _pkg(33, diagram_id="diag-1")
    service.find_doc_summary_package_for_diagram = AsyncMock(side_effect=[None, existing])
    service.create_package = AsyncMock()

    result = await service.ensure_doc_summary_session(
        diagram_id="diag-1",
        diagram_title="Title",
        create_if_missing=True,
    )

    assert result.id == 33
    service.create_package.assert_not_awaited()
    assert service.find_doc_summary_package_for_diagram.await_count == 2
