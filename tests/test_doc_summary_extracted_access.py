"""Tests for Document Summary COS ownership probe endpoints."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from routers.api.doc_summary import session as doc_summary_routes
from tests.typing_helpers import as_user


@pytest.mark.asyncio
async def test_authorize_extracted_access_allows_owner() -> None:
    """Owner of a doc_summary package with content gets allowed=true."""
    user = as_user(SimpleNamespace(id=7))
    db = AsyncMock()
    resolved = {
        "allowed": True,
        "package_id": 9,
        "object_id": "abc",
        "storage": "cos",
        "has_content": True,
    }
    with patch.object(
        doc_summary_routes,
        "resolve_owned_extracted",
        new_callable=AsyncMock,
        return_value=resolved,
    ):
        result = await doc_summary_routes.authorize_extracted_access(9, user, db)
    assert result.allowed is True
    assert result.object_id == "abc"
    assert result.has_content is True


@pytest.mark.asyncio
async def test_authorize_extracted_access_rejects_missing_package() -> None:
    """Unknown package returns 404."""
    user = as_user(SimpleNamespace(id=7))
    db = AsyncMock()
    with patch.object(
        doc_summary_routes,
        "resolve_owned_extracted",
        new_callable=AsyncMock,
        return_value={"allowed": False, "reason": "package_not_found", "package_id": 9},
    ):
        with pytest.raises(HTTPException) as exc:
            await doc_summary_routes.authorize_extracted_access(9, user, db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_resolve_owned_extracted_denies_other_users_package() -> None:
    """Package lookup is scoped to the caller user id."""
    db = AsyncMock()
    packages = MagicMock()
    packages.get_package = AsyncMock(return_value=None)
    with patch.object(doc_summary_routes, "KnowledgePackageService", return_value=packages):
        resolved = await doc_summary_routes.resolve_owned_extracted(
            db=db,
            user_id=1,
            package_id=99,
        )
    assert resolved["allowed"] is False
    assert resolved["reason"] == "package_not_found"
    packages.get_package.assert_awaited_once_with(99)
