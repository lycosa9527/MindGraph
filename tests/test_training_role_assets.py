"""Packed role catalog stays in git; live GET 302s to COS."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from config.settings import config
from models.domain.auth import User
from routers.api.training_asset_routes import (
    can_read_packed_role,
    download_training_asset,
)
from services.features.training.courses.constants import DOUBLE_BUBBLE_COURSE_ID
from services.features.training.roles.catalog import (
    TRAINING_ROLE_IDS,
    is_packed_role_key,
    packed_role_file,
    packed_role_key,
    packed_role_public_url,
    parse_packed_role_key,
)
from services.features.training.roles.publish import (
    _HOLDER,
    packed_role_cos_prefixes,
    publish_packed_roles_sync,
)

_COVER_KEY = f"courses/{DOUBLE_BUBBLE_COURSE_ID}/cover.png"


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
async def test_signed_in_users_can_read_packed_roles() -> None:
    """Packed mascots are brand assets for Course Builder and 研习社."""
    assert await can_read_packed_role(_user("teacher")) is True
    assert await can_read_packed_role(_user("student")) is True
    assert await can_read_packed_role(_user("superadmin")) is True


@pytest.mark.asyncio
async def test_packed_role_download_uses_repo_file_when_cos_off() -> None:
    """COS off serves the git-packed WebP from disk."""
    with (
        patch("routers.api.training_asset_routes.can_read_packed_role", new=AsyncMock(return_value=True)),
        patch("routers.api.training_asset_routes.cos_training_enabled", return_value=False),
        patch("routers.api.training_asset_routes.config") as mock_config,
        patch("routers.api.training_asset_routes.ensure_packed_roles_on_cos", new=AsyncMock()),
    ):
        mock_config.COURSE_BUILDER_LOAD_FROM_COS = True
        response = await download_training_asset(
            "roles/11-clap.webp",
            proxy=False,
            current_user=_user("superadmin"),
        )
    assert isinstance(response, FileResponse)
    assert str(response.path).endswith("11-clap.webp")


@pytest.mark.asyncio
async def test_packed_role_falls_back_to_repo_when_presign_fails() -> None:
    """COS on but no presign still serves the git-packed WebP."""
    with (
        patch("routers.api.training_asset_routes.can_read_packed_role", new=AsyncMock(return_value=True)),
        patch("routers.api.training_asset_routes.cos_training_enabled", return_value=True),
        patch("routers.api.training_asset_routes.config") as mock_config,
        patch("routers.api.training_asset_routes.ensure_packed_roles_on_cos", new=AsyncMock()),
        patch("routers.api.training_asset_routes.create_presigned_get", return_value=None),
    ):
        mock_config.COURSE_BUILDER_LOAD_FROM_COS = True
        response = await download_training_asset(
            "roles/11-clap.webp",
            proxy=False,
            current_user=_user("superadmin"),
        )
    assert isinstance(response, FileResponse)
    assert str(response.path).endswith("11-clap.webp")


@pytest.mark.asyncio
async def test_packed_role_uses_repo_when_builder_cos_gate_off() -> None:
    """COURSE_BUILDER_LOAD_FROM_COS=false serves git WebPs and does not 302."""
    with (
        patch("routers.api.training_asset_routes.can_read_packed_role", new=AsyncMock(return_value=True)),
        patch("routers.api.training_asset_routes.cos_training_enabled", return_value=True),
        patch("routers.api.training_asset_routes.config") as mock_config,
        patch("routers.api.training_asset_routes.ensure_packed_roles_on_cos", new=AsyncMock()),
        patch(
            "routers.api.training_asset_routes.create_presigned_get",
            return_value="https://cos.example/roles/11-clap.webp",
        ) as presign,
    ):
        mock_config.COURSE_BUILDER_LOAD_FROM_COS = False
        response = await download_training_asset(
            "roles/11-clap.webp",
            proxy=False,
            current_user=_user("superadmin"),
        )
    assert isinstance(response, FileResponse)
    presign.assert_not_called()


@pytest.mark.asyncio
async def test_packed_role_download_redirects_to_cos() -> None:
    """COS on returns a short-lived redirect, not app-server bytes."""
    with (
        patch("routers.api.training_asset_routes.can_read_packed_role", new=AsyncMock(return_value=True)),
        patch("routers.api.training_asset_routes.cos_training_enabled", return_value=True),
        patch("routers.api.training_asset_routes.config") as mock_config,
        patch("routers.api.training_asset_routes.ensure_packed_roles_on_cos", new=AsyncMock()),
        patch(
            "routers.api.training_asset_routes.create_presigned_get",
            return_value="https://cos.example/roles/11-clap.webp",
        ),
    ):
        mock_config.COURSE_BUILDER_LOAD_FROM_COS = True
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


def test_packed_role_prefixes_cover_dev_and_test(monkeypatch: pytest.MonkeyPatch) -> None:
    """Mascot clips are mirrored to both non-prod training prefixes."""
    monkeypatch.delenv("COS_ENV_PREFIX", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    config.refresh_env_cache()
    try:
        prefixes = packed_role_cos_prefixes()
        assert "dev/training" in prefixes
        assert "test/training" in prefixes
        assert not any(item.startswith("production/") for item in prefixes)
    finally:
        config.refresh_env_cache()


def test_packed_role_prefixes_empty_on_production(monkeypatch: pytest.MonkeyPatch) -> None:
    """Production must not publish roles to dev, test, or production/."""
    monkeypatch.delenv("COS_ENV_PREFIX", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    config.refresh_env_cache()
    try:
        assert not packed_role_cos_prefixes()
    finally:
        config.refresh_env_cache()


@pytest.mark.asyncio
async def test_packed_role_serves_repo_when_production_has_no_prefix() -> None:
    """Empty publish list skips COS 302 so production does not hit missing keys."""
    with (
        patch(
            "routers.api.training_asset_routes.can_read_packed_role",
            new=AsyncMock(return_value=True),
        ),
        patch("routers.api.training_asset_routes.cos_training_enabled", return_value=True),
        patch("routers.api.training_asset_routes.config") as mock_config,
        patch(
            "routers.api.training_asset_routes.packed_role_cos_prefixes",
            return_value=(),
        ),
        patch("routers.api.training_asset_routes.ensure_packed_roles_on_cos", new=AsyncMock()),
        patch("routers.api.training_asset_routes.create_presigned_get") as presign,
    ):
        mock_config.COURSE_BUILDER_LOAD_FROM_COS = True
        response = await download_training_asset(
            "roles/11-clap.webp",
            proxy=False,
            current_user=_user("superadmin"),
        )
    assert isinstance(response, FileResponse)
    presign.assert_not_called()


@pytest.mark.asyncio
async def test_course_asset_skips_redirect_when_builder_gate_off(tmp_path: Path) -> None:
    """COURSE_BUILDER_LOAD_FROM_COS=false serves course media from the API."""
    disk = tmp_path / "cover.png"
    disk.write_bytes(b"png")
    with (
        patch(
            "routers.api.training_asset_routes.can_read_training_asset",
            new=AsyncMock(return_value=True),
        ),
        patch("routers.api.training_asset_routes.cos_training_enabled", return_value=True),
        patch("routers.api.training_asset_routes.config") as mock_config,
        patch("routers.api.training_asset_routes.create_presigned_get") as presign,
        patch("routers.api.training_asset_routes.resolve_local_safe", return_value=disk),
    ):
        mock_config.COURSE_BUILDER_LOAD_FROM_COS = False
        response = await download_training_asset(
            _COVER_KEY,
            proxy=False,
            current_user=_user("superadmin"),
        )
    assert isinstance(response, FileResponse)
    presign.assert_not_called()


@pytest.mark.asyncio
async def test_course_asset_redirects_when_builder_gate_on() -> None:
    """COURSE_BUILDER_LOAD_FROM_COS=true still 302s course media to COS."""
    location = "https://example.myqcloud.com/cover.png"
    with (
        patch(
            "routers.api.training_asset_routes.can_read_training_asset",
            new=AsyncMock(return_value=True),
        ),
        patch("routers.api.training_asset_routes.cos_training_enabled", return_value=True),
        patch("routers.api.training_asset_routes.config") as mock_config,
        patch(
            "routers.api.training_asset_routes.create_presigned_get",
            return_value=location,
        ),
    ):
        mock_config.COURSE_BUILDER_LOAD_FROM_COS = True
        response = await download_training_asset(
            _COVER_KEY,
            proxy=False,
            current_user=_user("superadmin"),
        )
    assert isinstance(response, RedirectResponse)
    assert response.headers["location"] == location


@pytest.mark.asyncio
async def test_course_asset_fetches_cos_via_server_when_gate_off() -> None:
    """Gate off with no local file still proxies COS through the API."""
    missing = Path("/nonexistent/training-cover.png")
    with (
        patch(
            "routers.api.training_asset_routes.can_read_training_asset",
            new=AsyncMock(return_value=True),
        ),
        patch("routers.api.training_asset_routes.cos_training_enabled", return_value=True),
        patch("routers.api.training_asset_routes.config") as mock_config,
        patch("routers.api.training_asset_routes.create_presigned_get") as presign,
        patch("routers.api.training_asset_routes.resolve_local_safe", return_value=missing),
        patch(
            "routers.api.training_asset_routes.get_bytes",
            new=AsyncMock(return_value=b"from-cos"),
        ),
    ):
        mock_config.COURSE_BUILDER_LOAD_FROM_COS = False
        response = await download_training_asset(
            _COVER_KEY,
            proxy=False,
            current_user=_user("superadmin"),
        )
    presign.assert_not_called()
    assert response.body == b"from-cos"
