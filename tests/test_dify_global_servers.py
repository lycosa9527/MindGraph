"""Dify main and backup env pairs match school 主服务器 and 备用服务器."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Optional, cast
from unittest.mock import AsyncMock

import pytest

from models.domain.auth import Organization
from routers.auth.admin import organization_dify as org_dify_mod
from services.dify import org_mindmate_client as mindmate_client_mod
from services.dify.dify_global_servers import (
    effective_configured_dify_servers,
    global_dify_backup_url,
    global_dify_slot_credentials,
)
from services.dify.dify_server_schema import clear_dify_server_schema_cache, organization_dify_server_slots
from services.redis.cache.redis_dify_server_health_cache import (
    HEALTH_FAILURE_THRESHOLD,
    DifyServerHealth,
)
from tests.typing_helpers import as_organization


def _clear_dify_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "DIFY_API_KEY",
        "DIFY_API_URL",
        "DIFY_BACKUP_API_KEY",
        "DIFY_BACKUP_API_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def _org(**overrides: object) -> Organization:
    base = {
        "id": 7,
        "dify_api_base_url": None,
        "dify_api_key": None,
        "dify_api_base_url_2": None,
        "dify_api_key_2": None,
        "dify_active_server": 1,
        "dify_failover_enabled": True,
    }
    base.update(overrides)
    return as_organization(SimpleNamespace(**base))


def test_env_slots_pair_with_school_servers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dify main is slot 1 and Dify backup is slot 2."""
    _clear_dify_env(monkeypatch)
    monkeypatch.setenv("DIFY_API_KEY", "main-key")
    monkeypatch.setenv("DIFY_API_URL", "https://main.example/v1")
    monkeypatch.setenv("DIFY_BACKUP_API_KEY", "backup-key")
    monkeypatch.setenv("DIFY_BACKUP_API_URL", "https://backup.example/v1")

    main = global_dify_slot_credentials(1)
    backup = global_dify_slot_credentials(2)
    assert main == ("main-key", "https://main.example/v1")
    assert backup == ("backup-key", "https://backup.example/v1")


def test_blank_school_slots_use_env_pair(monkeypatch: pytest.MonkeyPatch) -> None:
    """A school with no override uses Dify main and Dify backup."""
    _clear_dify_env(monkeypatch)
    monkeypatch.setenv("DIFY_API_KEY", "main-key")
    monkeypatch.setenv("DIFY_API_URL", "https://main.example/v1")
    monkeypatch.setenv("DIFY_BACKUP_API_KEY", "backup-key")
    monkeypatch.setenv("DIFY_BACKUP_API_URL", "https://backup.example/v1")

    servers = effective_configured_dify_servers(_org())
    assert [(entry.server, entry.api_url) for entry in servers] == [
        (1, "https://main.example/v1"),
        (2, "https://backup.example/v1"),
    ]


def test_school_override_replaces_matching_env_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 主服务器 override keeps Dify backup on the blank 备用服务器 slot."""
    _clear_dify_env(monkeypatch)
    monkeypatch.setenv("DIFY_API_KEY", "main-key")
    monkeypatch.setenv("DIFY_API_URL", "https://main.example/v1")
    monkeypatch.setenv("DIFY_BACKUP_API_KEY", "backup-key")
    monkeypatch.setenv("DIFY_BACKUP_API_URL", "https://backup.example/v1")

    org = _org(dify_api_base_url="https://school.example/v1", dify_api_key="school-key")
    servers = effective_configured_dify_servers(org)
    assert [(entry.server, entry.api_key) for entry in servers] == [
        (1, "school-key"),
        (2, "backup-key"),
    ]


def test_school_pair_ignores_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """A school that already has two servers does not pick up the env pair."""
    _clear_dify_env(monkeypatch)
    monkeypatch.setenv("DIFY_API_KEY", "main-key")
    monkeypatch.setenv("DIFY_API_URL", "https://main.example/v1")
    monkeypatch.setenv("DIFY_BACKUP_API_KEY", "backup-key")
    monkeypatch.setenv("DIFY_BACKUP_API_URL", "https://backup.example/v1")

    org = _org(
        dify_api_base_url="https://s1.example/v1",
        dify_api_key="k1",
        dify_api_base_url_2="https://s2.example/v1",
        dify_api_key_2="k2",
    )
    servers = effective_configured_dify_servers(org)
    assert [entry.api_key for entry in servers] == ["k1", "k2"]


def test_backup_unset_does_not_fill_slots(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without Dify backup, a blank school stays on its own servers only."""
    _clear_dify_env(monkeypatch)
    monkeypatch.setenv("DIFY_API_KEY", "main-key")
    monkeypatch.setenv("DIFY_API_URL", "https://main.example/v1")

    assert not effective_configured_dify_servers(_org())
    assert global_dify_slot_credentials(2) is None


def test_unset_backup_url_defaults_to_mindspring_host(monkeypatch: pytest.MonkeyPatch) -> None:
    """备用服务器 shows the MindSpring host, not the public Dify placeholder."""
    _clear_dify_env(monkeypatch)

    assert global_dify_backup_url() == "http://dify.mindspringedu.com/v1"
    fields = org_dify_mod.global_mindmate_dify_fields()
    assert fields["dify_backup_api_base_url"] == "http://dify.mindspringedu.com/v1"
    assert fields["dify_backup_api_key_masked"] is None

    monkeypatch.setenv("DIFY_BACKUP_API_KEY", "backup-key")
    assert global_dify_slot_credentials(2) == ("backup-key", "http://dify.mindspringedu.com/v1")


def test_global_fields_expose_backup_without_raw_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Admin default payload names main and backup and masks both keys."""
    _clear_dify_env(monkeypatch)
    monkeypatch.setenv("DIFY_API_KEY", "main-secret-key")
    monkeypatch.setenv("DIFY_API_URL", "https://main.example/v1")
    monkeypatch.setenv("DIFY_BACKUP_API_KEY", "backup-secret-key")
    monkeypatch.setenv("DIFY_BACKUP_API_URL", "https://backup.example/v1")

    fields = org_dify_mod.global_mindmate_dify_fields()
    assert fields["dify_api_base_url"] == "https://main.example/v1"
    assert fields["dify_backup_api_base_url"] == "https://backup.example/v1"
    assert "main-secret-key" not in str(fields["dify_api_key_masked"])
    assert "backup-secret-key" not in str(fields["dify_backup_api_key_masked"])
    assert fields["dify_api_key_masked"]
    assert fields["dify_backup_api_key_masked"]


@pytest.mark.asyncio
async def test_client_fails_over_to_env_backup(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Dify main is down, a school with blank slots is routed to Dify backup."""
    _clear_dify_env(monkeypatch)
    monkeypatch.setenv("DIFY_API_KEY", "main-key")
    monkeypatch.setenv("DIFY_API_URL", "https://main.example/v1")
    monkeypatch.setenv("DIFY_BACKUP_API_KEY", "backup-key")
    monkeypatch.setenv("DIFY_BACKUP_API_URL", "https://backup.example/v1")
    monkeypatch.setenv("DIFY_TIMEOUT", "300")

    org = _org()

    class _Result:
        def scalar_one_or_none(self) -> Organization:
            """Scalar one or none."""
            return org

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result())

    async def fake_health(_org_id: int, server: int) -> Optional[DifyServerHealth]:
        now = 10_000_000_000.0
        if server == 1:
            return DifyServerHealth(
                online=False,
                consecutive_failures=HEALTH_FAILURE_THRESHOLD,
                last_ok_at=None,
                last_checked_at=now,
            )
        return DifyServerHealth(
            online=True,
            consecutive_failures=0,
            last_ok_at=now,
            last_checked_at=now,
        )

    monkeypatch.setattr(mindmate_client_mod, "get_server_health", fake_health)
    client = await mindmate_client_mod.resolve_mindmate_dify_client(db, org.id)
    assert client.api_key == "backup-key"
    assert client.api_url == "https://backup.example/v1"


def test_resolve_slot_two_uses_backup_not_main(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asking for 备用服务器 does not reuse the Dify main key."""
    _clear_dify_env(monkeypatch)
    monkeypatch.setenv("DIFY_API_KEY", "main-key")
    monkeypatch.setenv("DIFY_API_URL", "https://main.example/v1")
    monkeypatch.setenv("DIFY_BACKUP_API_KEY", "backup-key")
    monkeypatch.setenv("DIFY_BACKUP_API_URL", "https://backup.example/v1")

    api_key, api_url = org_dify_mod.resolve_organization_dify_credentials(_org(), server=2)
    assert api_key == "backup-key"
    assert api_url == "https://backup.example/v1"

    monkeypatch.delenv("DIFY_BACKUP_API_KEY")
    monkeypatch.delenv("DIFY_BACKUP_API_URL")
    empty_key, empty_url = org_dify_mod.resolve_organization_dify_credentials(_org(), server=2)
    assert empty_key == ""
    assert empty_url == ""


def test_three_slot_school_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """A school already on servers 2 and 3 keeps that pair."""
    _clear_dify_env(monkeypatch)
    monkeypatch.setenv("DIFY_API_KEY", "main-key")
    monkeypatch.setenv("DIFY_API_URL", "https://main.example/v1")
    monkeypatch.setenv("DIFY_BACKUP_API_KEY", "backup-key")
    monkeypatch.setenv("DIFY_BACKUP_API_URL", "https://backup.example/v1")

    org = cast(
        Organization,
        SimpleNamespace(
            id=7,
            dify_api_base_url=None,
            dify_api_key=None,
            dify_api_base_url_2="https://s2.example/v1",
            dify_api_key_2="k2",
            dify_api_base_url_3="https://s3.example/v1",
            dify_api_key_3="k3",
            dify_active_server=2,
            dify_failover_enabled=True,
        ),
    )
    monkeypatch.setattr(
        "services.dify.dify_server_schema._organization_column_names",
        lambda: frozenset(
            {
                "dify_api_base_url",
                "dify_api_key",
                "dify_api_base_url_2",
                "dify_api_key_2",
                "dify_api_base_url_3",
                "dify_api_key_3",
            }
        ),
    )
    clear_dify_server_schema_cache()
    organization_dify_server_slots.cache_clear()
    try:
        servers = effective_configured_dify_servers(org)
        assert [entry.server for entry in servers] == [2, 3]
        empty_key, empty_url = org_dify_mod.resolve_organization_dify_credentials(org, server=1)
        assert empty_key == ""
        assert empty_url == ""
    finally:
        clear_dify_server_schema_cache()


def test_conversation_on_another_server_drops_its_id() -> None:
    """A 主服务器 thread is not sent to 备用服务器."""
    assert mindmate_client_mod.conversation_owner_server("conv-1", None) == 1
    assert mindmate_client_mod.conversation_owner_server("conv-1", 2) == 2
    assert mindmate_client_mod.conversation_owner_server(None, 2) is None
    assert mindmate_client_mod.upstream_conversation_id("conv-1", 1, 2) is None
    assert mindmate_client_mod.upstream_conversation_id("conv-backup", 2, 2) == "conv-backup"
    assert mindmate_client_mod.upstream_conversation_id(None, None, 2) is None


@pytest.mark.asyncio
async def test_backup_thread_stays_on_backup_after_main_recovers(monkeypatch: pytest.MonkeyPatch) -> None:
    """A chat opened on 备用服务器 keeps its id after 主服务器 is healthy again."""
    _clear_dify_env(monkeypatch)
    monkeypatch.setenv("DIFY_API_KEY", "main-key")
    monkeypatch.setenv("DIFY_API_URL", "https://main.example/v1")
    monkeypatch.setenv("DIFY_BACKUP_API_KEY", "backup-key")
    monkeypatch.setenv("DIFY_BACKUP_API_URL", "https://backup.example/v1")
    monkeypatch.setenv("DIFY_TIMEOUT", "300")

    org = _org()

    class _Result:
        def scalar_one_or_none(self) -> Organization:
            """Scalar one or none."""
            return org

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result())

    async def fake_health(_org_id: int, server: int) -> Optional[DifyServerHealth]:
        now = 10_000_000_000.0
        assert server in (1, 2)
        return DifyServerHealth(
            online=True,
            consecutive_failures=0,
            last_ok_at=now,
            last_checked_at=now,
        )

    class _Session:
        async def __aenter__(self) -> AsyncMock:
            """Yield the stand-in database session."""
            return db

        async def __aexit__(self, *_exc: object) -> bool:
            """Do not swallow exceptions."""
            return False

    monkeypatch.setattr(mindmate_client_mod, "get_server_health", fake_health)
    monkeypatch.setattr(mindmate_client_mod, "system_rls_session", _Session)
    target = await mindmate_client_mod.resolve_mindmate_dify_stream_short_lived(
        org.id,
        detail="missing",
        conversation_id="conv-backup",
        conversation_server=2,
    )
    assert target.client.api_url == "https://backup.example/v1"
    assert target.upstream_conversation_id == "conv-backup"
    assert target.notify_backup is False
    assert target.server == 2


@pytest.mark.asyncio
async def test_main_thread_is_not_sent_to_backup_during_outage(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 主服务器 conversation id is dropped while chat is on 备用服务器."""
    _clear_dify_env(monkeypatch)
    monkeypatch.setenv("DIFY_API_KEY", "main-key")
    monkeypatch.setenv("DIFY_API_URL", "https://main.example/v1")
    monkeypatch.setenv("DIFY_BACKUP_API_KEY", "backup-key")
    monkeypatch.setenv("DIFY_BACKUP_API_URL", "https://backup.example/v1")
    monkeypatch.setenv("DIFY_TIMEOUT", "300")

    org = _org()

    class _Result:
        def scalar_one_or_none(self) -> Organization:
            """Scalar one or none."""
            return org

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result())

    async def fake_health(_org_id: int, server: int) -> Optional[DifyServerHealth]:
        now = 10_000_000_000.0
        if server == 1:
            return DifyServerHealth(
                online=False,
                consecutive_failures=HEALTH_FAILURE_THRESHOLD,
                last_ok_at=None,
                last_checked_at=now,
            )
        return DifyServerHealth(
            online=True,
            consecutive_failures=0,
            last_ok_at=now,
            last_checked_at=now,
        )

    class _Session:
        async def __aenter__(self) -> AsyncMock:
            """Yield the stand-in database session."""
            return db

        async def __aexit__(self, *_exc: object) -> bool:
            """Do not swallow exceptions."""
            return False

    monkeypatch.setattr(mindmate_client_mod, "get_server_health", fake_health)
    monkeypatch.setattr(mindmate_client_mod, "system_rls_session", _Session)
    target = await mindmate_client_mod.resolve_mindmate_dify_stream_short_lived(
        org.id,
        detail="missing",
        conversation_id="conv-main",
        conversation_server=1,
    )
    assert target.client.api_url == "https://backup.example/v1"
    assert target.upstream_conversation_id is None
    assert target.notify_backup is True
