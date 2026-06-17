"""
PostgreSQL startup configuration derived from ``.env``.

Single source of truth for whether MindGraph may ``initdb`` / spawn a local
``postgres`` subprocess vs connect-only to an existing system/external cluster.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse

from scripts.db.migration_urls import ROLE_APP, ROLE_LEGACY, ROLE_MIGRATE

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", ""})


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.getenv(name, "true" if default else "false").strip().lower()
    return raw not in ("false", "0", "no")


def _is_local_host(host: str) -> bool:
    return host.lower() in _LOCAL_HOSTS


def _parse_database_url(raw: str) -> tuple[str, int, str, str]:
    parsed = urlparse(raw)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    user = parsed.username or ""
    path = (parsed.path or "").lstrip("/")
    database = path or "mindgraph"
    return host, port, user, database


@dataclass(frozen=True)
class PostgresRuntimeConfig:
    """Resolved PostgreSQL settings for infrastructure startup."""

    database_url: str
    host: str
    port: int
    port_str: str
    database: str
    runtime_user: str
    provision_user: str
    provision_password: str
    spawn_subprocess: bool
    is_local: bool

    @property
    def uses_rls_runtime_role(self) -> bool:
        """True when DATABASE_URL uses an RLS login role."""
        return self.runtime_user in (ROLE_APP, ROLE_MIGRATE)

    @property
    def mode_label(self) -> str:
        """Human-readable startup mode for logs."""
        if not self.is_local:
            return "external (remote host from DATABASE_URL)"
        if self.spawn_subprocess:
            return "app-managed subprocess"
        return "local system/external (connect only)"

    @property
    def connection_probe_host(self) -> str:
        """Host string for socket/TCP probes (normalises localhost aliases)."""
        if self.host.lower() in ("localhost", "::1"):
            return "127.0.0.1"
        return self.host


def load_postgres_runtime_config() -> PostgresRuntimeConfig:
    """
    Build startup configuration from ``DATABASE_URL`` and ``POSTGRESQL_*`` env vars.

    Spawn/initdb is allowed only when:
    - ``POSTGRESQL_MANAGED_BY_APP`` is true (default), and
    - ``DATABASE_URL`` points at a local host, and
    - the runtime login role is the legacy dev user (``mindgraph_user``), not RLS roles.
    """
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url or "sqlite" in database_url.lower():
        database_url = (
            f"postgresql://{os.getenv('POSTGRESQL_USER', ROLE_LEGACY)}:"
            f"{os.getenv('POSTGRESQL_PASSWORD', 'mindgraph_password')}@"
            f"{os.getenv('POSTGRESQL_HOST', 'localhost')}:"
            f"{os.getenv('POSTGRESQL_PORT', '5432')}/"
            f"{os.getenv('POSTGRESQL_DATABASE', 'mindgraph')}"
        )

    host, port, runtime_user, database = _parse_database_url(database_url)
    env_port = os.getenv("POSTGRESQL_PORT", "").strip()
    if env_port.isdigit():
        port = int(env_port)

    is_local = _is_local_host(host)
    managed_by_app = _env_flag("POSTGRESQL_MANAGED_BY_APP", default=True)
    spawn_subprocess = (
        managed_by_app
        and is_local
        and runtime_user in ("", ROLE_LEGACY)
    )

    provision_user = os.getenv("POSTGRESQL_USER", ROLE_LEGACY)
    provision_password = os.getenv("POSTGRESQL_PASSWORD", "mindgraph_password")
    provision_database = os.getenv("POSTGRESQL_DATABASE", database)

    return PostgresRuntimeConfig(
        database_url=database_url,
        host=host if host else "localhost",
        port=port,
        port_str=str(port),
        database=provision_database,
        runtime_user=runtime_user or ROLE_LEGACY,
        provision_user=provision_user,
        provision_password=provision_password,
        spawn_subprocess=spawn_subprocess,
        is_local=is_local,
    )
