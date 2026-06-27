"""Tests for generate_dingtalk library identity resolution."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.diagram.dify_user_resolve import (
    DiagramSaveIdentity,
    library_save_skip_reason,
    resolve_diagram_save_identity,
)
from services.diagram.library_save_user_notices import (
    library_save_limit_notice,
    library_save_skip_user_notice,
)
from services.diagram.generation_library_save import SAVE_LIMIT_REACHED
from utils.dify_user_key import resolve_user_and_org_from_dify_key


def test_library_save_skip_reason_success() -> None:
    """Saved diagram id yields no skip reason."""
    assert (
        library_save_skip_reason(
            user_id=7,
            saved_id="550e8400-e29b-41d4-a716-446655440000",
            dify_user_key="",
        )
        is None
    )


def test_library_save_skip_reason_limit_reached() -> None:
    """Library full maps to limit_reached."""
    assert (
        library_save_skip_reason(
            user_id=7,
            saved_id=SAVE_LIMIT_REACHED,
            dify_user_key="mg_user_7",
        )
        == "limit_reached"
    )


def test_library_save_skip_reason_unbound_staff() -> None:
    """MindBot key without bind maps to unbound_staff."""
    assert (
        library_save_skip_reason(
            user_id=None,
            saved_id=None,
            dify_user_key="mindbot_5_staff42",
        )
        == "unbound_staff"
    )


def test_library_save_skip_reason_no_user() -> None:
    """Missing user maps to no_user."""
    assert (
        library_save_skip_reason(
            user_id=None,
            saved_id=None,
            dify_user_key="",
        )
        == "no_user"
    )


def test_library_save_skip_reason_save_error() -> None:
    """Known user with failed save maps to save_error."""
    assert (
        library_save_skip_reason(
            user_id=7,
            saved_id=None,
            dify_user_key="mg_user_7",
        )
        == "save_error"
    )


def test_library_save_limit_notice_zh() -> None:
    """Chinese limit notice is returned for zh language."""
    assert "图库已满" in library_save_limit_notice("zh")


def test_library_save_limit_notice_en() -> None:
    """English limit notice is returned for en language."""
    assert "library is full" in library_save_limit_notice("en").lower()


def test_library_save_skip_user_notice_unbound_staff() -> None:
    """Unbound staff skip yields bind DingTalk guidance."""
    notice = library_save_skip_user_notice("unbound_staff", "en")
    assert "bind DingTalk" in notice


def test_library_save_skip_user_notice_no_user() -> None:
    """No user skip yields X-MG-Dify-User guidance."""
    notice = library_save_skip_user_notice("no_user", "zh")
    assert "X-MG-Dify-User" in notice


def test_library_save_skip_user_notice_success_empty() -> None:
    """No notice when reason is None or limit_reached."""
    assert library_save_skip_user_notice(None, "en") == ""
    assert library_save_skip_user_notice("limit_reached", "en") == ""


@pytest.mark.asyncio
async def test_resolve_user_and_org_mg_user_missing_row() -> None:
    """Unknown mg_user pk returns None."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.first.return_value = None
    db.execute.return_value = result_mock

    user_id, org_id = await resolve_user_and_org_from_dify_key(db, "mg_user_999")
    assert user_id is None
    assert org_id is None


@pytest.mark.asyncio
async def test_resolve_user_and_org_mg_user_valid_row() -> None:
    """Valid mg_user pk returns user and org from users row."""
    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.first.return_value = (42, 5)
    db.execute.return_value = result_mock

    user_id, org_id = await resolve_user_and_org_from_dify_key(db, "mg_user_42")
    assert user_id == 42
    assert org_id == 5


@pytest.mark.asyncio
async def test_resolve_diagram_save_identity_from_current_user() -> None:
    """JWT user path returns id and organization_id without Dify key."""
    db = AsyncMock()
    user = MagicMock()
    user.id = 11
    user.organization_id = 3
    request = MagicMock()
    request.headers.get.return_value = ""

    identity = await resolve_diagram_save_identity(db, request, user, None)
    assert identity == DiagramSaveIdentity(user_id=11, organization_id=3, dify_user_key="")


@pytest.mark.asyncio
async def test_resolve_diagram_save_identity_from_header() -> None:
    """X-MG-Dify-User header resolves mg_user pk."""
    db = AsyncMock()
    request = MagicMock()

    def _header(name: str) -> str:
        if name == "X-MG-Dify-User":
            return "mg_user_42"
        return ""

    request.headers.get.side_effect = _header
    with patch(
        "services.diagram.dify_user_resolve.resolve_user_and_org_from_dify_key",
        new_callable=AsyncMock,
        return_value=(42, 5),
    ) as resolve_mock:
        identity = await resolve_diagram_save_identity(db, request, None, None)

    resolve_mock.assert_awaited_once_with(db, "mg_user_42")
    assert identity == DiagramSaveIdentity(user_id=42, organization_id=5, dify_user_key="mg_user_42")


@pytest.mark.asyncio
async def test_resolve_diagram_save_identity_from_mg_dify_user_body() -> None:
    """mg_dify_user body field resolves when header absent."""
    db = AsyncMock()
    request = MagicMock()
    request.headers.get.return_value = ""
    req = MagicMock()
    req.dify_user_id = None
    req.mg_dify_user = "mindbot_5_staff42"

    with patch(
        "services.diagram.dify_user_resolve.resolve_user_and_org_from_dify_key",
        new_callable=AsyncMock,
        return_value=(77, 5),
    ) as resolve_mock:
        identity = await resolve_diagram_save_identity(db, request, None, req)

    resolve_mock.assert_awaited_once_with(db, "mindbot_5_staff42")
    assert identity.user_id == 77


@pytest.mark.asyncio
async def test_resolve_diagram_save_identity_no_key() -> None:
    """Missing header and body yields empty identity."""
    db = AsyncMock()
    request = MagicMock()
    request.headers.get.return_value = ""

    with patch(
        "services.diagram.dify_user_resolve.lookup_solo_recent_mindbot_session",
        new_callable=AsyncMock,
        return_value=None,
    ):
        identity = await resolve_diagram_save_identity(db, request, None, None)
    assert identity == DiagramSaveIdentity(user_id=None, organization_id=None, dify_user_key="")


@pytest.mark.asyncio
async def test_resolve_diagram_save_identity_from_mindmate_session() -> None:
    """MindMate session bridges conversation_id to logged-in user without custom header."""
    db = AsyncMock()
    request = MagicMock()
    request.headers.get.return_value = ""
    req = MagicMock()
    req.dify_user_id = None
    req.mg_dify_user = None
    req.conversation_id = "conv-abc"
    req.mg_conversation_id = None

    with patch(
        "services.diagram.dify_user_resolve.lookup_generation_session",
        new_callable=AsyncMock,
    ) as lookup_mock:
        lookup_mock.return_value = {
            "channel": "mindmate",
            "user_id": 3,
            "organization_id": 9,
            "dify_user_id": "mg_user_3",
        }
        identity = await resolve_diagram_save_identity(db, request, None, req)

    assert identity == DiagramSaveIdentity(
        user_id=3,
        organization_id=9,
        dify_user_key="mg_user_3",
    )


@pytest.mark.asyncio
async def test_resolve_diagram_save_identity_from_mg_conversation_id() -> None:
    """mg_conversation_id body field bridges to session registry."""
    db = AsyncMock()
    request = MagicMock()
    request.headers.get.return_value = ""
    req = MagicMock()
    req.dify_user_id = None
    req.mg_dify_user = None
    req.conversation_id = None
    req.mg_conversation_id = "conv-mg"

    with patch(
        "services.diagram.dify_user_resolve.lookup_generation_session",
        new_callable=AsyncMock,
    ) as lookup_mock:
        lookup_mock.return_value = {
            "channel": "mindbot",
            "user_id": 3,
            "organization_id": 5,
            "dify_user_id": "mindbot_5_staff42",
        }
        identity = await resolve_diagram_save_identity(db, request, None, req)

    lookup_mock.assert_awaited_once_with(conversation_id="conv-mg", dify_user_key=None)
    assert identity.user_id == 3


@pytest.mark.asyncio
async def test_resolve_diagram_save_identity_from_solo_mindbot_session() -> None:
    """Solo recent MindBot session fallback when Dify tool omits identity."""
    db = AsyncMock()
    request = MagicMock()
    request.headers.get.return_value = ""
    req = MagicMock()
    req.dify_user_id = None
    req.mg_dify_user = None
    req.conversation_id = None
    req.mg_conversation_id = None

    with (
        patch(
            "services.diagram.dify_user_resolve.lookup_generation_session",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "services.diagram.dify_user_resolve.lookup_solo_recent_mindbot_session",
            new_callable=AsyncMock,
        ) as solo_mock,
    ):
        solo_mock.return_value = {
            "channel": "mindbot",
            "user_id": 3,
            "organization_id": 5,
            "dify_user_id": "mindbot_5_staff42",
        }
        identity = await resolve_diagram_save_identity(db, request, None, req)

    assert identity == DiagramSaveIdentity(
        user_id=3,
        organization_id=5,
        dify_user_key="mindbot_5_staff42",
    )
