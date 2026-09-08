"""研习社: each school sees only its own channels; 系统公告 is platform-wide."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from pydantic import ValidationError

from models.domain.workshop_chat import FileAttachment
from routers.features.workshop_chat.dependencies import (
    access_channel,
    access_channel_message,
    access_dm_partner,
    get_effective_org_id,
)
from routers.features.workshop_chat.schemas import UpdateChannelPermissionsRequest
from routers.features.workshop_chat.ws import _ws_access_error_message
from services.features.workshop_chat.channel_service import ChannelService
from services.features.workshop_chat.file_service import user_can_access_attachment
from tests.typing_helpers import as_type, as_user


def _user(*, role: str, organization_id: int | None, user_id: int = 10):
    """Typed user double for tenant checks."""
    return as_user(SimpleNamespace(id=user_id, role=role, organization_id=organization_id))


def _scalar(value: object) -> MagicMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def test_teacher_cannot_override_org_id() -> None:
    """Teachers stay in their own school even if they pass another org_id."""
    teacher = _user(role="teacher", organization_id=5)
    assert get_effective_org_id(teacher, 7) == 5


def test_school_admin_cannot_override_org_id() -> None:
    """School admins are not platform admins and cannot browse another school."""
    admin = _user(role="school_admin", organization_id=5)
    assert get_effective_org_id(admin, 7) == 5


def test_superadmin_can_override_org_id() -> None:
    """Platform superadmins may inspect another school's workshop."""
    admin = _user(role="superadmin", organization_id=None)
    assert get_effective_org_id(admin, 7) == 7


@pytest.mark.asyncio
async def test_access_channel_allows_own_school() -> None:
    """Same-org public channels are readable."""
    user = _user(role="teacher", organization_id=5)
    channel = SimpleNamespace(id=20, channel_type="public", organization_id=5)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar(channel))
    assert await access_channel(db, 20, user) is channel


@pytest.mark.asyncio
async def test_access_channel_allows_platform_announce() -> None:
    """系统公告 is readable for every school."""
    user = _user(role="teacher", organization_id=5)
    channel = SimpleNamespace(id=1, channel_type="announce", organization_id=None)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar(channel))
    assert await access_channel(db, 1, user) is channel


@pytest.mark.asyncio
async def test_access_channel_rejects_other_school() -> None:
    """Teachers cannot open another school's 教研组 / 课例."""
    user = _user(role="teacher", organization_id=5)
    channel = SimpleNamespace(id=99, channel_type="public", organization_id=7)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar(channel))
    with pytest.raises(HTTPException) as exc:
        await access_channel(db, 99, user)
    assert exc.value.status_code == 403
    assert "organization" in str(exc.value.detail).lower()


@pytest.mark.asyncio
async def test_school_admin_cannot_open_other_school_channel() -> None:
    """School admins stay inside their own org for channel access."""
    user = _user(role="school_admin", organization_id=5)
    channel = SimpleNamespace(id=99, channel_type="public", organization_id=7)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar(channel))
    with pytest.raises(HTTPException) as exc:
        await access_channel(db, 99, user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_access_channel_message_follows_channel_org() -> None:
    """Message routes inherit the channel's school boundary."""
    user = _user(role="teacher", organization_id=5)
    message = SimpleNamespace(id=3, channel_id=99)
    channel = SimpleNamespace(id=99, channel_type="public", organization_id=7)
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar(message), _scalar(channel)])
    with pytest.raises(HTTPException) as exc:
        await access_channel_message(db, 3, user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_access_dm_partner_rejects_other_school() -> None:
    """DMs cannot cross organizations."""
    user = _user(role="teacher", organization_id=5)
    partner = _user(role="teacher", organization_id=7, user_id=22)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar(partner))
    with pytest.raises(HTTPException) as exc:
        await access_dm_partner(db, user, 22)
    assert exc.value.status_code == 403


def test_permissions_schema_rejects_announce() -> None:
    """The API does not accept announce as a writable channel type."""
    with pytest.raises(ValidationError):
        UpdateChannelPermissionsRequest.model_validate({"channel_type": "announce"})


def test_ws_hides_foreign_school_as_not_found() -> None:
    """Socket clients must not learn that another school's channel exists."""
    assert _ws_access_error_message(HTTPException(status_code=404, detail="Channel not found")) == ("Channel not found")
    assert (
        _ws_access_error_message(HTTPException(status_code=403, detail="Not your organization")) == "Channel not found"
    )


@pytest.mark.asyncio
async def test_service_ignores_announce_type_on_school_channel() -> None:
    """Passing announce does not detach a 教研组 from its school."""
    channel = SimpleNamespace(
        id=20,
        channel_type="public",
        organization_id=5,
        posting_policy="everyone",
        is_default=False,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar(channel))
    db.commit = AsyncMock()
    result = await ChannelService.update_channel_permissions(db, 20, channel_type="announce")
    assert channel.channel_type == "public"
    assert channel.organization_id == 5
    assert result is not None
    assert result["channel_type"] == "public"


@pytest.mark.asyncio
async def test_service_does_not_retarget_announce() -> None:
    """系统公告 stays platform-wide even if a public type is requested."""
    channel = SimpleNamespace(
        id=1,
        channel_type="announce",
        organization_id=None,
        posting_policy="everyone",
        is_default=False,
    )
    db = AsyncMock()
    db.execute = AsyncMock(return_value=_scalar(channel))
    db.commit = AsyncMock()
    result = await ChannelService.update_channel_permissions(db, 1, channel_type="public")
    assert channel.channel_type == "announce"
    assert channel.organization_id is None
    assert result is not None
    assert result["channel_type"] == "announce"


@pytest.mark.asyncio
async def test_announce_attachment_readable_without_membership() -> None:
    """Anyone who can read 系统公告 can download its files."""
    att = as_type(SimpleNamespace(message_id=8, dm_id=None, uploader_id=1), FileAttachment)
    message = SimpleNamespace(channel_id=1)
    channel = SimpleNamespace(id=1, channel_type="announce")
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[_scalar(message), _scalar(channel)])
    assert await user_can_access_attachment(db, 99, att) is True
