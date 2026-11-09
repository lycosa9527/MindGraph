"""Live RLS checks for owner-only diagrams, DM parties, and platform-admin rows (rev 0169)."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

import config.database as database_bootstrap
from utils.db.rls_context import RlsContext, rls_async_session, scoped_rls_context

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RLS_DB_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_RLS_DB_TESTS=1 with migrated Postgres and mindgraph_app URL",
)

_CODE = "SCH-RLS-TIGHTEN"
_PHONES = ("19900008101", "19900008102", "19900008103")
_DIAGRAM_ID = "rls-tighten-diagram"


@dataclass(frozen=True)
class _Seed:
    org_id: int
    viewer_id: int
    owner_id: int
    peer_id: int


def _teacher(user_id: int, org_id: int) -> RlsContext:
    return RlsContext(mode="authenticated", user_id=user_id, organization_id=org_id, role="teacher")


async def _system_exec(sql: str, params: Mapping[str, object]) -> None:
    async with rls_async_session(RlsContext.system_bootstrap()) as session:
        await session.execute(text(sql), params)
        await session.commit()


async def _cleanup() -> None:
    async with rls_async_session(RlsContext.system_bootstrap()) as session:
        await session.execute(text("DELETE FROM diagram_shares WHERE diagram_id = :d"), {"d": _DIAGRAM_ID})
        await session.execute(text("DELETE FROM diagrams WHERE id = :d"), {"d": _DIAGRAM_ID})
        await session.execute(
            text("DELETE FROM direct_messages WHERE sender_id IN (SELECT id FROM users WHERE phone = ANY(:phones))"),
            {"phones": list(_PHONES)},
        )
        await session.execute(
            text(
                "DELETE FROM organization_oauth_configs WHERE organization_id IN "
                "(SELECT id FROM organizations WHERE code = :code)"
            ),
            {"code": _CODE},
        )
        await session.execute(text("DELETE FROM users WHERE phone = ANY(:phones)"), {"phones": list(_PHONES)})
        await session.execute(text("DELETE FROM organizations WHERE code = :code"), {"code": _CODE})
        await session.commit()


async def _insert_teacher(session: AsyncSession, phone: str, org_id: int) -> int:
    user_id = (
        await session.execute(
            text(
                """
                INSERT INTO users (
                    phone, password_hash, name, organization_id, role, created_at,
                    login_password_set, allows_simplified_chinese, email_login_whitelisted_from_cn
                )
                VALUES (
                    :phone, 'hash', 'RLS tighten test', :org_id, 'teacher',
                    now() AT TIME ZONE 'utc', false, true, false
                )
                RETURNING id
                """
            ),
            {"phone": phone, "org_id": org_id},
        )
    ).scalar_one()
    return int(user_id)


async def _insert_seed(session: AsyncSession) -> _Seed:
    org_id = (
        await session.execute(
            text(
                "INSERT INTO organizations (code, name, created_at, is_active, school_tier) "
                "VALUES (:code, 'RLS tighten test', now() AT TIME ZONE 'utc', true, 'trial') RETURNING id"
            ),
            {"code": _CODE},
        )
    ).scalar_one()
    viewer_id = await _insert_teacher(session, _PHONES[0], org_id)
    owner_id = await _insert_teacher(session, _PHONES[1], org_id)
    peer_id = await _insert_teacher(session, _PHONES[2], org_id)
    await session.execute(
        text(
            "INSERT INTO diagrams (id, user_id, title, diagram_type, spec) "
            "VALUES (:d, :owner, 'RLS tighten', 'mindmap', '{}'::jsonb)"
        ),
        {"d": _DIAGRAM_ID, "owner": owner_id},
    )
    await session.execute(
        text(
            """
            INSERT INTO direct_messages (
                sender_id, recipient_id, content, message_type, is_read, is_deleted, created_at
            )
            VALUES (:owner, :peer, 'private', 'text', false, false, now() AT TIME ZONE 'utc')
            """
        ),
        {"owner": owner_id, "peer": peer_id},
    )
    await session.execute(
        text(
            "INSERT INTO organization_oauth_configs (organization_id, dingtalk_login_app_secret) "
            "VALUES (:org_id, 'secret')"
        ),
        {"org_id": org_id},
    )
    return _Seed(org_id=int(org_id), viewer_id=viewer_id, owner_id=owner_id, peer_id=peer_id)


@pytest_asyncio.fixture(name="seed")
async def fixture_seed() -> AsyncIterator[_Seed]:
    """One school with three teachers, a diagram, a DM, and a login secret."""
    assert database_bootstrap.AsyncSessionLocal is not None
    await _cleanup()
    async with rls_async_session(RlsContext.system_bootstrap()) as session:
        seed = await _insert_seed(session)
        await session.commit()
    try:
        yield seed
    finally:
        await _cleanup()


async def _count(ctx: RlsContext, sql: str, params: Mapping[str, object]) -> int:
    async with rls_async_session(ctx) as session:
        return int((await session.execute(text(sql), params)).scalar_one())


_DIAGRAM_COUNT = "SELECT count(*) FROM diagrams WHERE id = :d"


@pytest.mark.asyncio
async def test_same_school_teacher_cannot_read_unshared_diagram(seed: _Seed) -> None:
    """Being in the same school no longer opens a colleague's diagram."""
    params = {"d": _DIAGRAM_ID}
    assert await _count(_teacher(seed.owner_id, seed.org_id), _DIAGRAM_COUNT, params) == 1
    assert await _count(_teacher(seed.viewer_id, seed.org_id), _DIAGRAM_COUNT, params) == 0


@pytest.mark.asyncio
async def test_share_grants_read_but_not_write(seed: _Seed) -> None:
    """A share recipient can open the diagram but cannot change it."""
    await _system_exec(
        "INSERT INTO diagram_shares (diagram_id, grantee_user_id, shared_by_user_id) VALUES (:d, :v, :o)",
        {"d": _DIAGRAM_ID, "v": seed.viewer_id, "o": seed.owner_id},
    )
    viewer = _teacher(seed.viewer_id, seed.org_id)
    assert await _count(viewer, _DIAGRAM_COUNT, {"d": _DIAGRAM_ID}) == 1
    async with rls_async_session(viewer) as session:
        updated = await session.execute(
            text("UPDATE diagrams SET title = 'hijack' WHERE id = :d RETURNING id"), {"d": _DIAGRAM_ID}
        )
        assert updated.first() is None


@pytest.mark.asyncio
async def test_workshop_visibility_controls_read(seed: _Seed) -> None:
    """An organization workshop is readable by a colleague; a private one is not."""
    viewer = _teacher(seed.viewer_id, seed.org_id)
    await _system_exec(
        "UPDATE diagrams SET workshop_code = 'RLS-WS', workshop_visibility = 'organization' WHERE id = :d",
        {"d": _DIAGRAM_ID},
    )
    assert await _count(viewer, _DIAGRAM_COUNT, {"d": _DIAGRAM_ID}) == 1
    await _system_exec("UPDATE diagrams SET workshop_visibility = 'private' WHERE id = :d", {"d": _DIAGRAM_ID})
    assert await _count(viewer, _DIAGRAM_COUNT, {"d": _DIAGRAM_ID}) == 0


@pytest.mark.asyncio
async def test_direct_messages_are_party_only(seed: _Seed) -> None:
    """A colleague in the same school cannot read someone else's DM."""
    sql = "SELECT count(*) FROM direct_messages WHERE sender_id = :o"
    params = {"o": seed.owner_id}
    assert await _count(_teacher(seed.peer_id, seed.org_id), sql, params) == 1
    assert await _count(_teacher(seed.viewer_id, seed.org_id), sql, params) == 0


@pytest.mark.asyncio
async def test_login_secret_is_platform_admin_only(seed: _Seed) -> None:
    """Teachers and school admins cannot read the DingTalk login secret; superadmin can."""
    sql = "SELECT count(*) FROM organization_oauth_configs WHERE organization_id = :org"
    params = {"org": seed.org_id}
    school_admin = RlsContext(
        mode="panel",
        user_id=seed.viewer_id,
        organization_id=seed.org_id,
        role="school_admin",
        readable_org_ids=str(seed.org_id),
        actor_user_id=seed.viewer_id,
    )
    superadmin = RlsContext(mode="panel", user_id=seed.viewer_id, panel_global_read=True, role="superadmin")
    assert await _count(_teacher(seed.viewer_id, seed.org_id), sql, params) == 0
    assert await _count(school_admin, sql, params) == 0
    assert await _count(superadmin, sql, params) == 1


@pytest.mark.asyncio
async def test_school_admin_cannot_grant_features(seed: _Seed) -> None:
    """Feature grants are a platform decision, not a school-admin write."""
    school_admin = RlsContext(
        mode="panel",
        user_id=seed.viewer_id,
        organization_id=seed.org_id,
        role="school_admin",
        readable_org_ids=str(seed.org_id),
        actor_user_id=seed.viewer_id,
    )
    async with rls_async_session(school_admin) as session:
        with pytest.raises(DBAPIError, match="row-level security"):
            await session.execute(
                text("INSERT INTO feature_access_org_grants (feature_key, organization_id) VALUES ('x', :org)"),
                {"org": seed.org_id},
            )


@pytest.mark.asyncio
async def test_scoped_context_restores_caller(seed: _Seed) -> None:
    """System scope sees the colleague's diagram only inside the block."""
    params = {"d": _DIAGRAM_ID}
    async with rls_async_session(_teacher(seed.viewer_id, seed.org_id)) as session:
        async with scoped_rls_context(session, RlsContext.system_bootstrap()):
            inside = (await session.execute(text(_DIAGRAM_COUNT), params)).scalar_one()
        after = (await session.execute(text(_DIAGRAM_COUNT), params)).scalar_one()
    assert inside == 1
    assert after == 0
