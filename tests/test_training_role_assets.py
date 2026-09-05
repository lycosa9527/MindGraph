"""Packed role catalog stays in git; live GET 302s to COS."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from models.domain.auth import User
from routers.api.training_asset_routes import (
    can_read_packed_role,
    download_training_asset,
)
from services.features.training.roles.catalog import (
    TRAINING_ROLE_IDS,
    is_packed_role_key,
    packed_role_file,
    packed_role_key,
    packed_role_public_url,
    parse_packed_role_key,
)
from services.features.training.roles.publish import _HOLDER, publish_packed_roles_sync


def _user(role: str, *, org_id: int | None = 10) -> User:
    return cast(User, SimpleNamespace(id=2, role=role, organization_id=org_id, name=role))


def test_packed_role_keys_match_shipped_webps() -> None:
    """Repo public folder has every catalog anim and thumb."""
    assert len(TRAINING_ROLE_IDS) == 20
    assert packed_role_key("11-clap") == "roles/11-clap.webp"
    assert packed_role_public_url("11-clap") == "/api/training/assets/roles/11-clap.webp"
    assert parse_packed_role_key("roles/11-clap-thumb.webp") == ("11-clap", True)
    assert is_packed_role_key("roles/11-clap.webp")
    assert not is_packed_role_key("courses/x/slides/a.webp")
    assert not is_packed_role_key("roles/../secret.webp")
    for role_id in TRAINING_ROLE_IDS:
        assert packed_role_file(role_id, thumb=False) is not None
        assert packed_role_file(role_id, thumb=True) is not None


@pytest.mark.asyncio
async def test_teacher_needs_a_live_session_for_packed_roles() -> None:
    """Teachers cannot pull role clips unless a session is live or paused."""
    with patch(
        "routers.api.training_asset_routes.get_session",
        new=AsyncMock(return_value=None),
    ):
        assert await can_read_packed_role(_user("teacher")) is False
    with patch(
        "routers.api.training_asset_routes.get_session",
        new=AsyncMock(return_value={"state": "live", "course_id": "abc"}),
    ):
        assert await can_read_packed_role(_user("teacher")) is True
    assert await can_read_packed_role(_user("superadmin")) is True


@pytest.mark.asyncio
async def test_packed_role_download_uses_repo_file_when_cos_off() -> None:
    """COS off serves the git-packed WebP from disk."""
    with (
        patch("routers.api.training_asset_routes.can_read_packed_role", new=AsyncMock(return_value=True)),
        patch("routers.api.training_asset_routes.cos_training_enabled", return_value=False),
        patch("routers.api.training_asset_routes.ensure_packed_roles_on_cos", new=AsyncMock()),
    ):
        response = await download_training_asset(
            "roles/11-clap.webp",
            proxy=False,
            current_user=_user("superadmin"),
        )
    assert isinstance(response, FileResponse)
    assert str(response.path).endswith("11-clap.webp")


@pytest.mark.asyncio
async def test_packed_role_download_redirects_to_cos() -> None:
    """COS on returns a short-lived redirect, not app-server bytes."""
    with (
        patch("routers.api.training_asset_routes.can_read_packed_role", new=AsyncMock(return_value=True)),
        patch("routers.api.training_asset_routes.cos_training_enabled", return_value=True),
        patch("routers.api.training_asset_routes.ensure_packed_roles_on_cos", new=AsyncMock()),
        patch(
            "routers.api.training_asset_routes.create_presigned_get",
            return_value="https://cos.example/roles/11-clap.webp",
        ),
    ):
        response = await download_training_asset(
            "roles/11-clap.webp",
            proxy=False,
            current_user=_user("teacher"),
        )
    assert isinstance(response, RedirectResponse)
    assert response.status_code == 302
    assert response.headers["location"] == "https://cos.example/roles/11-clap.webp"


@pytest.mark.asyncio
async def test_unknown_packed_role_is_not_found() -> None:
    """Unknown filenames stay 404."""
    with patch(
        "routers.api.training_asset_routes.can_read_packed_role",
        new=AsyncMock(return_value=True),
    ):
        with pytest.raises(HTTPException) as exc:
            await download_training_asset(
                "roles/ghost.webp",
                proxy=False,
                current_user=_user("superadmin"),
            )
    assert exc.value.status_code == 404


def test_publish_skips_when_cos_off() -> None:
    """Local/CI does not attempt a COS catalog upload."""
    _HOLDER.done = False
    with patch(
        "services.features.training.roles.publish.cos_training_enabled",
        return_value=False,
    ):
        assert publish_packed_roles_sync() is True
